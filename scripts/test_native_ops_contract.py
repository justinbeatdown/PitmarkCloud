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
        self.assertNotIn("native_analytics_suite", hq)
        hq_overview = hq.split('@router.get("/api/control/hq/overview")', 1)[1]
        hq_overview = hq_overview.split('@router.', 1)[0]
        self.assertNotIn("business_intelligence", hq_overview)
        self.assertNotIn("native", hq_overview)

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

    def test_intelligence_has_bounded_wait(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("ThreadPoolExecutor", service)
        self.assertIn("timeout=12.0", service)

    def test_shopify_paginates(self):
        service = (ROOT / "services" / "business_intelligence.py").read_text(encoding="utf-8")
        self.assertIn("pageInfo { hasNextPage endCursor }", service)
        self.assertIn('orders(first: 100, after: $after', service)
        self.assertIn('after = str(page_info.get("endCursor")', service)


if __name__ == "__main__":
    unittest.main()
