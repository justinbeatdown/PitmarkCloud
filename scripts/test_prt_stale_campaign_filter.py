from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from sqlalchemy import delete, select

from services import persistent_store
from services.control_center import SocialPost
from services.database import engine, SessionLocal
from services.first_party_models import FirstPartyEvent, FirstPartyState
from services.social_asset_pool import SocialAsset, SocialAssetUpload
from services.social_daily_campaign import DailyCampaign, DailyCampaignAsset, campaign_day_key


class StalePrtCampaignFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        persistent_store.RuntimeStateRow.__table__.create(bind=engine, checkfirst=True)
        FirstPartyEvent.__table__.create(bind=engine, checkfirst=True)
        FirstPartyState.__table__.create(bind=engine, checkfirst=True)
        SocialPost.__table__.create(bind=engine, checkfirst=True)
        SocialAsset.__table__.create(bind=engine, checkfirst=True)
        SocialAssetUpload.__table__.create(bind=engine, checkfirst=True)
        DailyCampaign.__table__.create(bind=engine, checkfirst=True)
        DailyCampaignAsset.__table__.create(bind=engine, checkfirst=True)

    def test_stale_prt_release_event_does_not_beat_fresh_blog(self):
        from services.social_daily_campaign import select_campaign_topic

        now = datetime(2099, 1, 2, 12, 0, tzinfo=timezone.utc)
        runtime_key = "prt_release_last_announced_version"
        first_party_key = "prt_manifest_version"
        stale_key = "test:prt_release:0.16.76"
        blog_key = "test:blog:fresh"

        with SessionLocal() as db:
            old_runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
            old_runtime_value = old_runtime.value if old_runtime else None
            old_first = db.get(FirstPartyState, first_party_key)
            old_first_value = old_first.value if old_first else None

        persistent_store.set_runtime_state(runtime_key, "0.16.82")
        with SessionLocal() as db:
            state = db.get(FirstPartyState, first_party_key)
            if state is None:
                db.add(FirstPartyState(state_key=first_party_key, value="0.16.76"))
            else:
                state.value = "0.16.76"
            db.add(FirstPartyEvent(
                event_key=stale_key,
                event_type="prt_release",
                title="PRT v0.16.76 released",
                summary="Stale release event.",
                url="https://prt.pitmarkracing.com",
                payload_json=json.dumps({"version": "0.16.76"}),
                status="processed",
                created_at=now,
                updated_at=now,
            ))
            db.add(FirstPartyEvent(
                event_key=blog_key,
                event_type="blog_publish",
                title="Fresh Racing Culture Story",
                summary="Fresh verified Pitmark story.",
                url="https://pitmarkracing.com/blogs/racing-culture/test",
                payload_json="{}",
                status="processed",
                created_at=now,
                updated_at=now,
            ))
            db.commit()

        try:
            topic = select_campaign_topic(now)
            self.assertEqual(topic["topic_type"], "blog_publish")
            self.assertEqual(topic["title"], "Fresh Racing Culture Story")
        finally:
            with SessionLocal() as db:
                db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([stale_key, blog_key])))
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

    def test_existing_stale_prt_daily_campaign_is_replaced_and_old_queue_is_cleared(self):
        from services.social_daily_campaign import ensure_daily_campaign

        now = datetime(2099, 1, 3, 17, 0, tzinfo=timezone.utc)
        day_key = campaign_day_key(now)
        runtime_key = "prt_release_last_announced_version"
        first_party_key = "prt_manifest_version"
        stale_key = "test:reset:prt_release:0.16.76"
        blog_key = "test:reset:blog:fresh"
        upload_token = "test-stale-campaign-upload"

        with SessionLocal() as db:
            old_runtime = db.get(persistent_store.RuntimeStateRow, runtime_key)
            old_runtime_value = old_runtime.value if old_runtime else None
            old_first = db.get(FirstPartyState, first_party_key)
            old_first_value = old_first.value if old_first else None
            db.execute(delete(DailyCampaign).where(DailyCampaign.day_key == day_key))
            db.execute(delete(SocialAssetUpload).where(SocialAssetUpload.public_token == upload_token))
            db.commit()

        persistent_store.set_runtime_state(runtime_key, "0.16.82")
        with SessionLocal() as db:
            state = db.get(FirstPartyState, first_party_key)
            if state is None:
                db.add(FirstPartyState(state_key=first_party_key, value="0.16.76"))
            else:
                state.value = "0.16.76"

            stale_event = FirstPartyEvent(
                event_key=stale_key,
                event_type="prt_release",
                title="PRT v0.16.76 released",
                summary="Bad stale event.",
                url="https://prt.pitmarkracing.com",
                payload_json=json.dumps({"version": "0.16.76"}),
                status="processed",
                created_at=now,
                updated_at=now,
            )
            blog_event = FirstPartyEvent(
                event_key=blog_key,
                event_type="blog_publish",
                title="Correct Fresh Story",
                summary="Fresh campaign source.",
                url="https://pitmarkracing.com/blogs/racing-culture/correct",
                payload_json="{}",
                status="processed",
                created_at=now,
                updated_at=now,
            )
            db.add_all([stale_event, blog_event])
            db.flush()

            stale_campaign = DailyCampaign(
                day_key=day_key,
                topic_type="prt_release",
                topic_ref=f"firstparty:{stale_event.id}",
                title="PRT v0.16.76 released",
                summary="Bad stale campaign.",
                url="https://prt.pitmarkracing.com",
                status="ready",
                package_json=json.dumps({"copy": {"facebook": "bad old copy"}}),
            )
            db.add(stale_campaign)
            db.flush()
            old_campaign_id = stale_campaign.id
            old_asset_url = f"https://pcc.pitmarkracing.com/social-assets/{upload_token}"
            db.add(DailyCampaignAsset(
                campaign_id=old_campaign_id,
                platform="instagram",
                slot=1,
                aspect="4:5",
                prompt="old",
                url=old_asset_url,
                status="ready",
            ))
            db.add(SocialPost(
                platform="facebook",
                title="old",
                body="bad old copy",
                source=f"dailycampaign:{old_campaign_id}",
                status="scheduled",
            ))
            db.add(SocialAssetUpload(
                public_token=upload_token,
                filename="old.png",
                mime_type="image/png",
                data=b"old",
            ))
            db.add(SocialAsset(
                url=old_asset_url,
                title="old",
                source="daily_campaign",
                source_ref=f"dailycampaign:{old_campaign_id}:instagram:1",
                asset_type="image",
                tags="pitmark,daily-campaign",
                active=True,
            ))
            db.commit()

        try:
            campaign = ensure_daily_campaign(now)
            self.assertEqual(campaign["topic_type"], "blog_publish")
            self.assertEqual(campaign["title"], "Correct Fresh Story")
            self.assertNotEqual(campaign["title"], "PRT v0.16.76 released")
            with SessionLocal() as db:
                old_assets = list(db.scalars(select(DailyCampaignAsset).where(DailyCampaignAsset.campaign_id == old_campaign_id)).all())
                old_posts = list(db.scalars(select(SocialPost).where(SocialPost.source == f"dailycampaign:{old_campaign_id}")).all())
                old_pool = list(db.scalars(select(SocialAsset).where(SocialAsset.source_ref.like(f"dailycampaign:{old_campaign_id}:%"))).all())
                old_upload = db.scalar(select(SocialAssetUpload).where(SocialAssetUpload.public_token == upload_token))
                self.assertEqual(old_assets, [])
                self.assertEqual(old_posts, [])
                self.assertEqual(old_pool, [])
                self.assertIsNone(old_upload)
        finally:
            with SessionLocal() as db:
                db.execute(delete(SocialPost).where(SocialPost.source == f"dailycampaign:{old_campaign_id}"))
                db.execute(delete(DailyCampaignAsset).where(DailyCampaignAsset.campaign_id == old_campaign_id))
                db.execute(delete(SocialAsset).where(SocialAsset.source_ref.like(f"dailycampaign:{old_campaign_id}:%")))
                db.execute(delete(SocialAssetUpload).where(SocialAssetUpload.public_token == upload_token))
                db.execute(delete(DailyCampaign).where(DailyCampaign.day_key == day_key))
                db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key.in_([stale_key, blog_key])))
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
