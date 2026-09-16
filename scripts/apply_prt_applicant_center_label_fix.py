from pathlib import Path

path = Path("api/early_access_admin.py")
source = path.read_text(encoding="utf-8")

marker = '''def _application_cards(rows: list[dict]) -> str:\n'''
helper = '''def _application_card_labels(placement: str | None) -> dict[str, str]:\n    role = application_role_from_placement(placement)\n    if role == "Broadcaster":\n        return {\n            "identity": "BROADCAST / PRODUCTION",\n            "frequency": "PRODUCTION FREQUENCY",\n            "role": "APPLICANT ROLE",\n            "tools": "BROADCAST TOOLS",\n            "goals": "WHAT WOULD MAKE PRT USEFUL TO YOUR BROADCAST?",\n        }\n    if role == "League / Club":\n        return {\n            "identity": "LEAGUE / CLUB",\n            "frequency": "RACE-NIGHT FREQUENCY",\n            "role": "APPLICANT ROLE",\n            "tools": "ADMIN TOOLS",\n            "goals": "WHAT WOULD MAKE PRT USEFUL TO YOUR LEAGUE / CLUB?",\n        }\n    if role == "Media / Developer":\n        return {\n            "identity": "OUTLET / PROJECT",\n            "frequency": "WORKFLOW FREQUENCY",\n            "role": "APPLICANT ROLE",\n            "tools": "WORKFLOW TOOLS",\n            "goals": "WHAT WOULD YOU LIKE TO INSPECT / TEST / DISCUSS?",\n        }\n    return {\n        "identity": "iRACING",\n        "frequency": "RACES",\n        "role": "DISCIPLINES",\n        "tools": "CURRENT TOOLS",\n        "goals": "WHAT WOULD MAKE PRT USEFUL?",\n    }\n\n\n'''

if helper not in source:
    if marker not in source:
        raise SystemExit("Applicant card marker not found")
    source = source.replace(marker, helper + marker, 1)

old_setup = '''        gmail_url = escape(_gmail_compose(raw_email, row.get("full_name") or "there"), quote=True)\n        acceptance_action = ""\n'''
new_setup = '''        gmail_url = escape(_gmail_compose(raw_email, row.get("full_name") or "there"), quote=True)\n        labels = _application_card_labels(row.get("placement") or "quick-apply")\n        acceptance_action = ""\n'''
if old_setup in source:
    source = source.replace(old_setup, new_setup, 1)
elif new_setup not in source:
    raise SystemExit("Applicant card setup marker not found")

replacements = {
    '<section><span class="label">iRACING</span><strong>{iracing}</strong></section>': '<section><span class="label">{labels[\'identity\']}</span><strong>{iracing}</strong></section>',
    '<section><span class="label">RACES</span><strong>{frequency}</strong></section>': '<section><span class="label">{labels[\'frequency\']}</span><strong>{frequency}</strong></section>',
    '<section><span class="label">DISCIPLINES</span><p>{disciplines}</p></section>': '<section><span class="label">{labels[\'role\']}</span><p>{disciplines}</p></section>',
    '<section><span class="label">CURRENT TOOLS</span><p>{tools}</p></section>': '<section><span class="label">{labels[\'tools\']}</span><p>{tools}</p></section>',
    '<span class="label">WHAT WOULD MAKE PRT USEFUL?</span>': '<span class="label">{labels[\'goals\']}</span>',
}
for old, new in replacements.items():
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise SystemExit(f"Expected Applicant Center label not found: {old}")

path.write_text(source, encoding="utf-8")
print("Applied role-aware PRT Applicant Center labels")
