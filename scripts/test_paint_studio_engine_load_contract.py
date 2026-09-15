from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "api" / "paint-studio.html").read_text(encoding="utf-8")
backend = (ROOT / "api" / "content_tools.py").read_text(encoding="utf-8")

script_tag = '<script src="/api/control/content/paint-studio.js?v=4"></script>'

assert script_tag in html, "Paint Studio must load its engine with a real same-origin script request"
assert "<!-- PAINT_STUDIO_ENGINE -->" not in html, "Inline engine placeholder must be removed"
assert 'html.replace("<!-- PAINT_STUDIO_ENGINE -->"' not in backend, "Backend must not inline the Paint Studio engine"
assert '@router.get("/paint-studio.js"' in backend, "Paint Studio JS route must remain available"

print("PAINT_STUDIO_ENGINE_LOAD_CONTRACT_OK")
