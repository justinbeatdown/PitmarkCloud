from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()

SCHEDULE = [
    {"round": 1, "date": "Jan 13, 2027", "night": "Wednesday", "track": "Daytona International Speedway", "laps": 70, "phase": "Regular Season", "note": "Season Opener"},
    {"round": 2, "date": "Jan 19, 2027", "night": "Tuesday", "track": "Charlotte Motor Speedway", "laps": 90, "phase": "Regular Season", "note": ""},
    {"round": 3, "date": "Jan 27, 2027", "night": "Wednesday", "track": "Iowa Speedway", "laps": 110, "phase": "Regular Season", "note": ""},
    {"round": 4, "date": "Feb 2, 2027", "night": "Tuesday", "track": "Phoenix Raceway", "laps": 105, "phase": "Regular Season", "note": ""},
    {"round": 5, "date": "Feb 10, 2027", "night": "Wednesday", "track": "Richmond Raceway", "laps": 125, "phase": "Regular Season", "note": ""},
    {"round": 6, "date": "Feb 16, 2027", "night": "Tuesday", "track": "Michigan International Speedway", "laps": 70, "phase": "Regular Season", "note": ""},
    {"round": 7, "date": "Feb 24, 2027", "night": "Wednesday", "track": "Martinsville Speedway", "laps": 150, "phase": "Regular Season", "note": ""},
    {"round": 8, "date": "Mar 2, 2027", "night": "Tuesday", "track": "Kansas Speedway", "laps": 90, "phase": "Regular Season", "note": ""},
    {"round": 9, "date": "Mar 10, 2027", "night": "Wednesday", "track": "Watkins Glen International", "laps": 35, "phase": "Regular Season", "note": "Road-Course Round"},
    {"round": 10, "date": "Mar 16, 2027", "night": "Tuesday", "track": "Nashville Superspeedway", "laps": 90, "phase": "Regular Season", "note": ""},
    {"round": 11, "date": "Mar 24, 2027", "night": "Wednesday", "track": "Talladega Superspeedway", "laps": 60, "phase": "Regular Season", "note": "CHASE CUTOFF"},
    {"round": 12, "date": "Mar 30, 2027", "night": "Tuesday", "track": "Bristol Motor Speedway", "laps": 160, "phase": "Chase", "note": "Chase Round 1"},
    {"round": 13, "date": "Apr 7, 2027", "night": "Wednesday", "track": "Dover Motor Speedway", "laps": 120, "phase": "Chase", "note": "Chase Round 2"},
    {"round": 14, "date": "Apr 13, 2027", "night": "Tuesday", "track": "Darlington Raceway", "laps": 110, "phase": "Chase", "note": "Chase Round 3"},
    {"round": 15, "date": "Apr 21, 2027", "night": "Wednesday", "track": "Homestead-Miami Speedway", "laps": 100, "phase": "Chase", "note": "CHAMPIONSHIP FINALE"},
]

REGISTRATION_URL = "https://docs.google.com/forms/d/e/1FAIpQLSc1AcvdYOZ1YRoyRe8yEdBmd1tttvIq1Put8Zk0gsJCKUoGjw/viewform"
HANDBOOK_URL = "https://docs.google.com/document/d/1S1_dZU9DRbCcjHEaRx-Ka1vvzxnOXWmF8ni4gMd_jf4/edit"
RULES_URL = "https://docs.google.com/document/d/1J46VOhEeb6nL54ryv01Um34yMmQ0fjE2uqdUDCK1yeY/edit"
OPERATIONS_URL = "https://docs.google.com/spreadsheets/d/1A8SxUR2DlsRPjzhAZxboCBxWcpjdF8L4jaX-6VEc4nU/edit"

@router.get("/api/prl/schedule")
def prl_schedule():
    return JSONResponse({"season": "2027 Inaugural ARCA Championship", "rounds": SCHEDULE})

@router.get("/prl", response_class=HTMLResponse)
def prl_landing():
    schedule_cards = "".join(
        f"""<article class='round {'chase' if item['phase']=='Chase' else ''}'>
        <div class='rnum'>R{item['round']:02}</div>
        <div><strong>{item['track']}</strong><span>{item['date']} · {item['night']} · {item['laps']} laps</span></div>
        <em>{item['note'] or item['phase']}</em>
        </article>"""
        for item in SCHEDULE
    )
    return HTMLResponse(f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>PRL — Pitmark Racing League</title>
<meta name='description' content='The Pitmark Racing League inaugural ARCA Championship: 15 rounds, rotating Wednesday/Tuesday nights, Race Center coverage and PRT integration.'>
<style>
:root{{--orange:#ff5500;--bg:#090909;--panel:#141414;--muted:#a9a9a9;--line:#2a2a2a}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:#f8f8f8;font-family:Arial,Helvetica,sans-serif}}
a{{color:inherit;text-decoration:none}} .wrap{{max-width:1180px;margin:auto;padding:0 24px}}
header{{border-bottom:1px solid var(--line);position:sticky;top:0;background:#090909ed;backdrop-filter:blur(10px);z-index:10}}
nav{{height:72px;display:flex;align-items:center;justify-content:space-between;gap:20px}}
.brand{{display:flex;align-items:center;gap:12px;font-weight:900;letter-spacing:.08em}} .mark{{font-size:30px;font-style:italic;color:var(--orange)}} .brand small{{display:block;font-size:10px;color:var(--muted)}}
.links{{display:flex;gap:18px;font-size:13px;font-weight:700}} .hero{{padding:72px 0 48px;background:radial-gradient(circle at 80% 0,#4a1800 0,transparent 32%),linear-gradient(135deg,#0b0b0b,#111)}}
.eyebrow{{color:var(--orange);font-weight:900;letter-spacing:.18em;font-size:12px}} h1{{font-size:clamp(48px,8vw,104px);line-height:.86;margin:18px 0;text-transform:uppercase;letter-spacing:-.04em;font-style:italic}}
h1 span{{color:var(--orange)}} .lede{{font-size:20px;line-height:1.5;color:#d0d0d0;max-width:760px}} .cta{{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}}
.btn{{padding:14px 20px;border:1px solid var(--orange);font-weight:900;text-transform:uppercase;font-size:13px}} .btn.primary{{background:var(--orange);color:#050505}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:42px}} .stat{{background:var(--panel);padding:20px;border-top:3px solid var(--orange)}} .stat b{{font-size:30px;display:block}} .stat span{{color:var(--muted);font-size:12px;text-transform:uppercase}}
section{{padding:52px 0}} h2{{font-size:34px;text-transform:uppercase;font-style:italic;margin:0 0 18px}} .sub{{color:var(--muted);margin-bottom:26px}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}} .round{{display:grid;grid-template-columns:66px 1fr auto;align-items:center;gap:12px;padding:16px;background:var(--panel);border:1px solid var(--line)}} .round.chase{{border-color:#613000;background:#1b120d}}
.rnum{{font-weight:900;color:var(--orange);font-size:18px}} .round strong{{display:block}} .round span{{display:block;color:var(--muted);font-size:12px;margin-top:4px}} .round em{{font-style:normal;color:#cfcfcf;font-size:11px;font-weight:900;text-transform:uppercase;text-align:right}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}} .card{{background:var(--panel);border:1px solid var(--line);padding:24px}} .card h3{{margin-top:0;text-transform:uppercase}} .card p{{color:var(--muted);line-height:1.55}}
footer{{border-top:1px solid var(--line);padding:30px 0 50px;color:var(--muted);font-size:12px}}
@media(max-width:800px){{.links{{display:none}}.stats{{grid-template-columns:repeat(2,1fr)}}.grid,.cards{{grid-template-columns:1fr}}.round{{grid-template-columns:55px 1fr}}.round em{{grid-column:2;text-align:left}}}}
</style>
</head><body>
<header><div class='wrap'><nav><a class='brand' href='/prl'><span class='mark'>PRL</span><span>PITMARK RACING LEAGUE<small>LEAVE YOUR MARK.</small></span></a><div class='links'><a href='#schedule'>Schedule</a><a href='{RULES_URL}'>Rules</a><a href='https://pitmarkracing.com/pages/race-center'>Race Center</a><a href='{REGISTRATION_URL}'>Register</a></div></nav></div></header>
<main>
<section class='hero'><div class='wrap'><div class='eyebrow'>2027 INAUGURAL ARCA CHAMPIONSHIP</div><h1>PITMARK <span>RACING LEAGUE</span></h1><p class='lede'>15 rounds. Fixed-setup ARCA racing. Alternating Wednesday and Tuesday nights built around real life — with Race Center coverage, PRT integration, and a four-race Chase for the championship.</p><div class='cta'><a class='btn primary' href='{REGISTRATION_URL}'>Register to Race</a><a class='btn' href='#schedule'>View Schedule</a><a class='btn' href='https://pitmarkracing.com/pages/race-center'>Race Center</a></div><div class='stats'><div class='stat'><b>15</b><span>Rounds</span></div><div class='stat'><b>11</b><span>Regular Season</span></div><div class='stat'><b>8</b><span>Chase Drivers</span></div><div class='stat'><b>4</b><span>Chase Races</span></div></div></div></section>
<section id='schedule'><div class='wrap'><h2>Season Schedule</h2><p class='sub'>Race window: 8:00 PM ET. Regular season ends at Talladega; the four-race Chase closes at Homestead-Miami.</p><div class='grid'>{schedule_cards}</div></div></section>
<section><div class='wrap'><h2>Built Into Pitmark</h2><div class='cards'><div class='card'><h3>Race Center</h3><p>Schedule, driver profiles, results, standings, Chase tracking, race recaps and league stories in the same Pitmark racing ecosystem.</p></div><div class='card'><h3>PRT</h3><p>PRT serves as PRL's race-technology platform for controlled testing, post-race intelligence and future Race Autopsy features.</p></div><div class='card'><h3>Partners</h3><p>Race entitlements, awards, Chase branding, digital inventory and broadcast-ready integrations without giving up ownership of Pitmark.</p></div></div></div></section>
<section><div class='wrap'><h2>League Documents</h2><div class='cta'><a class='btn' href='{HANDBOOK_URL}'>League Handbook</a><a class='btn' href='{RULES_URL}'>Sporting Regulations</a><a class='btn' href='{OPERATIONS_URL}'>Master Operations</a></div></div></section>
</main>
<footer><div class='wrap'>Pitmark Racing League · A Pitmark Racing Co. property · Leave Your Mark.</div></footer>
</body></html>""")
