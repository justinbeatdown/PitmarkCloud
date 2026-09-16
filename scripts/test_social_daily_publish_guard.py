from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SocialDailyPublishGuardTests(unittest.TestCase):
    def test_daily_campaign_instagram_skips_single_image_worker(self):
        text = (ROOT / "services" / "social_publish_worker.py").read_text(encoding="utf-8")
        self.assertIn('platform == "instagram"', text)
        self.assertIn('startswith("dailycampaign:")', text)
        self.assertIn("carousel", text.lower())


if __name__ == "__main__":
    unittest.main()
