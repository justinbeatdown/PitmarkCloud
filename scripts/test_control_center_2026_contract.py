from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ControlCenter2026Contract(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_prt_ops_api_exists_and_exposes_required_routes(self):
        text = self.read("api/control_center_2026.py")
        for route in (
            "/api/control/ops/overview",
            "/api/control/ops/testers",
            "/api/control/ops/founders-race",
            "/api/control/ops/feedback",
            "/api/control/ops/testers/{application_id}/status",
            "/api/control/ops/feedback/{feedback_id}/status",
        ):
            self.assertIn(route, text)
        self.assertIn("require_control_user", text)
        self.assertIn("leaderboard", text)
        self.assertIn("list_applications", text)
        self.assertIn("list_early_access_invites", text)
        self.assertIn("list_feedback", text)
        init_text = self.read("api/__init__.py")
        self.assertIn("control_center_2026", init_text)
        self.assertIn("include_router(control_center_2026.router)", init_text)

    def test_desktop_and_mobile_share_the_2026_bundle(self):
        for filename in ("api/control_center.html", "api/control_mobile.html"):
            text = self.read(filename)
            self.assertIn('id="pm26-root"', text)
            self.assertIn("/control-center-overhaul.css", text)
            self.assertIn("/control-center-overhaul.js", text)
            self.assertNotIn('src="/control.js"', text)
            self.assertNotIn('src="/control-mobile.js', text)

    def test_shell_has_all_operating_areas_and_deep_links(self):
        html = self.read("api/control_center.html")
        for view in ("home", "prt", "content", "comms", "relationships", "systems"):
            self.assertIn(f'data-pm26-nav="{view}"', html)
        self.assertIn("/control/early-access", html)
        self.assertIn("/control/founders-race", html)

    def test_css_is_responsive_accessible_and_isolated(self):
        css = self.read("api/control_center_overhaul.css")
        self.assertIn("#pm26-root", css)
        self.assertIn("env(safe-area-inset-bottom)", css)
        self.assertRegex(css, r"@media\s*\(max-width:\s*8[0-9]{2}px\)")
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height: 44px", css)

    def test_js_uses_real_control_center_endpoints(self):
        js = self.read("api/control_center_overhaul.js")
        for endpoint in (
            "/api/control/ops/overview",
            "/api/control/ops/testers",
            "/api/control/ops/founders-race",
            "/api/control/ops/feedback",
            "/api/control/status",
            "/api/control/brief",
            "/api/control/notifications",
            "/api/control/autopilot/posts",
            "/api/control/blog/drafts",
            "/api/control/email/threads",
            "/api/control/outreach",
            "/api/control/auth/logout",
        ):
            self.assertIn(endpoint, js)
        self.assertIn("window.addEventListener('load'", js)


if __name__ == "__main__":
    unittest.main()
