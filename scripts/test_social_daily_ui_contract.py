from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SocialDailyUiContractTests(unittest.TestCase):
    def test_operator_api_exposes_daily_campaign_status_and_run(self):
        text = (ROOT / "api" / "social_operator.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/daily-campaign/status")', text)
        self.assertIn('@router.post("/daily-campaign/run")', text)
        self.assertIn('payload["daily_campaign"]', text)

    def test_control_center_shows_daily_campaign_progress(self):
        text = (ROOT / "api" / "control_social_daily_campaign.js").read_text(encoding="utf-8")
        for token in (
            "Today's Campaign",
            "Platform Copy",
            "Instagram Slides",
            "Vertical Assets",
            "TikTok / Reels",
            "daily-campaign/run",
        ):
            self.assertIn(token, text)

    def test_daily_campaign_preview_uses_same_origin_asset_path(self):
        text = (ROOT / "api" / "control_social_daily_campaign.js").read_text(encoding="utf-8")
        self.assertIn("function previewAssetUrl", text)
        self.assertIn("previewAssetUrl(item.url)", text)
        self.assertIn("/social-assets/", text)

    def test_daily_campaign_assets_are_layered_into_control_center(self):
        text = (ROOT / "api" / "social_operator.py").read_text(encoding="utf-8")
        self.assertIn("control_social_daily_campaign.js", text)
        self.assertIn("control_social_daily_campaign.css", text)


if __name__ == "__main__":
    unittest.main()
