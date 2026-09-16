from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from sqlalchemy import delete

from services import persistent_store
from services.database import engine, SessionLocal
from services.first_party_models import FirstPartyEvent, FirstPartyState


class StalePrtCampaignFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        persistent_store.RuntimeStateRow.__table__.create(bind=engine, checkfirst=True)
        FirstPartyEvent.__table__.create(bind=engine, checkfirst=True)
        FirstPartyState.__table__.create(bind=engine, checkfirst=True)

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


if __name__ == "__main__":
    unittest.main()
