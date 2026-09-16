from pathlib import Path

# Final exact-head verification for the role-aware apply funnel and view tracking.
home = Path("api/prt.html").read_text(encoding="utf-8")
apply_html = Path("api/prt-apply.html").read_text(encoding="utf-8")
apply_js = Path("api/prt-apply.js").read_text(encoding="utf-8")
prt_ui = Path("api/prt_ui.py").read_text(encoding="utf-8")
backend = Path("services/prt_applications.py").read_text(encoding="utf-8")

required = {
    "home": [
        '/prt/apply?role=driver',
        '/prt/apply?role=league',
        '/prt/apply?role=broadcaster',
        '/prt/apply?role=media',
    ],
    "apply_html": [
        'name="applicant_role"',
        'value="driver"',
        'value="league"',
        'value="broadcaster"',
        'value="media"',
        'id="iracingNameLabel"',
        'id="disciplinesFieldset"',
        'id="raceFrequencyLabel"',
        'id="currentToolsLabel"',
        'id="goalsLabel"',
        'id="testerAgreementCopy"',
    ],
    "apply_js": [
        "quick-apply-driver",
        "quick-apply-league",
        "quick-apply-broadcaster",
        "quick-apply-media",
        "Organization / league / outlet / project",
        "I can test or review PRT in a real workflow and send honest feedback",
    ],
    "prt_ui": [
        "_apply_view_placement",
        '"quick-apply-driver"',
        '"quick-apply-league"',
        '"quick-apply-broadcaster"',
        '"quick-apply-media"',
        'placement=_apply_view_placement(request)',
    ],
    "backend": [
        "application_role_from_placement",
        "Organization / outlet",
        "Applicant role",
    ],
}

texts = {
    "home": home,
    "apply_html": apply_html,
    "apply_js": apply_js,
    "prt_ui": prt_ui,
    "backend": backend,
}

missing = []
for surface, tokens in required.items():
    for token in tokens:
        if token not in texts[surface]:
            missing.append(f"{surface}: {token}")

if missing:
    raise SystemExit("Missing role-aware PRT apply contract tokens:\n- " + "\n- ".join(missing))

print("PRT role-aware apply contract OK")
