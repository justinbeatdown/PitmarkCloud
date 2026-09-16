from pathlib import Path

path = Path("api/prt_ui.py")
source = path.read_text(encoding="utf-8")

helper_marker = '''def _request_campaign_context(request: Request) -> tuple[str, str, str]:\n    return _campaign_context(\n        campaign=request.query_params.get("utm_campaign", ""),\n        source=request.query_params.get("utm_source", ""),\n        asset=request.query_params.get("utm_content", ""),\n    )\n\n\n'''
helper = '''def _request_campaign_context(request: Request) -> tuple[str, str, str]:\n    return _campaign_context(\n        campaign=request.query_params.get("utm_campaign", ""),\n        source=request.query_params.get("utm_source", ""),\n        asset=request.query_params.get("utm_content", ""),\n    )\n\n\ndef _apply_view_placement(request: Request) -> str:\n    role = (request.query_params.get("role", "") or "").strip().lower()\n    placements = {\n        "driver": "quick-apply-driver",\n        "league": "quick-apply-league",\n        "broadcaster": "quick-apply-broadcaster",\n        "media": "quick-apply-media",\n    }\n    return placements.get(role, "quick-apply")\n\n\n'''

if "def _apply_view_placement(request: Request)" not in source:
    if helper_marker not in source:
        raise SystemExit("campaign context marker not found")
    source = source.replace(helper_marker, helper, 1)

old = '                placement="quick-apply",\n'
new = '                placement=_apply_view_placement(request),\n'
if old in source:
    source = source.replace(old, new, 1)
elif new not in source:
    raise SystemExit("apply view placement marker not found")

path.write_text(source, encoding="utf-8")
print("Applied role-aware PRT apply-view placement tracking")
