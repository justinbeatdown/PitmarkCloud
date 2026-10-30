"""Static contracts for Control Center 2.0's isolated owner experience."""
from pathlib import Path
import ast
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OwnerHQContracts(unittest.TestCase):
    def test_python_compiles(self):
        for name in ("api/control_center_next.py", "api/control_center_ui.py"):
            ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)

    def test_javascript_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not installed")
        subprocess.run([node, "--check", str(ROOT / "api/control_next.js")], check=True)
        subprocess.run([node, "--check", str(ROOT / "api/control_next_modules.js")], check=True)

    def test_owner_route_and_classic_fallback(self):
        source = (ROOT / "api/control_center_ui.py").read_text(encoding="utf-8")
        self.assertIn("return _guarded_html('control_next.html', guard=True)", source)
        self.assertIn("@router.get('/control/classic'", source)
        self.assertIn("return _guarded_html('control_center.html', guard=True)", source)
        self.assertIn("router.include_router(owner_hq_router)", source)

    def test_owner_api_authenticated_and_read_first(self):
        source = (ROOT / "api/control_center_next.py").read_text(encoding="utf-8")
        self.assertIn('require_control_user(request, None)', source)
        self.assertIn('@router.get("/api/control/hq/v2")', source)
        self.assertIn('@router.post("/api/control/hq/v2/visit")', source)
        self.assertIn("MAX_EVENTS = 60", source)
        self.assertIn("MAX_ACTIONS = 45", source)
        self.assertIn("Internal operations data unavailable", source)
        self.assertNotIn("publish_post(", source)
        self.assertNotIn("send_message(", source)

    def test_no_external_providers_on_critical_path(self):
        source = (ROOT / "api/control_center_next.py").read_text(encoding="utf-8")
        self.assertNotIn("list_items(", source)
        self.assertNotIn("httpx.", source)
        self.assertNotIn("shopify_service.", source)
        self.assertIn("SessionLocal()", source)

    def test_source_provenance_and_unavailable_states(self):
        js = (ROOT / "api/control_next.js").read_text(encoding="utf-8")
        self.assertIn("Unavailable does not mean zero", js)
        self.assertIn("Local operations connected", js)
        self.assertIn("Reconcile provider status", (ROOT / "api/control_center_next.py").read_text(encoding="utf-8"))
        self.assertIn("new URL(s)", js)
        self.assertIn("escapeText", js)

    def test_owner_mobile_and_brand(self):
        css = (ROOT / "api/control_next.css").read_text(encoding="utf-8")
        html = (ROOT / "api/control_next.html").read_text(encoding="utf-8")
        self.assertIn("#ff5500", css)
        self.assertIn("@media(max-width:530px)", css)
        self.assertIn('src="/control-logo-badge.png"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-live="polite"', html)

    def test_full_overhaul_workspace_navigation(self):
        html = (ROOT / "api/control_next.html").read_text(encoding="utf-8")
        js = (ROOT / "api/control_next.js").read_text(encoding="utf-8")
        module = (ROOT / "api/control_next_modules.js").read_text(encoding="utf-8")
        api = (ROOT / "api/control_center_next.py").read_text(encoding="utf-8")
        for name in ("inbox", "mail", "content", "relationships", "prt", "work", "racing", "store", "growth", "systems"):
            self.assertIn(f'data-view="{name}"', html)
        self.assertIn("mountWorkspace(view,root", module)
        self.assertIn("WORKSPACE_VIEWS.has(view)", js)
        self.assertIn('"/api/control/hq/v2/records/{kind}"', api)
        self.assertIn("limit: int = Query(default=35", api)
        self.assertIn("const ttl=new Map()", module)
        self.assertIn("inflight=new Map()", module)
        self.assertIn("'mail-form'", module)
        self.assertIn("'contact-form'", module)
        self.assertIn("'post-form'", module)
        self.assertNotIn("'/control/classic#content'", js)
        self.assertNotIn('href="/control/classic#content"', html)

    def test_mobile_canonical_route_and_css(self):
        html = (ROOT / "api/control_next.html").read_text(encoding="utf-8")
        ui = (ROOT / "api/control_center_ui.py").read_text(encoding="utf-8")
        css = (ROOT / "api/control_next.css").read_text(encoding="utf-8")
        self.assertIn('id="mobile-dim"', html)
        self.assertIn("return RedirectResponse(", ui)
        self.assertIn("url='/control'", ui)
        self.assertIn("control_next_modules_js", ui)
        self.assertIn("@media(max-width:530px)", css)
        self.assertIn("font:800 clamp(30px", css)
        self.assertNotIn("'Barlow Condensed'", css)
        self.assertNotIn("Impact,sans-serif", css)

    def test_no_shield_queue_exposure(self):
        html = (ROOT / "api/control_next.html").read_text(encoding="utf-8")
        self.assertNotIn('data-view="shield"', html.lower())
        self.assertNotIn('id="shield"', html.lower())


if __name__ == "__main__":
    unittest.main()
