from pathlib import Path
import unittest


class PrtReleaseGatewayContractTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("services/discord_gateway_service.py").read_text(encoding="utf-8")

    def test_gateway_imports_release_announcement_service(self):
        self.assertIn("prt_release_announcements", self.source)

    def test_on_ready_starts_single_release_watcher(self):
        self.assertIn("_release_watcher_task", self.source)
        self.assertIn("prt_release_announcements.watch(self)", self.source)
        self.assertIn('name="pitmark-prt-release-announcements"', self.source)

    def test_stop_cancels_release_watcher(self):
        self.assertIn("_release_watcher_task.cancel()", self.source)
        self.assertIn("await _release_watcher_task", self.source)


if __name__ == "__main__":
    unittest.main()
