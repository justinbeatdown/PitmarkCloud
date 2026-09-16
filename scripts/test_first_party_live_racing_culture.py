from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import delete, select

from services.control_center import BlogDraft, ShopifyPublishRecord
from services.database import engine, SessionLocal
from services.first_party_models import FirstPartyEvent


class FirstPartyLiveRacingCultureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BlogDraft.__table__.create(bind=engine, checkfirst=True)
        ShopifyPublishRecord.__table__.create(bind=engine, checkfirst=True)
        FirstPartyEvent.__table__.create(bind=engine, checkfirst=True)

    def test_live_shopify_racing_culture_article_is_queued_without_local_draft_record(self):
        from services.first_party_sources import scan_blogs

        article_id = "gid://shopify/Article/999991"
        handle = "live-racing-culture-autopilot-test"
        event_key = f"blog_publish:shopify:{article_id}"
        expected_url = f"https://pitmarkracing.com/blogs/racing-culture/{handle}"
        published_at = datetime.now(timezone.utc).isoformat()

        with SessionLocal() as db:
            db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key == event_key))
            db.commit()

        shopify_payload = {
            "articles": {
                "nodes": [
                    {
                        "id": article_id,
                        "title": "Live Racing Culture Autopilot Test",
                        "handle": handle,
                        "summary": "A live Shopify article with no local PitmarkDB draft record.",
                        "body": "",
                        "isPublished": True,
                        "publishedAt": published_at,
                        "image": {"originalSrc": "https://cdn.example.com/live-racing-culture.jpg"},
                        "blog": {"handle": "racing-culture", "title": "Racing Culture"},
                    }
                ]
            }
        }

        try:
            with patch("services.first_party_sources.shopify_service.graphql", return_value=shopify_payload):
                result = scan_blogs()

            with SessionLocal() as db:
                row = db.scalar(
                    select(FirstPartyEvent).where(FirstPartyEvent.event_key == event_key)
                )

            self.assertIsNotNone(row)
            self.assertEqual(row.event_type, "blog_publish")
            self.assertEqual(row.title, "Live Racing Culture Autopilot Test")
            self.assertEqual(row.url, expected_url)
            self.assertEqual(row.media_url, "https://cdn.example.com/live-racing-culture.jpg")
            self.assertGreaterEqual(result.get("queued", 0), 1)
        finally:
            with SessionLocal() as db:
                db.execute(delete(FirstPartyEvent).where(FirstPartyEvent.event_key == event_key))
                db.commit()


if __name__ == "__main__":
    unittest.main()
