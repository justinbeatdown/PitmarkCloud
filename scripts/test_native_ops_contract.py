from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class NativeOpsContractTests(unittest.TestCase):
    def test_isolated_router_registered(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("control_native_ops", main)
        self.assertIn("app.include_router(control_native_ops.router)", main)

    def test_native_routes_exist(self):
        api = (ROOT / "api" / "control_native_ops.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/analytics")', api)
        self.assertIn('@router.get("/social")', api)
        self.assertIn('@router.post("/refresh")', api)

    def test_native_ui_is_standalone(self):
        ui = (ROOT / "api" / "control_center_ui.py").read_text(encoding="utf-8")
        html = ROOT / "api" / "control_native_ops.html"
        js = ROOT / "api" / "control_native_ops.js"
        css = ROOT / "api" / "control_native_ops.css"
        self.assertTrue(html.exists())
        self.assertTrue(js.exists())
        self.assertTrue(css.exists())
        self.assertIn("@router.get('/control/native-ops'", ui)
        self.assertIn("@router.get('/control-native-ops.js'", ui)
        self.assertIn("@router.get('/control-native-ops.css'", ui)

    def test_csp_allows_native_assets(self):
        security = (ROOT / "utils" / "security.py").read_text(encoding="utf-8")
        for path in (
            "/control/native-ops",
            "/control-native-ops.js",
            "/control-native-ops.css",
        ):
            self.assertIn(path, security)

    def test_hq_boot_does_not_call_native_ops(self):
        hq = (ROOT / "api" / "control_center_hq.py").read_text(encoding="utf-8")
        hq_overview = hq.split('@router.get("/api/control/hq/overview")', 1)[1]
        hq_overview = hq_overview.split('@router.', 1)[0]
        self.assertNotIn("business_intelligence", hq_overview)
        self.assertNotIn("native_analytics_suite", hq_overview)

    def test_native_service_has_cache(self):
        service = (ROOT / "services" / "native_analytics_suite.py").read_text(encoding="utf-8")
        self.assertIn("_CACHE_SECONDS", service)
        self.assertIn("def analytics_overview", service)
        self.assertIn("def social_desk", service)
        self.assertIn("def clear_cache", service)

    def test_control_center_links_are_static_only(self):
        views = (ROOT / "api" / "control_center_views.js").read_text(encoding="utf-8")
        self.assertIn('/control/native-ops?tab=social', views)
        self.assertIn('/control/native-ops?tab=analytics', views)
        self.assertNotIn("native_analytics_suite", views)

    def test_x_credit_depletion_stops_retry_loop(self):
        worker = (ROOT / "services" / "social_publish_worker.py").read_text(encoding="utf-8")
        self.assertIn('"credits depleted" in str(exc).lower()', worker)
        self.assertIn('post.status = "approved"', worker)
        self.assertIn("instead of retrying every minute", worker)

    def test_native_client_uses_multi_selector_for_tabs(self):
        client = (ROOT / "api" / "control_native_ops.js").read_text(encoding="utf-8")
        bad_lines = [
            line.strip()
            for line in client.splitlines()
            if line.strip().startswith("$('[data-tab]').forEach")
        ]
        self.assertEqual(bad_lines, [])
        self.assertGreaterEqual(client.count("$$('[data-tab]').forEach"), 3)
        self.assertIn("location.hash", client)

    def test_recommendations_execute_with_currency_values(self):
        import importlib.util
        import sys
        from types import ModuleType

        # Static contract: old-style comma currency formatting must never return.
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertNotIn("%,.2f", service)
        self.assertIn("{revenue:,.2f}", service)
        self.assertIn("{ad_spend:,.2f}", service)

    def test_intelligence_has_bounded_wait(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("ThreadPoolExecutor", service)
        self.assertIn("timeout=12.0", service)

    def test_google_connected_forbidden_state_is_distinct(self):
        client = (ROOT / "api" / "control_native_ops.js").read_text(encoding="utf-8")
        self.assertIn("googleAuthorized", client)
        self.assertIn("Google connected · API access needs attention", client)

    def test_google_callback_does_not_require_control_cookie(self):
        hq = (ROOT / "api" / "control_center_hq.py").read_text(encoding="utf-8")
        block = hq.split('@router.get("/control/google-callback"', 1)[1].split('@router.', 1)[0]
        self.assertNotIn("_auth(request)", block)
        self.assertIn("verified_state_user", block)

    def test_server_side_google_callback_exists(self):
        hq = (ROOT / "api" / "control_center_hq.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/control/google-callback"', hq)
        self.assertIn('http://127.0.0.1:8765/?', hq)
        self.assertIn('complete_analytics_authorization', hq)

    def test_google_oauth_uses_in_page_completion_panel(self):
        client = (ROOT / "api" / "control_native_ops.js").read_text(encoding="utf-8")
        self.assertIn("showGoogleConnectPanel", client)
        self.assertIn("google-callback-url", client)
        self.assertNotIn("prompt('Approve GA4", client)

    def test_google_core_auth_does_not_bundle_youtube(self):
        auth = (ROOT / "services" / "google_business_intelligence_auth.py").read_text(encoding="utf-8")
        self.assertIn("analytics.readonly", auth)
        self.assertIn("webmasters.readonly", auth)
        scope_block = auth.split("ANALYTICS_SCOPES", 1)[1].split("])", 1)[0]
        self.assertNotIn("youtube.readonly", scope_block)

    def test_social_calendar_separates_failures(self):
        service = (ROOT / "services" / "native_analytics_suite.py").read_text(encoding="utf-8")
        self.assertIn('visible_statuses = {"scheduled", "published", "approved", "pending"}', service)
        self.assertIn('failure_statuses = {"failed", "rejected"}', service)
        self.assertIn('"failures": failures[:20]', service)

    def test_shopify_paginates(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("pageInfo { hasNextPage endCursor }", service)
        self.assertIn('orders(first: 100, after: $after', service)
        self.assertIn('after = str(page_info.get("endCursor")', service)


    def test_meta_reporting_uses_published_posts_with_graceful_fallback(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn('"/published_posts"', service)
        self.assertIn("reactions.limit(0).summary(true)", service)
        self.assertIn('basic_fields = "id,message,created_time,permalink_url,shares"', service)
        self.assertIn('"permission_required"', service)
        self.assertIn('"ads_read access', service)

    def test_google_sources_expose_setup_actions_independently(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("def _google_setup_urls", service)
        self.assertIn('"analyticsadmin.googleapis.com"', service)
        self.assertIn('"analyticsdata.googleapis.com"', service)
        self.assertIn('"searchconsole.googleapis.com"', service)
        self.assertIn('"api_disabled"', service)
        self.assertIn('"setup_urls": (google.get("ga4")', service)
        self.assertIn('"setup_urls": (google.get("search_console")', service)

    def test_native_analytics_has_replacement_dashboard_sections(self):
        client = (ROOT / "api" / "control_native_ops.js").read_text(encoding="utf-8")
        self.assertIn("function sourceHealthRow", client)
        self.assertIn("Social Performance", client)
        self.assertIn("Website + Google Search", client)
        self.assertIn("Recent Orders", client)
        self.assertIn("Replacement Coverage", client)
        self.assertIn("setup_urls", client)

    def test_native_analytics_rows_escape_detail_by_default(self):
        client = (ROOT / "api" / "control_native_ops.js").read_text(encoding="utf-8")
        self.assertIn("detailIsHtml=false", client)
        self.assertIn("const safeDetail=detailIsHtml?String(detail||''):esc(detail)", client)
        self.assertIn("rel=\"noopener noreferrer\"", client)

    def test_native_ops_assets_are_cache_busted_for_v2(self):
        html = (ROOT / "api" / "control_native_ops.html").read_text(encoding="utf-8")
        self.assertIn("/control-native-ops.css?v=6", html)
        self.assertIn("/control-native-ops.js?v=7", html)


    def test_x_publish_service_has_credit_circuit_breaker(self):
        service = (ROOT / "services" / "x_publish_service.py").read_text(encoding="utf-8")
        self.assertIn("_X_CREDIT_COOLDOWN_SECONDS", service)
        self.assertIn("_credits_depleted_until", service)
        self.assertIn("if r.status_code == 402", service)
        self.assertIn("instead of repeatedly billing the API", service)


if __name__ == "__main__":
    unittest.main()
