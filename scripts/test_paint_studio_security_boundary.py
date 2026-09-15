from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
security = (ROOT / "utils" / "security.py").read_text(encoding="utf-8")

assert "PAINT_STUDIO_PSD_MAX_REQUEST_BODY" in security, "Paint Studio PSD uploads need a route-specific body limit"
assert "PAINT_STUDIO_GENERATE_MAX_REQUEST_BODY" in security, "Paint Studio generation needs a route-specific body limit"
assert 'path in {"/api/control/content/paint-studio/psd/import", "/api/control/content/paint-studio/psd/render"}' in security
assert 'path == "/api/control/content/paint-studio/generate"' in security

marker = 'elif request.url.path.startswith("/api/control/content/paint-studio"):'
assert marker in security, "Paint Studio needs an explicit CSP instead of the default-src none fallback"
block = security.split(marker, 1)[1].split("elif ", 1)[0]
assert "script-src 'self'" in block, "Paint Studio must be allowed to load its same-origin JS engine"
assert "connect-src 'self'" in block, "Paint Studio must be allowed to call its same-origin PSD/generation APIs"
assert "style-src 'self' 'unsafe-inline'" in block, "Paint Studio needs its stylesheet plus runtime canvas sizing styles"
assert "img-src 'self' blob: data:" in block, "Paint Studio previews use local blob/data image URLs"

print("PAINT_STUDIO_SECURITY_BOUNDARY_OK")
