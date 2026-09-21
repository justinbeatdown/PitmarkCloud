from pathlib import Path
import unittest


class SocialPacingContractTests(unittest.TestCase):
    def test_shared_guard_exists(self):
        source = Path("services/social_pacing.py").read_text(encoding="utf-8")
        self.assertIn("DEFAULT_DAILY_CAP = 2", source)
        self.assertIn("BUSY_DAY_CAP = 3", source)
        self.assertIn("DEFAULT_MIN_GAP_MINUTES = 180", source)
        self.assertIn("recent manual post suppresses automated post", source)

    def test_all_automation_lanes_use_shared_guard(self):
        growth = Path("services/social_operator.py").read_text(encoding="utf-8")
        daily = Path("services/social_daily_package.py").read_text(encoding="utf-8")
        first_party = Path("services/first_party_auto_schedule.py").read_text(encoding="utf-8")
        self.assertIn("pacing_decision", growth)
        self.assertIn("pacing_decision", daily)
        self.assertIn("pacing_decision", first_party)

    def test_priority_path_is_reserved_for_time_sensitive_first_party(self):
        source = Path("services/first_party_auto_schedule.py").read_text(encoding="utf-8")
        self.assertIn('priority = _content_timing(posts, now_local)["kind"] != "evergreen"', source)
        self.assertIn("priority=priority", source)


if __name__ == "__main__":
    unittest.main()
