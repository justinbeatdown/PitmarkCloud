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
        self.assertIn("/control-reset", sw)
        self.assertNotIn("control-mobile.js", sw)
        self.assertNotIn("control-mobile-blog.js", sw)
        self.assertNotIn("pitmark-mobile-v0.21.42", sw)

    def test_recovery_route_is_direct_server_redirect(self):
        recovery = self.read("api/control_center_recovery.py")
        self.assertIn("@router.get('/control-reset'", recovery)
        self.assertIn("RedirectResponse", recovery)
        self.assertIn("status_code=302", recovery)
        self.assertIn("/control/mobile?fresh=", recovery)
        self.assertNotIn("<script>", recovery)
        self.assertNotIn("HTMLResponse", recovery)

        init_text = self.read("api/__init__.py")
        self.assertIn("control_center_recovery", init_text)
        self.assertIn("include_router(control_center_recovery.router)", init_text)


if __name__ == "__main__":
    unittest.main()
