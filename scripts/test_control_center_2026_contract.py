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
        self.assertIn("RedirectResponse", ui)
        self.assertIn("/control-reset?source=mobile-retired-20260918", ui)
        self.assertIn("control_mobile_login.html", ui)

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
        self.assertRegex(app_js, r"['\"]\./control-center-api\.js(?:\?[^'\"]+)?['\"]")
        self.assertRegex(app_js, r"['\"]\./control-center-views\.js(?:\?[^'\"]+)?['\"]")

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
            "standings",
        ):
            self.assertIn(f'data-domain="{domain}"', html)
        self.assertIn('id="global-command"', html)
        self.assertIn('id="mobile-nav"', html)
        self.assertIn('id="mobile-page-title"', html)
        self.assertIn('id="mobile-page-kicker"', html)
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
            "/api/control/social/posts",
            "/api/control/social/assets/generate",
            "/api/control/autopilot/composer/generate",
            "/api/control/blog/drafts",
            "/api/control/outreach",
            "/api/control/status",
            "/api/control/brief",
            "/api/control/notifications",
            "/api/control/workspace/status",
            "/api/control/workspace/oauth/start",
            "/api/control/workspace/oauth/complete",
            "/api/control/auth/logout",
            "/api/control/standings",
            "/api/control/standings/refresh",
        ):
            self.assertIn(endpoint, api_js)
        self.assertNotIn("/api/control/email/threads", api_js)
        app_js = self.read("api/control_center_app.js")
        self.assertIn("addEventListener", app_js)
        self.assertIn("AbortController", api_js)

    def test_content_supports_bulk_select_edit_approve_publish_and_delete(self):
        api_py = self.read("api/control_center.py")
        self.assertIn("@router.delete('/autopilot/posts/{post_id}')", api_py)
        self.assertIn("platform: str | None = None", api_py)
        api_js = self.read("api/control_center_api.js")
        self.assertIn("deletePost:", api_js)
        views = self.read("api/control_center_views.js")
        for token in (
            "data-post-select",
            "data-select-all",
            'data-bulk-action="edit"',
            'data-bulk-action="approve"',
            'data-bulk-action="publish"',
            'data-bulk-action="delete"',
            "openBulkEdit",
            "runBulk",
        ):
            self.assertIn(token, views)
        css = self.read("api/control_center_overhaul.css")
        self.assertIn(".pm-bulk-bar", css)
        self.assertIn(".pm-content-check", css)

    def test_systems_can_connect_google_sheets(self):
        views = self.read("api/control_center_views.js")
        api_js = self.read("api/control_center_api.js")
        self.assertIn("Connect Google Sheets", views)
        self.assertIn("openWorkspaceConnect", views)
        self.assertIn("workspaceOAuthStart", views)
        self.assertIn("workspaceOAuthComplete", views)
        self.assertIn("Google Sheets connected. Master Checklist is live.", views)
        self.assertIn("workspaceStatus:", api_js)
        self.assertIn("workspaceOAuthStart:", api_js)
        self.assertIn("workspaceOAuthComplete:", api_js)

    def test_systems_render_human_readable_brief_and_non_mail_signals(self):
        views = self.read("api/control_center_views.js")
        notifications = self.read("services/notification_engine.py")
        self.assertIn("renderCommandBrief", views)
        self.assertIn("notificationPayload?.items", views)
        self.assertIn("No current operational signals.", views)
        self.assertNotIn("JSON.stringify(brief)", views)
        self.assertIn("_control_center_visible", notifications)
        self.assertIn('"shield", "mail", "gmail", "email"', notifications)
        self.assertIn("Control Center is not an inbox", notifications)

    def test_owner_community_posts_skip_approval_but_manual_authority_stays_gated(self):
        api_py = self.read("api/control_center.py")
        worker = self.read("services/social_publish_worker.py")
        views = self.read("api/control_center_views.js")
        self.assertIn('content_type == "community"', api_py)
        self.assertIn('source = "control_center:auto"', api_py)
        self.assertIn('status = "scheduled"', api_py)
        self.assertIn('raw == "control_center:auto"', worker)
        self.assertIn("Community post saved into the automatic scheduling lane.", views)
        self.assertIn('status = "pending"', api_py)

    def test_content_can_generate_and_attach_publish_safe_media(self):
        api_js = self.read("api/control_center_api.js")
        views = self.read("api/control_center_views.js")
        publish = self.read("api/social_publish.py")
        self.assertIn("/api/control/social/assets/generate", api_js)
        self.assertIn("generateSocialImage:", api_js)
        self.assertIn("Generate image", views)
        self.assertIn("image/jpeg", publish)
        self.assertIn('format="JPEG"', publish)

    def test_prt_acceptance_is_complete_onboarding_action(self):
        ops = self.read("api/control_center_2026.py")
        views = self.read("api/control_center_views.js")
        self.assertIn("create_early_access_invite", ops)
        self.assertIn("_acceptance_message", ops)
        self.assertIn("onboarding_sent", ops)
        self.assertIn("Early Access code + onboarding email sent", views)

    def test_content_approved_posts_can_publish_live(self):
        api_js = self.read("api/control_center_api.js")
        self.assertIn("/api/control/social/posts", api_js)
        self.assertIn("publishPost:", api_js)
        views = self.read("api/control_center_views.js")
        self.assertIn("'approved'", views)
        self.assertIn("Publish Now", views)
        self.assertIn("api.publishPost", views)
        self.assertIn("Post approved — ready to publish.", views)
        self.assertIn("ctx.state.contentTab='published'", views)

    def test_legacy_mobile_mail_shell_is_retired(self):
        legacy_html = self.read("api/control_mobile.html")
        legacy_js = self.read("api/control_center_overhaul.js")
        self.assertIn("/control-reset?source=legacy-template", legacy_html)
        self.assertNotIn("Pitmark Mail", legacy_html)
        self.assertNotIn("data-pm26-nav=\"comms\"", legacy_html)
        self.assertIn("/control-reset?source=legacy-ui", legacy_js)

    def test_hq_stays_actionable_without_checklist(self):
        views = self.read("api/control_center_views.js")
        self.assertIn("Operator Queue", views)
        self.assertIn("What Needs You", views)
        self.assertIn("Recent Signals", views)
        self.assertIn("Quick Access", views)
        self.assertIn('data-go="prt"', views)
        self.assertIn('data-go="content"', views)
        css = self.read("api/control_center_overhaul.css")
        self.assertIn(".pm-quick-grid", css)
        app_js = self.read("api/control_center_app.js")
        self.assertIn("mobilePageTitle", app_js)
        self.assertIn("mobilePageKicker", app_js)

    def test_hq_surfaces_racing_command_brief_and_content_actions(self):
        views = self.read("api/control_center_views.js")
        api_js = self.read("api/control_center_api.js")
        for token in (
            "Racing opportunities",
            "Racing Intelligence",
            "data-op-content",
            "data-op-research",
            "data-op-scan",
            "Make Content",
            "Research More",
            "Open article",
        ):
            self.assertIn(token, views)
        for endpoint in (
            "/api/control/autopilot/opportunities",
            "/api/control/autopilot/intelligence/run",
            "/api/control/community/research/prepare",
        ):
            self.assertIn(endpoint, api_js)
        self.assertIn("prepareOpportunityResearch:", api_js)
        self.assertIn("runIntelligence:", api_js)

    def test_racing_standings_hub_tracks_major_series_and_snapshots(self):
        service = self.read("services/racing_standings.py")
        views = self.read("api/control_center_views.js")
        api_js = self.read("api/control_center_api.js")
        api_py = self.read("api/control_center.py")
        html = self.read("api/control_center.html")
        for token in (
            "nascar-cup",
            "nascar-oreilly",
            "nascar-truck",
            "world-of-outlaws-sprint",
            "world-of-outlaws-late-models",
            "nhra-top-fuel",
            "nhra-funny-car",
            "nhra-pro-stock",
            "nhra-pro-stock-motorcycle",
            '"key": "f1"',
            '"key": "indycar"',
            '"key": "formula-e"',
            "imsa-weathertech",
            '"key": "wec"',
            '"key": "supercars"',
            '"key": "motogp"',
        ):
            self.assertIn(token, service)
        self.assertIn("class RacingStandingSnapshot", service)
        self.assertIn("movement", service)
        self.assertIn("official_table", service)
        self.assertIn("@router.get('/standings')", api_py)
        self.assertIn("@router.post('/standings/refresh')", api_py)
        self.assertIn("standings:", api_js)
        self.assertIn("refreshStandings:", api_js)
        self.assertIn("Standings Hub", views)
        self.assertIn("Full standings", views)
        self.assertIn("CHAMPIONSHIP LEADERS", views)
        self.assertIn('data-domain="standings"', html)

    def test_control_center_readability_scale_covers_tiny_ui_text(self):
        css = self.read("api/control_center_overhaul.css")
        self.assertIn("Readability pass — 2026-09-20", css)
        for token in (
            ".pm-button{font-size:12px}",
            ".pm-row-actions .pm-button{min-height:36px;padding:0 10px;font-size:11px}",
            ".pm-row-main strong{font-size:13px}",
            ".pm-row-main p{font-size:11px",
            ".pm-badge{min-height:22px;font-size:9px}",
            ".pm-table td strong{font-size:12px}",
            ".pm-table td small{font-size:10px}",
        ):
            self.assertIn(token, css)

    def test_operating_tables_stack_cleanly_on_mobile(self):
        views = self.read("api/control_center_views.js")
        self.assertIn('data-label="Applicant"', views)
        self.assertIn('data-label="Tester state"', views)
        self.assertIn('data-label="Milestone"', views)
        self.assertIn('data-label="Next follow-up"', views)
        css = self.read("api/control_center_overhaul.css")
        self.assertIn("content:attr(data-label)", css)
        self.assertIn(".pm-table thead{display:none}", css)
        self.assertIn(".pm-table tbody{display:grid;gap:9px}", css)

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
        self.assertIn("workConnected && attention.length", views)
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
        self.assertIn("/control-reset?source=mobile-retired-20260918", mobile_source)
        self.assertIn("control_mobile_login.html", mobile_source)


if __name__ == "__main__":
    unittest.main()
