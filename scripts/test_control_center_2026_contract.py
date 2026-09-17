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

    def test_hq_api_uses_master_checklist_without_shadow_task_model(self):
        text = self.read("api/control_center_hq.py")
        for route in (
            "/api/control/hq/overview",
            "/api/control/work",
            "/api/control/work/{row_number}",
            "/api/control/search",
        ):
            self.assertIn(route, text)
        self.assertIn("require_control_user", text)
        self.assertIn("services.master_checklist", text)
        self.assertIn("list_items", text)
        self.assertIn("update_item", text)
        self.assertNotRegex(text, r"class\s+(Task|ChecklistItem)\s*\(")
        init_text = self.read("api/__init__.py")
        self.assertIn("control_center_hq", init_text)
        self.assertIn("include_router(control_center_hq.router)", init_text)

    def test_authenticated_desktop_and_mobile_use_one_shell(self):
        html = self.read("api/control_center.html")
        ui = self.read("api/control_center_ui.py")
        self.assertIn('id="pitmark-control"', html)
        self.assertIn("/control-center-overhaul.css", html)
        self.assertIn("/control-center-app.js", html)
        self.assertIn("type=\"module\"", html)
        self.assertIn("filename = 'control_center.html' if user_from_request(request) else 'control_mobile_login.html'", ui)

    def test_current_hq_module_graph_is_served(self):
        assets = self.read("api/control_center_assets.py")
        expected_routes = {
            "/control-center-app.js": "control_center_app.js",
            "/control-center-api.js": "control_center_api.js",
            "/control-center-views.js": "control_center_views.js",
        }
        for route, filename in expected_routes.items():
            self.assertIn(f'@router.get("{route}"', assets)
            self.assertIn(f'return _javascript("{filename}")', assets)

        init_text = self.read("api/__init__.py")
        self.assertIn("control_center_assets", init_text)
        self.assertIn("include_router(control_center_assets.router)", init_text)

        app_js = self.read("api/control_center_app.js")
        self.assertIn("'./control-center-api.js'", app_js)
        self.assertIn("'./control-center-views.js'", app_js)

    def test_shell_has_current_operating_domains_and_no_email_or_finance_product(self):
        html = self.read("api/control_center.html")
        for domain in (
            "hq",
            "work",
            "prt",
            "partnerships",
            "content",
            "store",
            "people",
            "systems",
            "insights",
        ):
            self.assertIn(f'data-domain="{domain}"', html)
        self.assertIn('id="global-command"', html)
        self.assertIn('id="mobile-nav"', html)
        self.assertIn('id="detail-sheet"', html)
        self.assertNotRegex(html, r">\s*(Comms|Email|Inbox|Mail)\s*<")
        self.assertNotRegex(html, r">\s*(Finance|Banking|Transactions|Budget)\s*<")

    def test_css_is_responsive_accessible_and_tokenized(self):
        css = self.read("api/control_center_overhaul.css")
        self.assertIn(".pm-app", css)
        self.assertIn(":root", css)
        self.assertIn("--pm-orange", css)
        self.assertIn("env(safe-area-inset-bottom)", css)
        self.assertRegex(css, r"@media\s*\(max-width:\s*8[0-9]{2}px\)")
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height:44px", css.replace(" ", ""))

    def test_new_module_client_uses_real_control_center_endpoints(self):
        api_js = self.read("api/control_center_api.js")
        for endpoint in (
            "/api/control/hq/overview",
            "/api/control/work",
            "/api/control/search",
            "/api/control/ops/overview",
            "/api/control/ops/testers",
            "/api/control/ops/founders-race",
            "/api/control/ops/feedback",
            "/api/control/autopilot/posts",
            "/api/control/autopilot/composer/generate",
            "/api/control/blog/drafts",
            "/api/control/outreach",
            "/api/control/status",
            "/api/control/brief",
            "/api/control/notifications",
            "/api/control/auth/logout",
        ):
            self.assertIn(endpoint, api_js)
        self.assertNotIn("/api/control/email/threads", api_js)
        app_js = self.read("api/control_center_app.js")
        self.assertIn("addEventListener", app_js)
        self.assertIn("AbortController", api_js)

    def test_hq_boot_does_not_self_abort(self):
        api_js = self.read("api/control_center_api.js")
        hq_line = next(line for line in api_js.splitlines() if line.strip().startswith("hq: (options"))
        self.assertNotIn("scope: 'hq'", hq_line)
        app_js = self.read("api/control_center_app.js")
        self.assertIn("renderCurrent(false);", app_js)
        self.assertIn("bootstrapStatus();", app_js)

    def test_hq_degrades_gracefully_when_master_checklist_is_offline(self):
        views = self.read("api/control_center_views.js")
        self.assertIn("const workConnected = modules.work?.ok === true;", views)
        self.assertIn("Checklist unavailable", views)
        self.assertIn("workConnected ? panel('Needs Attention'", views)
        self.assertNotIn("Work source needs attention.", views)
        self.assertNotIn("Checklist disconnected</span>", views)

    def test_authenticated_routes_do_not_inject_legacy_bundles(self):
        ui = self.read("api/control_center_ui.py")
        legacy_assets = (
            '/control.js',
            '/control-mobile.js',
            'control-center-v19',
            'control-center-v191',
            'control-center-v195',
            'control-center-v201',
            'control-center-v202',
            'control-runtime-v194',
            'control-mail-client',
            'control-email.js',
        )
        route_source = ui.split("@router.get('/control'", 1)[1].split("@router.get('/control/mobile'", 1)[0]
        mobile_source = ui.split("@router.get('/control/mobile'", 1)[1].split("def _text_asset", 1)[0]
        for asset in legacy_assets:
            self.assertNotIn(asset, route_source)
            self.assertNotIn(asset, mobile_source)
        self.assertIn("filename = 'control_center.html' if user_from_request(request) else 'control_login.html'", route_source)
        self.assertIn("filename = 'control_center.html' if user_from_request(request) else 'control_mobile_login.html'", mobile_source)


if __name__ == "__main__":
    unittest.main()
