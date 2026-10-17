"""Ensure PRT pairing UI works under Race Center's strict public-page CSP."""
from pathlib import Path
import ast
import re

root = Path(__file__).resolve().parents[1]
module = (root / "api" / "prt_race_center_bridge.py").read_text(encoding="utf8")
javascript = (root / "api" / "prt_connect.js").read_text(encoding="utf8")
css = (root / "api" / "prt_connect.css").read_text(encoding="utf8")
policy = (root / "utils" / "security.py").read_text(encoding="utf8")

ast.parse(module)
assert '@router.get("/race-center/prt-connect"' in module
assert '@router.get("/prt-connect.css"' in module
assert '@router.get("/prt-connect.js"' in module
assert 'href="/prt-connect.css?v=2"' in module
assert 'src="/prt-connect.js?v=2"' in module
page = module.split('@router.get("/race-center/prt-connect"', 1)[1]
assert "<script>" not in page and "<style>" not in page
assert 'id="approve"' in page
assert 'id="feedback"' in page
assert 'aria-live="polite"' in page
assert 'type="button"' in page
assert "style-src 'self'; script-src 'self'" in policy
assert "addEventListener('click'" in javascript
assert "/api/public/race-center/prt/link/approve" in javascript
assert "Code expired or already used" in javascript
assert "Return to PRT" in javascript
assert "credentials: 'same-origin'" in javascript
assert len(css) > 1500
print("PRT pairing UI CSP and static-contract checks PASS")
