from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SocialOperationsShutdownContractTests(unittest.TestCase):
    def test_scheduler_skips_social_operations_when_disabled(self):
        text = (ROOT / "services" / "autopilot_multiplatform.py").read_text(encoding="utf-8")
        self.assertIn("Social Operations disabled; skipping autonomous social pass", text)
        self.assertIn("settings.social_operator_enabled", text)

    def test_publish_worker_blocks_existing_automatic_social_rows_when_disabled(self):
        text = (ROOT / "services" / "social_publish_worker.py").read_text(encoding="utf-8")
        self.assertIn("_automatic_social_source", text)
        self.assertIn("settings.social_operator_enabled", text)
        self.assertIn('startswith("dailycampaign:")', text)
        self.assertIn('startswith("firstparty:")', text)
        self.assertIn('"operator:growth-loop"', text)


if __name__ == "__main__":
    unittest.main()
