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

    def test_no_shield_queue_exposure(self):
        html = (ROOT / "api/control_next.html").read_text(encoding="utf-8")
        self.assertNotIn('data-view="shield"', html.lower())
        self.assertNotIn('id="shield"', html.lower())


if __name__ == "__main__":
    unittest.main()
