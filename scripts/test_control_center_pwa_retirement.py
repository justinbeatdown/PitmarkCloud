from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControlCenterPwaRetirementContract(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_service_worker_is_retirement_only(self):
        sw = self.read("api/control_sw.js")
        self.assertIn("registration.unregister", sw)
        self.assertIn("caches.keys", sw)
        self.assertIn("clients.matchAll", sw)
        self.assertNotIn("control-mobile.js", sw)
        self.assertNotIn("control-mobile-blog.js", sw)
        self.assertNotIn("pitmark-mobile-v0.21.42", sw)

    def test_recovery_route_sits_outside_old_worker_scope(self):
        ui = self.read("api/control_center_ui.py")
        self.assertIn("@router.get('/control-reset'", ui)
        self.assertIn("navigator.serviceWorker.getRegistrations", ui)
        self.assertIn("caches.keys", ui)
        self.assertIn("/control/mobile?fresh=", ui)

    def test_current_app_also_retires_stale_control_workers(self):
        app = self.read("api/control_center_app.js")
        self.assertIn("getRegistrations", app)
        self.assertIn("unregister", app)
        self.assertIn("caches.keys", app)


if __name__ == "__main__":
    unittest.main()
