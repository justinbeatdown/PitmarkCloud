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

    def test_content_publish_failures_stay_visible_and_show_platform_health(self):
        api_js = self.read("api/control_center_api.js")
        views = self.read("api/control_center_views.js")
        publish = self.read("api/social_publish.py")
        self.assertIn("/api/control/social/status", api_js)
        self.assertIn("socialPublishStatus:", api_js)
        self.assertIn("publishBlockReason", views)
        self.assertIn("Nothing was moved out of Approved & Ready.", views)
        self.assertIn("stayed Approved & Ready", views)
        self.assertIn("X publishing is paused", views)
        self.assertIn("ctx.state.contentSelection=[...keepSelected]", views)
        self.assertIn('"publishable_platforms": publishable', publish)
        self.assertIn('"blocked_platforms": blocked', publish)
        self.assertIn('code = 402 if "credits are depleted"', publish)


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
        main = self.read("main.py")
        self.assertIn("racing_standings_sync_loop", main)
        self.assertIn('name="racing-standings"', main)

    def test_standings_parser_keeps_accessible_body_rows(self):
        service = self.read("services/racing_standings.py")
        self.assertIn("def _parse_html_tables", service)
        self.assertIn('row.find_parent("thead") is not None', service)
        self.assertIn("all_header_cells", service)
        self.assertIn("Accessible standings tables often use <th scope=\"row\">", service)

    def test_standings_reader_fallback_handles_blocked_and_js_sites(self):
        service = self.read("services/racing_standings.py")
        self.assertIn("def _reader_table_rows", service)
        self.assertIn("https://r.jina.ai/http://", service)
        self.assertIn("def _parse_markdown_tables", service)
        self.assertIn("rendered fallback failed", service)
        self.assertIn("X-Return-Format", service)

    def test_public_standings_hub_and_expanded_series(self):
        service = self.read("services/racing_standings.py")
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        main = self.read("main.py")
        for token in (
            "lucas-oil-late-models",
            "high-limit-sprint",
            "usac-national-sprint",
            "usac-national-midget",
            "usac-silver-crown",
            "arca-menards",
            "cars-tour-lmsc",
            "asa-stars",
            "smart-modified",
        ):
            self.assertIn(token, service)
        self.assertIn('@router.get("/standings"', public_api)
        self.assertIn('@router.get("/api/public/standings"', public_api)
        self.assertIn("All of racing.", public_html)
        self.assertIn('data-view="{{RACE_CENTER_VIEW}}"', public_html)
        self.assertIn("seriesVisible", public_js)
        self.assertIn("standings_public.router", main)

    def test_public_standings_serve_saved_snapshots_without_remote_wait(self):
        service = self.read("services/racing_standings.py")
        public_api = self.read("api/standings_public.py")
        main = self.read("main.py")
        self.assertIn("def get_standings_snapshot_hub", service)
        self.assertIn("get_standings_snapshot_hub()", public_api)
        self.assertNotIn("get_standings_hub(force=False)", public_api)
        self.assertIn("await asyncio.sleep(interval)", main)
        self.assertIn('PITMARK_STANDINGS_SYNC_SECONDS", 14400, 1800, 43200', main)

    def test_usac_uses_column_section_parser(self):
        service = self.read("services/racing_standings.py")
        self.assertIn('def _fetch_column_sections', service)
        self.assertIn('"provider": "column_sections"', service)
        self.assertIn('"column_title": "Driver Standings"', service)
        self.assertIn('if provider == "column_sections"', service)

    def test_public_standings_v5_loads_saved_snapshot_api_without_inline_bootstrap(self):
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        self.assertIn("get_standings_snapshot_hub()", public_api)
        self.assertIn('html.replace("{{RACE_CENTER_VIEW}}", view)', public_api)
        self.assertIn("fetch('/api/public/standings", public_js)
        self.assertIn("AbortController", public_js)
        self.assertIn("bootRaceCenter", public_js)
        self.assertIn("<small>V6</small>", public_html)
        self.assertIn('class="race-pulse home-race-pulse"', public_html)
        self.assertIn('id="pulseLive"', public_html)
        self.assertIn('id="favoritesFilter"', public_html)
        self.assertIn('class="mobile-dock"', public_html)
        self.assertIn("pitmark-race-center-v5", public_js)
        self.assertIn("renderPulse", public_js)
        self.assertIn("renderMySeries", public_js)
        self.assertIn("countdownText", public_js)
        self.assertIn("data-favorite-key", public_js)
        self.assertNotIn("{{PITMARK_STANDINGS_BOOTSTRAP}}", public_html)
        self.assertNotIn("{{PITMARK_STANDINGS_INLINE_JS}}", public_html)

    def test_race_center_v5_customer_accounts_and_cloud_follows(self):
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        accounts = self.read("services/race_center_accounts.py")
        database = self.read("services/database.py")
        for route in (
            "/api/public/race-center/account",
            "/api/public/race-center/account/signup",
            "/api/public/race-center/account/login",
            "/api/public/race-center/account/logout",
            "/api/public/race-center/follows",
        ):
            self.assertIn(route, public_api)
        self.assertIn("race_center_users", accounts)
        self.assertIn("race_center_follows", accounts)
        self.assertIn("SESSION_COOKIE = \"pitmark_race_session\"", accounts)
        self.assertIn("RaceCenterFollow", accounts)
        self.assertIn("race_center_accounts  # noqa: F401", database)
        self.assertIn('id="accountButton"', public_html)
        self.assertIn('id="signupForm"', public_html)
        self.assertIn('id="loginForm"', public_html)
        self.assertIn("syncAccount", public_js)
        self.assertIn("cloudFollow", public_js)
        self.assertIn("data-driver-follow", public_js)
        self.assertIn("credentials:'same-origin'", public_js)

    def test_race_center_v5_social_infrastructure_stays_available_without_driving_home(self):
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        social_js = self.read("api/race_center_v5.js")
        accounts = self.read("services/race_center_accounts.py")
        security = self.read("utils/security.py")
        for token in (
            "race_center_profiles",
            "race_center_posts",
            "race_center_reactions",
            "race_center_comments",
            "def create_post",
            "def toggle_reaction",
            "def add_comment",
            "def list_posts",
        ):
            self.assertIn(token, accounts)
        for route in (
            "/api/public/race-center/profile",
            "/api/public/race-center/feed",
            "/reaction",
            "/comments",
            "/race-center-v5.js",
        ):
            self.assertIn(route, public_api)
        self.assertIn('id="profileForm"', public_html)
        self.assertIn('id="profileAccountType"', public_html)
        self.assertIn("/race-center-v5.js", public_html)
        self.assertIn("v5LoadFeed", social_js)
        self.assertNotIn('class="race-social"', public_html)
        self.assertNotIn('id="raceFeed"', public_html)
        self.assertNotIn('id="pitWallInput"', public_html)
        self.assertIn('"/standings", "/race-center"', security)
        self.assertIn("youtube-nocookie.com", security)

    def test_race_center_v5_people_graph_and_official_identity(self):
        accounts = self.read("services/race_center_accounts.py")
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        social_js = self.read("api/race_center_v5.js")
        css = self.read("api/standings_public.css")
        for token in (
            "race_center_identities",
            "race_center_connections",
            "def follow_user",
            "def unfollow_user",
            "def discover_people",
            "def public_profile_by_handle",
        ):
            self.assertIn(token, accounts)
        for route in (
            "/api/public/race-center/people/discover",
            "/api/public/race-center/people/{handle}",
            "/api/public/race-center/people/follow",
        ):
            self.assertIn(route, public_api)
        self.assertIn('id="peopleDialog"', public_html)
        self.assertNotIn('id="peopleDiscovery"', public_html)
        self.assertNotIn('id="peopleGrid"', public_html)
        for token in (
            "v5BroadcastGraphic",
            "broadcast-photo-card",
            "Photo:",
            "v5LoadPeople",
            "v5OpenProfile",
            "data-v5-follow-user",
            "verified-badge",
        ):
            self.assertIn(token, social_js + css)

    def test_race_center_home_restores_v1_clarity_with_v5_personalization(self):
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        css = self.read("api/standings_public.css")
        for token in (
            'id="heroTitle"',
            'id="racePulseTitle"',
            'id="mySeriesShell"',
            'id="mySeriesStrip"',
            'id="mySeriesPrev"',
            'id="mySeriesNext"',
            'id="pulseLive"',
            'id="pulseCountdown"',
            'id="pulseMoves"',
            'id="pulseFavorites"',
            'id="standingsStart"',
            'id="raceWeekend"',
            'id="leaderStrip"',
            'id="standingsBoard"',
            'id="seriesGroups"',
        ):
            self.assertIn(token, public_html)
        self.assertIn("Your racing.<br><em>One command center.</em>", public_js)
        self.assertIn("renderMySeries", public_js)
        self.assertIn("renderPulse", public_js)
        self.assertIn("bindMySeriesScroller", public_js)
        self.assertIn("refreshMySeriesScrollCue", public_js)
        self.assertIn("openSeries(chip.dataset.key)", public_js)
        self.assertIn("Drag or scroll to see all", public_js)
        self.assertIn("mySeriesPrev", public_js)
        self.assertIn("mySeriesNext", public_js)
        self.assertIn(".my-series-strip.is-scrollable", css)
        self.assertIn(".my-series-strip.is-dragging", css)
        self.assertIn("Race Center usability reset", css)
        self.assertIn('body[data-view="hub"] .home-race-pulse', css)
        self.assertIn('RACE CENTER V6 — racing-first home correction', css)
        self.assertIn('body[data-view="hub"] .race-social{display:none!important}', css)
        self.assertIn('body[data-view="hub"] .live-section,', css)
        self.assertIn('body[data-view="hub"] .leaders-section,', css)
        self.assertIn('body[data-view="hub"] .series-section{', css)
        self.assertNotIn('class="race-social"', public_html)
        self.assertNotIn('id="raceFeed"', public_html)
        self.assertIn('id="raceSearchInput"', public_html)

    def test_race_center_drivers_claims_and_public_profiles(self):
        accounts = self.read("services/race_center_accounts.py")
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        profile_html = self.read("api/race_center_profile.html")
        profile_js = self.read("api/race_center_profile.js")
        css = self.read("api/standings_public.css")
        security = self.read("utils/security.py")

        for token in (
            "race_center_profile_photos",
            "race_center_driver_claims",
            "def set_profile_photo",
            "def profile_photo_by_handle",
            "def submit_driver_claim",
            "author_user_id: int | None = None",
        ):
            self.assertIn(token, accounts)

        for token in (
            "/api/public/race-center/profile/photo",
            "/api/public/race-center/profile-photo/{handle}",
            "/api/public/race-center/profile-wall/{handle}",
            "/api/public/race-center/driver-claims",
            "/race-center/drivers",
            "/race-center/driver/{series_key}/{driver_name:path}",
            "/race-center/u/{handle}",
            "/race-center-profile.js",
        ):
            self.assertIn(token, public_api)

        for token in (
            'href="/race-center/drivers"',
            'id="driversDirectory"',
            'id="driversGrid"',
            'id="driverSearch"',
            'id="driverProfilePage"',
            'id="driverClaimDialog"',
        ):
            self.assertIn(token, public_html)

        for token in (
            "driverDirectoryRows",
            "renderDrivers",
            "renderDriverProfile",
            "photo_use_allowed===true",
            "data-driver-claim",
        ):
            self.assertIn(token, public_js)

        for token in (
            'data-profile-handle="{{PROFILE_HANDLE}}"',
            'id="publicProfileAvatar"',
            'id="profilePhotoInput"',
            'id="profileWallComposer"',
            'id="profileWallFeed"',
        ):
            self.assertIn(token, profile_html)

        for token in (
            "/api/public/race-center/profile/photo",
            "/api/public/race-center/profile-wall/",
            "/api/public/race-center/feed",
            "profileFollowButton",
            "prepareProfilePhoto",
            "createImageBitmap",
            "canvas.toBlob",
            "Preparing photo…",
        ):
            self.assertIn(token, profile_js)

        self.assertIn("Race Center readability + drivers/profile pass", css)
        self.assertIn(".drivers-grid", css)
        self.assertIn(".public-profile-hero", css)
        self.assertIn(".profile-photo-upload[hidden]", css)
        self.assertIn(".public-profile-actions [hidden]", css)
        self.assertIn('grid-template-columns:repeat(4,minmax(0,1fr))!important', css)
        self.assertIn("PROFILE_PHOTO_UPLOAD_MAX_REQUEST_BODY", security)
        self.assertIn('path == "/api/public/race-center/profile/photo"', security)

    def test_race_center_drivers_route_is_distinct_from_home(self):
        public_js = self.read("api/standings_public.js")
        public_html = self.read("api/standings_public.html")
        css = self.read("api/standings_public.css")

        self.assertIn("routePath.endsWith('/drivers')", public_js)
        self.assertIn("routePath.includes('/race-center/driver/')", public_js)
        self.assertIn("$('[data-race-view]').forEach", public_js)
        self.assertNotIn("  $('[data-race-view]').forEach", public_js)
        self.assertIn("Find a driver.<br><em>Know their racing.</em>", public_js)
        self.assertIn('data-race-view="drivers"', public_html)
        self.assertIn('body[data-view="drivers"] .drivers-directory', css)
        self.assertIn("Drivers route identity fix", css)

    def test_race_center_driver_profiles_have_real_racing_depth(self):
        public_js = self.read("api/standings_public.js")
        css = self.read("api/standings_public.css")

        for token in (
            "driverAppearances",
            "driverStandingContext",
            "driverNextRace",
            "CHAMPIONSHIP SNAPSHOT",
            "RACING ACROSS RACE CENTER",
            "RACING IDENTITY",
            "SOURCES",
            "Gap to leader",
            "Series tracked",
        ):
            self.assertIn(token, public_js)

        for token in (
            ".driver-profile-stat-grid",
            ".driver-profile-layout",
            ".driver-neighbor-list",
            ".driver-series-row",
            ".driver-identity-list",
            "Driver profile depth pass",
        ):
            self.assertIn(token, css)

    def test_race_center_driver_identity_enriches_on_demand(self):
        standings = self.read("services/racing_standings.py")
        public_api = self.read("api/standings_public.py")
        public_js = self.read("api/standings_public.js")

        self.assertIn('"carsonhocevar": {"number": "77", "team": "Spire Motorsports", "manufacturer": "Chevrolet"}', standings)
        self.assertIn("cache_scope =", standings)
        self.assertIn("def get_driver_identity(", standings)
        self.assertIn("/api/public/race-center/driver-identity/{series_key}/{driver_name:path}", public_api)
        self.assertIn("get_driver_identity(series_key, driver_name)", public_api)
        self.assertIn("function loadDriverIdentity(", public_js)
        self.assertIn("/api/public/race-center/driver-identity/", public_js)
        self.assertIn("Checking sources…", public_js)
        self.assertNotIn("primary.team||'Not verified'", public_js)
        self.assertNotIn("primary.manufacturer||'Not verified'", public_js)

    def test_race_center_standings_fail_closed_and_show_all_by_default(self):
        standings = self.read("services/racing_standings.py")
        public_js = self.read("api/standings_public.js")
        public_html = self.read("api/standings_public.html")
        css = self.read("api/standings_public.css")

        self.assertIn("def _looks_like_uniform_table_shift(", standings)
        self.assertIn("dominant_count * 10 >= matched * 6", standings)
        self.assertIn("zero_points * 10 >= dominant_count * 8", standings)
        self.assertIn("if snapshot_valid and _looks_like_uniform_table_shift(entries, previous_entries):", standings)

        self.assertIn("favoritesOnly:false", public_js)
        self.assertNotIn("favoritesOnly:Boolean(raw.favoritesOnly)", public_js)
        self.assertNotIn("favoritesOnly:state.favoritesOnly", public_js)
        self.assertIn("const standingsOnly=state.view==='standings';", public_js)
        self.assertIn("if(state.view==='standings')state.favoritesOnly=false;", public_js)

        self.assertIn("Only changes that survive Pitmark’s snapshot-integrity checks appear here.", public_html)
        self.assertIn('body:not([data-view="hub"]) .home-race-pulse', css)
        self.assertIn('body[data-view="standings"] .toolbar', css)
        self.assertIn("position:relative!important", css)
        self.assertIn("Standings integrity + layout cleanup", css)

    def test_race_center_verified_movement_requires_points_change(self):
        standings = self.read("services/racing_standings.py")
        public_js = self.read("api/standings_public.js")

        self.assertIn("movement_verified = bool(", standings)
        self.assertIn("points_delta not in (None, 0)", standings)
        self.assertIn('current["movement_verified"] = movement_verified', standings)
        self.assertIn("if(!ready)return '';", public_js)
        self.assertIn("if(!Number.isFinite(v)||v===0)return '';", public_js)
        self.assertIn("row.movement_verified===false", public_js)
        self.assertIn("if(!movement||!delta)return;", public_js)

    def test_race_center_driver_identity_uses_trusted_secondary_fallback(self):
        standings = self.read("services/racing_standings.py")
        public_js = self.read("api/standings_public.js")
        css = self.read("api/standings_public.css")

        for token in (
            "WIKIPEDIA_API_URL",
            "def _wikipedia_pick_page(",
            "def _wikipedia_infobox(",
            "def _wikipedia_driver_identity(",
            "field_sources",
            '"source_kind": source_kind',
            '"secondary_source_url": secondary.get("source_url")',
        ):
            self.assertIn(token, standings)

        self.assertIn("officialIdentity?.status==='ready'", public_js)
        self.assertIn("officialIdentity.photo_use_allowed", public_js)
        self.assertIn("Checking sources…", public_js)
        self.assertIn("ABOUT THE DRIVER", public_js)
        self.assertIn("Trusted secondary identity source", public_js)
        self.assertIn("Identity enriched from ", public_js)
        self.assertNotIn("Unavailable from official source", public_js)
        self.assertIn("Driver secondary-source enrichment", css)

    def test_race_center_series_staff_and_shared_profile_layout(self):
        accounts = self.read("services/race_center_accounts.py")
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        profile_html = self.read("api/race_center_profile.html")
        profile_js = self.read("api/race_center_profile.js")
        css = self.read("api/standings_public.css")

        for token in (
            "PITMARK_STAFF_ACCOUNTS",
            "def _pitmark_staff_identity(",
            '"staff": _pitmark_staff_identity(user.email)',
        ):
            self.assertIn(token, accounts)

        for token in (
            '@router.get("/race-center/series"',
            '@router.get("/race-center/series/{series_key}"',
            '"seriesprofile" if "/race-center/series/" in path',
            '"series" if path.endswith("/series")',
        ):
            self.assertIn(token, public_api)

        for token in (
            'data-race-view="series"',
            'id="seriesDirectory"',
            'id="seriesProfilePage"',
            'id="seriesSearch"',
            'href="/race-center/series"',
        ):
            self.assertIn(token, public_html)

        for token in (
            "function seriesDirectoryRows()",
            "function renderSeriesDirectory()",
            "function renderSeriesProfile()",
            "seriesProfileHref",
            "seriesprofile",
            "seriesSearch",
        ):
            self.assertIn(token, public_js)

        self.assertIn('id="pitmarkStaffBadge"', profile_html)
        self.assertIn('href="/race-center/series"', profile_html)
        self.assertIn("const staff=profile.staff||{};", profile_js)
        self.assertIn("staffBadge.classList.toggle('is-founder'", profile_js)

        for token in (
            ".pitmark-staff-badge",
            ".series-directory-grid",
            ".series-profile-hero",
            ".series-profile-layout",
            "Shared header, staff identity + Series destination",
        ):
            self.assertIn(token, css)

    def test_race_center_driver_identity_photos_and_account_racing_populate(self):
        standings = self.read("services/racing_standings.py")
        public_js = self.read("api/standings_public.js")
        profile_js = self.read("api/race_center_profile.js")
        css = self.read("api/standings_public.css")

        for token in (
            "wikipedia-driver-v2",
            "def _wikipedia_series_clause(",
            "def _wikipedia_identity_from_summary(",
            "def _wikipedia_page_payload(",
            "def _wikipedia_licensed_photo(",
            '"photo_use_allowed": bool(secondary.get("photo_use_allowed"))',
            '"photo_source_url": secondary.get("photo_source_url")',
            '"photo_license": secondary.get("photo_license")',
            '"Official racing source (partial)"',
        ):
            self.assertIn(token, standings)

        for token in (
            "function applyDriverIdentityToCards(",
            "function hydrateDriverDirectoryCards(",
            "data-driver-enrich-series",
            "officialIdentity.photo_use_allowed",
            "driver-photo-credit",
            "const accountFollows=state.account?.authenticated",
            "accountFollows.filter(x=>x.kind==='driver')",
            "my-racing-driver-chip",
            "Your saved series and drivers live here.",
        ):
            self.assertIn(token, public_js)

        self.assertIn('href="/race-center/series/', profile_js)
        self.assertIn('href="/race-center/driver/', profile_js)
        self.assertIn("Race Center data/photo/personalization repair", css)
        self.assertIn('body[data-view="standings"] .series-section', css)
        self.assertIn('body[data-view="driver"] .hero-actions', css)
        self.assertIn(".profile-followed-racing>a", css)
        self.assertIn("pitmark-race-center-v6-feed-20260923", public_js)
        self.assertIn("controller.abort(),20000", public_js)
        self.assertIn("Home is a racing home, not a sticky browse toolbar", css)

    def test_race_center_completion_pass_guarantees_known_nascar_identity_and_readable_staff_badge(self):
        standings = self.read("services/racing_standings.py")
        css = self.read("api/standings_public.css")
        profile_html = self.read("api/race_center_profile.html")

        for token in (
            "def _nascar_profile_url(",
            "Hard completeness floor for current NASCAR profiles",
            'NASCAR_2026_IDENTITY_FALLBACK',
            '"kylelarson": {"number": "5", "team": "Hendrick Motorsports", "manufacturer": "Chevrolet"}',
            "secondary = _wikipedia_driver_identity(config, clean_name, season)",
        ):
            self.assertIn(token, standings)

        self.assertIn("Staff badge readability completion", css)
        self.assertIn("min-width:248px!important", css)
        self.assertIn("width:112px!important", css)
        self.assertIn("race-center-complete-20260923", profile_html)

    def test_race_center_v6_finished_vision_contract(self):
        public_html = self.read("api/standings_public.html")
        public_js = self.read("api/standings_public.js")
        social_js = self.read("api/race_center_v5.js")
        v6_js = self.read("api/race_center_v6.js")
        public_api = self.read("api/standings_public.py")
        standings = self.read("services/racing_standings.py")
        accounts = self.read("services/race_center_accounts.py")
        css = self.read("api/standings_public.css")

        for token in (
            'id="raceSearchInput"',
            'id="raceSearchResults"',
            'id="racePulseTitle"',
            'id="mySeriesShell"',
            'id="raceWeekend"',
            'id="leaderStrip"',
            'id="standingsBoard"',
            '/race-center-v6.js',
            '<small>V6</small>',
        ):
            self.assertIn(token, public_html)
        self.assertNotIn('id="v5Home"', public_html)
        self.assertNotIn('id="raceFeedList"', public_html)

        for token in (
            "Pitmark Race Center — Your Racing Command Center",
            "cache:'no-store'",
            "identity_quality",
            "Not published by source",
            "Complete identity",
        ):
            self.assertIn(token, public_js)

        for token in (
            "data-driver-href",
            "profileOpen.dataset.v6Wired",
            "people-avatar has-photo",
            "pitmark-person-badge",
        ):
            self.assertIn(token, social_js)

        for token in (
            "function searchItems(",
            "function renderAccountIdentity(",
            "setInterval(enhance,10000)",
            "driverHref=String(card.dataset.driverHref",
        ):
            self.assertIn(token, v6_js)

        self.assertIn('@router.get("/race-center-v6.js"', public_api)

        for token in (
            "DRIVER_IDENTITY_RESOLVER_VERSION = 3",
            "class RaceCenterDriverIdentityCache(Base):",
            "def _driver_identity_cache_get(",
            "def _driver_identity_cache_set(",
            '"identity_quality":',
        ):
            self.assertIn(token, standings)

        self.assertIn('"photo_url": f"/api/public/race-center/profile-photo/{profile.handle}"', accounts)
        self.assertIn('"staff": _pitmark_staff_identity(user.email if user else "")', accounts)

        for token in (
            "RACE CENTER V6 — finished product shell",
            "RACE CENTER V6 — racing-first home correction",
            "body[data-view=\"hub\"] .race-social{display:none!important}",
            ".race-search-results",
            ".social-staff-badge",
            ".driver-identity-status.complete",
            ".people-avatar.has-photo",
        ):
            self.assertIn(token, css)

    def test_race_center_v6_saved_snapshot_hydrates_persistent_driver_identity(self):
        standings = self.read("services/racing_standings.py")
        for token in (
            "def _hydrate_saved_identity(",
            "RaceCenterDriverIdentityCache.series_key == series_key",
            "NASCAR_2026_IDENTITY_FALLBACK.get(series_key",
            "cache_row.photo_use_allowed",
            '"entries": _hydrate_saved_identity(',
        ):
            self.assertIn(token, standings)

    def test_race_center_home_board_is_not_hidden_by_legacy_social_css(self):
        css = self.read("api/standings_public.css")
        self.assertNotIn(
            'body[data-view="hub"] .content-section:not(.social-feed-card){display:none!important}',
            css,
        )
        self.assertIn('body[data-view="hub"] .live-section,', css)
        self.assertIn('body[data-view="hub"] .leaders-section,', css)
        self.assertIn('body[data-view="hub"] .series-section{', css)
        self.assertIn('display:block!important', css)

    def test_race_center_identity_type_is_owned_but_verification_is_not(self):
        accounts = self.read("services/race_center_accounts.py")
        public_api = self.read("api/standings_public.py")
        public_html = self.read("api/standings_public.html")
        social_js = self.read("api/race_center_v5.js")
        self.assertIn("ALLOWED_ACCOUNT_TYPES", accounts)
        self.assertIn('account_type: str = Field(default="fan"', public_api)
        self.assertIn("account_type=body.account_type", public_api)
        self.assertIn('id="profileAccountType"', public_html)
        self.assertIn("v5AccountTypeLabel", social_js)
        self.assertNotIn("verification_status=body", public_api)
        self.assertNotIn("official_label=body", public_api)

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
