import unittest

from services.social_operator import _next_growth_slot


class ControlCenterLowRiskSchedulerRuntimeTests(unittest.TestCase):
    def test_growth_scheduler_exists_and_returns_future_platform_slot(self):
        for platform in ("facebook", "instagram", "x"):
            slot = _next_growth_slot(platform)
            self.assertIsNotNone(slot.tzinfo)
            self.assertIn("T", slot.isoformat())


if __name__ == "__main__":
    unittest.main()
