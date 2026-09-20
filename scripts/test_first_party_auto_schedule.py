from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import unittest

from services.first_party_auto_schedule import _content_timing, _choose_campaign_slot


class FirstPartyAutoScheduleTests(unittest.TestCase):
    def setUp(self):
        self.zone = ZoneInfo("America/New_York")

    def posts(self, text):
        return [SimpleNamespace(title=text, body="", source="firstparty:test")]

    def test_explicit_event_start_time_is_parsed(self):
        now = datetime(2026, 9, 20, 12, 0, tzinfo=self.zone)
        timing = _content_timing(self.posts("Race preview September 20 at 7:30 PM"), now)
        self.assertEqual(timing["kind"], "preview")
        self.assertEqual(timing["start"].hour, 19)
        self.assertEqual(timing["start"].minute, 30)

    def test_championship_preview_is_not_mistaken_for_result(self):
        now = datetime(2026, 9, 20, 15, 0, tzinfo=self.zone)
        posts = [SimpleNamespace(
            title="Florence Speedway Championship Finale",
            body="Florence Speedway closes its 2026 season September 19. Read the full event preview before the Championship Finale.",
            source="firstparty:test",
        )]
        timing = _content_timing(posts, now)
        self.assertEqual(timing["kind"], "preview")
        self.assertEqual(timing["start"].date().isoformat(), "2026-09-19")
        slot, reason = _choose_campaign_slot(now, [], posts)
        self.assertIsNone(slot)
        self.assertIn("already started", reason)

    def test_nearby_event_uses_urgent_pre_event_slot(self):
        now = datetime(2026, 9, 20, 17, 50, tzinfo=self.zone)
        slot, reason = _choose_campaign_slot(
            now,
            [],
            self.posts("Tonight's race preview September 20 at 7 PM"),
        )
        self.assertIsNotNone(slot)
        self.assertLess(slot, datetime(2026, 9, 20, 19, 0, tzinfo=self.zone))
        self.assertEqual(reason, "urgent pre-event")

    def test_continuous_pass_contains_daily_campaign_duplicate_sweep(self):
        from pathlib import Path
        source = Path("services/first_party_auto_schedule.py").read_text(encoding="utf-8")
        self.assertIn("def _repair_duplicate_daily_campaigns", source)
        self.assertIn('SocialPost.source.like("dailycampaign:%")', source)
        self.assertIn('SocialPost.source.like("firstparty:%")', source)
        self.assertIn('"archived_duplicate"', source)
        self.assertIn("repaired.extend(_repair_duplicate_daily_campaigns(db))", source)

    def test_preview_is_not_scheduled_after_event_starts(self):
        now = datetime(2026, 9, 20, 19, 10, tzinfo=self.zone)
        slot, reason = _choose_campaign_slot(
            now,
            [],
            self.posts("Where to watch September 20 at 7 PM"),
        )
        self.assertIsNone(slot)
        self.assertIn("already started", reason)


if __name__ == "__main__":
    unittest.main()
