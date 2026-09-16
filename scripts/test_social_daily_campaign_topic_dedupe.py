from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from sqlalchemy import delete, select

from services import persistent_store
from services.control_center import SocialPost
from services.database import engine, SessionLocal
from services.first_party_models import FirstPartyEvent, FirstPartyState
from services.social_asset_pool import SocialAsset, SocialAssetUpload
from services.social_daily_campaign import DailyCampaign, DailyCampaignAsset, campaign_day_key


class DailyCampaignTopicDedupeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        persistent_store.RuntimeStateRow.__table__.create(bind=engine, checkfirst=True)
        FirstPartyEvent.__table__.create(bind=engine, checkfirst=True)
        FirstPartyState.__table__.create(bind=engine, checkfirst=True)
        DailyCampaign.__table__.create(bind=engine, checkfirst=True)
        DailyCampaignAsset.__table__.create(bind=engine, checkfirst=True)
        SocialPost.__table__.create(bind=engine, checkfirst=True)
        SocialAsset.__table__.create(bind=engine, checkfirst=True)
        SocialAssetUpload.__table__.create(bind=engine, checkfirst=True)

    def test_previous_day_topic_is_not_selected_again(self):
        from services.social_daily_campaign import select_campaign_topic

        now = datetime(2099, 1, 4, 17, 0, tzinfo=timezone.utc)
        previous_day = campaign_day_key(datetime(2099, 1, 3, 17, 0, tzinfo=timezone.utc))
        runtime_key = "prt_release_last_announced_version"
        first_party_key = "prt_manifest_version"
        release_key = "test:dedupe:prt_release:0.16.82"
        blog_key = "test:dedupe:blog:fresh"

        with SessionLocal() as db:
            old_runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
            old_runtime_value = old_runtime.value if old_runtime else None
            old_first = db.get(FirstPartyState, first_party_key)
            old_first_value = old_first.value if old_first else None
            db.execute(delete(DailyCampaign).where(DailyCampaign.day_key == previous_day))
            db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([release_key, blog_key])))
            db.commit()

        persistent_store.set_runtime_state(runtime_key, "0.16.82")
        with SessionLocal() as db:
            state = db.get(FirstPartyState, first_party_key)
            if state is None:
                db.add(FirstPartyState(state_key=first_party_key, value="0.16.82"))
            else:
                state.value = "0.16.82"

            release_event = FirstPartyEvent(
                event_key=release_key,
                event_type="prt_release",
                title="PRT v0.16.82 released",
                summary="Current release.",
                url="https://prt.pitmarkracing.com",
                payload_json=json.dumps({"version": "0.16.82"}),
                status="processed",
                created_at=now,
                updated_at=now,
            )
            blog_event = FirstPartyEvent(
                event_key=blog_key,
                event_type="blog_publish",
                title="Fresh Racing Culture Story",
                summary="A fresh verified story.",
                url="https://pitmarkracing.com/blogs/racing-culture/fresh-dedupe-test",
                payload_json="{}",
                status="processed",
                created_at=now,
                updated_at=now,
            )
            db.add_all([release_event, blog_event])
            db.flush()
            db.add(DailyCampaign(
                day_key=previous_day,
                topic_type="prt_release",
                topic_ref=f"firstparty:{release_event.id}",
                title="PRT v0.16.82 released",
                summary="Yesterday's campaign.",
                url="https://prt.pitmarkracing.com",
                status="ready",
                package_json="{}",
            ))
            db.commit()

        try:
            topic = select_campaign_topic(now)
            self.assertEqual(topic["topic_type"], "blog_publish")
            self.assertEqual(topic["title"], "Fresh Racing Culture Story")
        finally:
            with SessionLocal() as db:
                db.execute(delete(DailyCampaign).where(DailyCampaign.day_key == previous_day))
                db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([release_key, blog_key])))
                runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
                if old_runtime_value is None:
                    if runtime is not None:
                        db.delete(runtime)
                elif runtime is not None:
                    runtime.value = old_runtime_value
                first = db.get(FirstPartyState, first_party_key)
                if old_first_value is None:
                    if first is not None:
                        db.delete(first)
                elif first is not None:
                    first.value = old_first_value
                db.commit()

    def test_occupied_daily_platform_slot_is_not_scheduled_twice(self):
        from services.social_daily_package import sync_campaign_queue

        occupied_source = "dailycampaign:test-occupied"
        new_source = "dailycampaign:987654"
        scheduled_for = "2099-01-04T11:15:00-05:00"
        with SessionLocal() as db:
            db.execute(delete(SocialPost).where(SocialPost.source.in_([occupied_source, new_source])))
            db.add(SocialPost(
                platform="facebook",
                title="Existing daily campaign",
                body="Existing scheduled copy",
                source=occupied_source,
                status="scheduled",
                risk="low",
                scheduled_for=scheduled_for,
            ))
            db.commit()

        campaign = {
            "id": 987654,
            "title": "Different daily topic",
            "topic_type": "blog_publish",
        }
        package = {"copy": {"facebook": "New daily campaign copy"}, "instagram_assets": []}
        try:
            with patch("services.social_daily_package._schedule_for", return_value=scheduled_for), patch(
                "services.social_daily_package.settings.social_operator_autopublish_low_risk", True
            ):
                result = sync_campaign_queue(campaign, package)

            facebook = result["items"]["facebook"]
            self.assertEqual(facebook["status"], "pending")
            self.assertIsNone(facebook["scheduled_for"])
            with SessionLocal() as db:
                scheduled = list(
                    db.scalars(
                        select(SocialPost).where(
                            SocialPost.platform == "facebook",
                            SocialPost.status == "scheduled",
                            SocialPost.scheduled_for == scheduled_for,
                        )
                    ).all()
                )
                self.assertEqual(len(scheduled), 1)
        finally:
            with SessionLocal() as db:
                db.execute(delete(SocialPost).where(SocialPost.source.in_([occupied_source, new_source])))
                db.commit()

    def test_existing_current_day_duplicate_topic_self_heals(self):
        from services.social_daily_campaign import ensure_daily_campaign

        now = datetime(2099, 2, 4, 17, 0, tzinfo=timezone.utc)
        previous_day = campaign_day_key(datetime(2099, 2, 3, 17, 0, tzinfo=timezone.utc))
        current_day = campaign_day_key(now)
        runtime_key = "prt_release_last_announced_version"
        first_party_key = "prt_manifest_version"
        release_key = "test:selfheal:prt_release:0.16.82"
        blog_key = "test:selfheal:blog:fresh"

        with SessionLocal() as db:
            old_runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
            old_runtime_value = old_runtime.value if old_runtime else None
            old_first = db.get(FirstPartyState, first_party_key)
            old_first_value = old_first.value if old_first else None
            existing_campaigns = list(
                db.scalars(select(DailyCampaign).where(DailyCampaign.day_key.in_([previous_day, current_day]))).all()
            )
            for row in existing_campaigns:
                db.execute(delete(SocialPost).where(SocialPost.source == f"dailycampaign:{row.id}"))
                db.execute(delete(DailyCampaignAsset).where(DailyCampaignAsset.campaign_id == row.id))
                db.execute(delete(DailyCampaign).where(DailyCampaign.id == row.id))
            db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([release_key, blog_key])))
            db.commit()

        persistent_store.set_runtime_state(runtime_key, "0.16.82")
        duplicate_id = None
        with SessionLocal() as db:
            state = db.get(FirstPartyState, first_party_key)
            if state is None:
                db.add(FirstPartyState(state_key=first_party_key, value="0.16.82"))
            else:
                state.value = "0.16.82"
            release_event = FirstPartyEvent(
                event_key=release_key,
                event_type="prt_release",
                title="PRT v0.16.82 released",
                summary="Current release.",
                url="https://prt.pitmarkracing.com",
                payload_json=json.dumps({"version": "0.16.82"}),
                status="processed",
                created_at=now,
                updated_at=now,
            )
            blog_event = FirstPartyEvent(
                event_key=blog_key,
                event_type="blog_publish",
                title="Replacement Racing Culture Story",
                summary="A distinct verified story.",
                url="https://pitmarkracing.com/blogs/racing-culture/replacement-self-heal-test",
                payload_json="{}",
                status="processed",
                created_at=now,
                updated_at=now,
            )
            db.add_all([release_event, blog_event])
            db.flush()
            prior = DailyCampaign(
                day_key=previous_day,
                topic_type="prt_release",
                topic_ref=f"firstparty:{release_event.id}",
                title="PRT v0.16.82 released",
                summary="Prior day's campaign.",
                status="ready",
                package_json="{}",
            )
            duplicate = DailyCampaign(
                day_key=current_day,
                topic_type="prt_release",
                topic_ref=f"firstparty:{release_event.id}",
                title="PRT v0.16.82 released",
                summary="Accidental midnight duplicate.",
                status="ready",
                package_json="{}",
            )
            db.add_all([prior, duplicate])
            db.flush()
            duplicate_id = duplicate.id
            db.add(SocialPost(
                platform="facebook",
                title="Duplicate queue row",
                body="Duplicate campaign copy",
                source=f"dailycampaign:{duplicate_id}",
                status="scheduled",
                risk="low",
                scheduled_for="2099-02-04T11:15:00-05:00",
            ))
            db.commit()

        try:
            campaign = ensure_daily_campaign(now)
            self.assertEqual(campaign["day_key"], current_day)
            self.assertEqual(campaign["topic_type"], "blog_publish")
            self.assertEqual(campaign["title"], "Replacement Racing Culture Story")
            with SessionLocal() as db:
                current_rows = list(
                    db.scalars(select(DailyCampaign).where(DailyCampaign.day_key == current_day)).all()
                )
                self.assertEqual(len(current_rows), 1)
                self.assertEqual(current_rows[0].topic_type, "blog_publish")
                self.assertEqual(current_rows[0].title, "Replacement Racing Culture Story")
                duplicate_posts = list(
                    db.scalars(select(SocialPost).where(SocialPost.source == f"dailycampaign:{duplicate_id}")).all()
                )
                self.assertEqual(duplicate_posts, [])
        finally:
            with SessionLocal() as db:
                campaigns = list(
                    db.scalars(select(DailyCampaign).where(DailyCampaign.day_key.in_([previous_day, current_day]))).all()
                )
                for row in campaigns:
                    db.execute(delete(SocialPost).where(SocialPost.source == f"dailycampaign:{row.id}"))
                    db.execute(delete(DailyCampaignAsset).where(DailyCampaignAsset.campaign_id == row.id))
                    db.execute(delete(DailyCampaign).where(DailyCampaign.id == row.id))
                db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([release_key, blog_key])))
                runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
                if old_runtime_value is None:
                    if runtime is not None:
                        db.delete(runtime)
                elif runtime is not None:
                    runtime.value = old_runtime_value
                first = db.get(FirstPartyState, first_party_key)
                if old_first_value is None:
                    if first is not None:
                        db.delete(first)
                elif first is not None:
                    first.value = old_first_value
                db.commit()


if __name__ == "__main__":
    unittest.main()
