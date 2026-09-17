import unittest

from services.master_checklist import bucket_for, normalize_row


class MasterChecklistContract(unittest.TestCase):
    def test_normalizes_live_sheet_row_without_shadow_state(self):
        row = [
            'FALSE',
            'Monitoring',
            'P1',
            'PRT',
            'PRT Early Access bug monitoring',
            'Keep collecting tester reports',
            'Notes',
            '2026-09-15',
        ]
        item = normalize_row(row, row_number=8)
        self.assertEqual(
            item,
            {
                'row_number': 8,
                'done': False,
                'status': 'Monitoring',
                'priority': 'P1',
                'area': 'PRT',
                'task': 'PRT Early Access bug monitoring',
                'next_action': 'Keep collecting tester reports',
                'notes': 'Notes',
                'last_updated': '2026-09-15',
                'desktop_required': False,
                'phone_actionable': False,
            },
        )

    def test_normalizes_short_rows_and_true_checkbox(self):
        item = normalize_row(['TRUE', 'Done', 'Complete', 'PRT', 'Release shipped'], row_number=12)
        self.assertTrue(item['done'])
        self.assertEqual(item['next_action'], '')
        self.assertEqual(item['notes'], '')
        self.assertEqual(item['last_updated'], '')
        self.assertEqual(bucket_for(item), 'completed')

    def test_status_buckets_preserve_sheet_meaning(self):
        cases = {
            'Active': 'active',
            'In Progress': 'active',
            'Waiting': 'waiting',
            'Monitoring': 'monitoring',
            'Blocked': 'blocked',
            'Done': 'completed',
            'Complete': 'completed',
            'Later': 'roadmap',
            'Planned': 'roadmap',
            'Paused': 'roadmap',
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                item = normalize_row(['FALSE', status, 'P2', 'Area', 'Task'], row_number=20)
                self.assertEqual(bucket_for(item), expected)

    def test_device_context_requires_explicit_evidence(self):
        desktop = normalize_row(
            ['FALSE', 'Active', 'P1', 'PRT', 'VR compatibility test', 'Requires Windows PC / iRacing live telemetry'],
            row_number=30,
        )
        phone = normalize_row(
            ['FALSE', 'Active', 'P2', 'Partnerships', 'Follow up with track', 'Phone-actionable today'],
            row_number=31,
        )
        unknown = normalize_row(
            ['FALSE', 'Active', 'P2', 'Content', 'Review article', 'Review the draft'],
            row_number=32,
        )
        self.assertTrue(desktop['desktop_required'])
        self.assertFalse(desktop['phone_actionable'])
        self.assertTrue(phone['phone_actionable'])
        self.assertFalse(phone['desktop_required'])
        self.assertFalse(unknown['phone_actionable'])
        self.assertFalse(unknown['desktop_required'])

    def test_done_checkbox_wins_over_stale_status(self):
        item = normalize_row(['TRUE', 'Monitoring', 'P1', 'Control Center', 'Old item'], row_number=40)
        self.assertEqual(bucket_for(item), 'completed')


if __name__ == '__main__':
    unittest.main()
