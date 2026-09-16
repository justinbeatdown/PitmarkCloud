from __future__ import annotations

from datetime import datetime, timezone
import unittest


class SocialDailyCampaignContractTests(unittest.TestCase):
    def test_local_day_key_uses_pitmark_timezone(self):
        from services.social_daily_campaign import campaign_day_key
        instant = datetime(2026, 9, 16, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(campaign_day_key(instant, timezone_name="America/New_York"), "2026-09-15")

    def test_package_contract_requires_full_platform_copy_and_assets(self):
        from services.social_daily_campaign import REQUIRED_COPY_PLATFORMS, REQUIRED_IG_SLIDES, REQUIRED_VERTICAL_ASSETS
        self.assertEqual(REQUIRED_COPY_PLATFORMS, ("facebook", "instagram", "x", "discord", "tiktok_reels"))
        self.assertEqual(REQUIRED_IG_SLIDES, 6)
        self.assertGreaterEqual(REQUIRED_VERTICAL_ASSETS, 4)

    def test_fallback_topic_is_deterministic_for_day(self):
        from services.social_daily_campaign import fallback_topic
        first = fallback_topic("2026-09-15")
        second = fallback_topic("2026-09-15")
        self.assertEqual(first, second)
        self.assertEqual(first["topic_type"], "community_growth")
        self.assertTrue(first["title"])
        self.assertTrue(first["summary"])

    def test_package_progress_reports_ready_only_when_complete(self):
        from services.social_daily_campaign import summarize_package_progress
        incomplete = summarize_package_progress({
            "copy": {"facebook": "a", "instagram": "b"},
            "instagram_assets": ["1", "2"],
            "vertical_assets": [],
        })
        self.assertFalse(incomplete["complete"])
        self.assertEqual(incomplete["copy_ready"], 2)
        self.assertEqual(incomplete["ig_assets_ready"], 2)

        complete = summarize_package_progress({
            "copy": {name: name for name in ("facebook", "instagram", "x", "discord", "tiktok_reels")},
            "instagram_assets": [str(i) for i in range(6)],
            "vertical_assets": [str(i) for i in range(4)],
        })
        self.assertTrue(complete["complete"])
        self.assertEqual(complete["copy_ready"], 5)
        self.assertEqual(complete["ig_assets_ready"], 6)
        self.assertEqual(complete["vertical_assets_ready"], 4)


if __name__ == "__main__":
    unittest.main()
