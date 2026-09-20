from pathlib import Path

# Contract: audience messaging must coexist with the existing apply/download entry points.
html = Path("api/prt.html").read_text(encoding="utf-8")

required = [
    'aria-label="PRT audience fit"',
    'Where do you fit?',
    '>Drivers<',
    '>Leagues &amp; Clubs<',
    '>Broadcasters<',
    '>Media / Developers<',
    'Broadcast Studio is in development',
    'Advanced coaching and Driver DNA are in development',
    'data-prt-funnel-link="hero-apply"',
    'data-prt-download="prt-home-accepted"',
    'aria-label="PRT Founder\'s Race"',
    'personal Founder’s Race Hub',
    'P1 earns 12 months',
    'data-prt-funnel-link="founders-race-apply"',
]

missing = [token for token in required if token not in html]
if missing:
    raise SystemExit("Missing PRT audience-fit contract tokens: " + ", ".join(missing))

print("PRT audience-fit contract OK")
