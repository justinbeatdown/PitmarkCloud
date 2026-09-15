from datetime import datetime, timezone
import unittest

from services.social_operator_logic import counts_toward_daily_coverage, summarize_channel_health


class SocialOperatorLogicTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    def test_pending_draft_does_not_count_as_daily_coverage(self):
        self.assertFalse(counts_toward_daily_coverage(
            status='pending', scheduled_for=None,
            created_at=self.now, updated_at=self.now,
            now=self.now, timezone_name='America/New_York'))

    def test_published_today_counts_as_daily_coverage(self):
        published = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)
        self.assertTrue(counts_toward_daily_coverage(
            status='published', scheduled_for=None,
            created_at=published, updated_at=published,
            now=self.now, timezone_name='America/New_York'))

    def test_scheduled_today_counts_as_daily_coverage(self):
        self.assertTrue(counts_toward_daily_coverage(
            status='scheduled', scheduled_for='2026-09-15T18:45:00-04:00',
            created_at=self.now, updated_at=self.now,
            now=self.now, timezone_name='America/New_York'))

    def test_channel_failure_marks_run_degraded(self):
        status, note = summarize_channel_health({
            'facebook': {'ok': False, 'error': 'Meta rejected request: pages_read_user_content required'},
            'instagram': {'ok': True, 'scanned': 0},
            'x': {'ok': True, 'scanned': 1},
        })
        self.assertEqual(status, 'degraded')
        self.assertIn('facebook', note.lower())
        self.assertIn('pages_read_user_content', note)

    def test_all_channels_healthy_marks_run_complete(self):
        status, note = summarize_channel_health({
            'facebook': {'ok': True, 'scanned': 0},
            'instagram': {'ok': True, 'scanned': 0},
            'x': {'ok': True, 'scanned': 0},
        })
        self.assertEqual(status, 'complete')
        self.assertEqual(note, '')


if __name__ == '__main__':
    unittest.main()
