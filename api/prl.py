from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.discord_hq_common import DISCORD_API, discord_request, list_channels
from utils.config import settings

router = APIRouter()

SCHEDULE = [
    {"round": 1, "date": "Jan 13, 2027", "night": "Wednesday", "track": "Daytona International Speedway", "laps": 80, "phase": "Regular Season", "note": "Season Opener"},
    {"round": 2, "date": "Jan 19, 2027", "night": "Tuesday", "track": "Charlotte Motor Speedway", "laps": 100, "phase": "Regular Season", "note": ""},
    {"round": 3, "date": "Jan 27, 2027", "night": "Wednesday", "track": "Iowa Speedway", "laps": 150, "phase": "Regular Season", "note": ""},
    {"round": 4, "date": "Feb 2, 2027", "night": "Tuesday", "track": "Phoenix Raceway", "laps": 150, "phase": "Regular Season", "note": ""},
    {"round": 5, "date": "Feb 10, 2027", "night": "Wednesday", "track": "Richmond Raceway", "laps": 200, "phase": "Regular Season", "note": ""},
    {"round": 6, "date": "Feb 16, 2027", "night": "Tuesday", "track": "Michigan International Speedway", "laps": 100, "phase": "Regular Season", "note": ""},
    {"round": 7, "date": "Feb 24, 2027", "night": "Wednesday", "track": "Martinsville Speedway", "laps": 200, "phase": "Regular Season", "note": ""},
    {"round": 8, "date": "Mar 2, 2027", "night": "Tuesday", "track": "Kansas Speedway", "laps": 100, "phase": "Regular Season", "note": ""},
    {"round": 9, "date": "Mar 10, 2027", "night": "Wednesday", "track": "Watkins Glen International", "laps": 41, "phase": "Regular Season", "note": "Road-Course Round"},
    {"round": 10, "date": "Mar 16, 2027", "night": "Tuesday", "track": "Nashville Superspeedway", "laps": 120, "phase": "Regular Season", "note": ""},
    {"round": 11, "date": "Mar 24, 2027", "night": "Wednesday", "track": "Talladega Superspeedway", "laps": 76, "phase": "Regular Season", "note": "CHASE CUTOFF"},
    {"round": 12, "date": "Mar 30, 2027", "night": "Tuesday", "track": "Bristol Motor Speedway", "laps": 200, "phase": "Chase", "note": "Chase Round 1"},
    {"round": 13, "date": "Apr 7, 2027", "night": "Wednesday", "track": "Dover Motor Speedway", "laps": 150, "phase": "Chase", "note": "Chase Round 2"},
    {"round": 14, "date": "Apr 13, 2027", "night": "Tuesday", "track": "Darlington Raceway", "laps": 125, "phase": "Chase", "note": "Chase Round 3"},
    {"round": 15, "date": "Apr 21, 2027", "night": "Wednesday", "track": "Homestead-Miami Speedway", "laps": 100, "phase": "Chase", "note": "CHAMPIONSHIP FINALE"},
]

REGISTRATION_URL = "https://docs.google.com/forms/d/e/1FAIpQLSc1AcvdYOZ1YRoyRe8yEdBmd1tttvIq1Put8Zk0gsJCKUoGjw/viewform"
HANDBOOK_URL = "/prl/docs/driver-handbook.pdf"
RULES_URL = "/prl/docs/competition-rulebook.pdf"
OPERATIONS_URL = "https://docs.google.com/spreadsheets/d/1A8SxUR2DlsRPjzhAZxboCBxWcpjdF8L4jaX-6VEc4nU/edit"
PRL_LOGO_URL = "https://cdn.shopify.com/s/files/1/1067/3913/8641/files/prl-logo.png?v=1791152433"
RACE_NIGHT_URL = "/prl/docs/race-night-guide.pdf"
CONTACT_EMAIL = "contact@pitmarkracing.com"
DISCORD_URL = "/prl/discord"
_DISCORD_INVITE_CACHE: str | None = None

async def _prl_discord_invite() -> str | None:
    global _DISCORD_INVITE_CACHE
    if _DISCORD_INVITE_CACHE:
        return _DISCORD_INVITE_CACHE

    guild_id = str(getattr(settings, "discord_hq_guild_id", "") or "").strip()
    if not guild_id:
        return None

    try:
        response = await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/invites")
        invites = list(response.json() or [])
        for invite in invites:
            code = str(invite.get("code") or "").strip()
            max_age = int(invite.get("max_age") or 0)
            max_uses = int(invite.get("max_uses") or 0)
            if code and max_age == 0 and max_uses == 0:
                _DISCORD_INVITE_CACHE = f"https://discord.gg/{code}"
                return _DISCORD_INVITE_CACHE

        channels = await list_channels(guild_id)
        target = next(
            (
                ch for ch in channels
                if int(ch.get("type", -1)) == 0
                and str(ch.get("name") or "") in {"welcome", "pitmark-chat"}
            ),
            None,
        )
        if target is None:
            target = next((ch for ch in channels if int(ch.get("type", -1)) == 0), None)
        if target is None:
            return None

        created = await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{target['id']}/invites",
            reason="PRL public website permanent invite",
            json={"max_age": 0, "max_uses": 0, "temporary": False, "unique": False},
        )
        code = str((created.json() or {}).get("code") or "").strip()
        if not code:
            return None
        _DISCORD_INVITE_CACHE = f"https://discord.gg/{code}"
        return _DISCORD_INVITE_CACHE
    except Exception:
        return None


@router.get("/prl/discord", include_in_schema=False)
@router.get("/discord", include_in_schema=False)
async def prl_discord_redirect():
    invite = await _prl_discord_invite()
    if invite:
        return RedirectResponse(url=invite, status_code=302)
    return RedirectResponse(url="/prl#contact", status_code=302)


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
.brand{{display:flex;align-items:center;gap:12px;font-weight:900;letter-spacing:.08em}} .brand img{{height:46px;width:auto;display:block}} .brand-copy{{display:none}} .hero-logo{{width:min(760px,92%);height:auto;display:block;margin:0 0 24px;filter:drop-shadow(0 10px 25px #000)}}
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
<header><div class='wrap'><nav><a class='brand' href='/prl'><img src='{PRL_LOGO_URL}' alt='Pitmark Racing League'><span class='brand-copy'>Pitmark Racing League</span></a><div class='links'><a href='#schedule'>Schedule</a><a href='#resources'>Driver Resources</a><a href='https://pitmarkracing.com/pages/race-center'>Race Center</a><a href='{REGISTRATION_URL}'>Register</a><a href='{DISCORD_URL}'>Discord</a><a href='#contact'>Contact</a></div></nav></div></header>
<main>
<section class='hero'><div class='wrap'><div class='eyebrow'>2027 INAUGURAL ARCA CHAMPIONSHIP</div><img class='hero-logo' src='{PRL_LOGO_URL}' alt='Pitmark Racing League'><h1 style='font-size:clamp(42px,6vw,82px)'>INAUGURAL <span>SEASON</span></h1><p class='lede'>15 rounds. Fixed-setup ARCA racing. Alternating Wednesday and Tuesday nights built around real life — with Race Center coverage, PRT integration, and a four-race Chase for the championship.</p><div class='cta'><a class='btn primary' href='{REGISTRATION_URL}'>Register to Race</a><a class='btn' href='{DISCORD_URL}'>Join Pitmark Discord</a><a class='btn' href='#schedule'>View Schedule</a><a class='btn' href='https://pitmarkracing.com/pages/race-center'>Race Center</a></div><div class='stats'><div class='stat'><b>15</b><span>Rounds</span></div><div class='stat'><b>11</b><span>Regular Season</span></div><div class='stat'><b>8</b><span>Chase Drivers</span></div><div class='stat'><b>4</b><span>Chase Races</span></div></div></div></section>
<section id='schedule'><div class='wrap'><h2>Season Schedule</h2><p class='sub'>Race window: 8:00 PM ET. Regular season ends at Talladega; the four-race Chase closes at Homestead-Miami.</p><div class='grid'>{schedule_cards}</div></div></section>
<section><div class='wrap'><h2>Built Into Pitmark</h2><div class='cards'><div class='card'><h3>Race Center</h3><p>Schedule, driver profiles, results, standings, Chase tracking, race recaps and league stories in the same Pitmark racing ecosystem.</p></div><div class='card'><h3>PRT</h3><p>PRT serves as PRL's race-technology platform for controlled testing, post-race intelligence and future Race Autopsy features.</p></div><div class='card'><h3>Partners</h3><p>Race entitlements, awards, Chase branding, digital inventory and broadcast-ready integrations without giving up ownership of Pitmark.</p></div></div></div></section>
<section><div class='wrap'><h2>League Community</h2><p class='sub'>PRL lives inside the Pitmark Racing Co. Discord. Drivers meetings, check-in, league announcements, race-week discussion, support and community conversation all run through the same server.</p><div class='card'><h3>Pitmark Discord</h3><p>Registered drivers should join the server before their first race night so they do not miss check-in, drivers meetings, schedule updates or Race Control notices.</p><a class='btn primary' href='{DISCORD_URL}'>Join the Pitmark Discord</a></div></div></section>
<section id='resources'><div class='wrap'><h2>Driver Resources</h2><p class='sub'>Public, driver-facing documents for the 2027 inaugural season.</p><div class='cards'><div class='card'><h3>Driver Handbook</h3><p>Season format, race-night flow, Chase system, points basics, conduct expectations and the full schedule.</p><a class='btn' href='{HANDBOOK_URL}' target='_blank' rel='noopener'>Open PDF</a></div><div class='card'><h3>Competition Rulebook</h3><p>The on-track rules competitors need: starts, restarts, blocking, contact, pit road, protests and penalties.</p><a class='btn' href='{RULES_URL}' target='_blank' rel='noopener'>Open PDF</a></div><div class='card'><h3>Race Night Guide</h3><p>A one-page quick reference for timeline, session settings and the five things every PRL driver should remember.</p><a class='btn' href='{RACE_NIGHT_URL}' target='_blank' rel='noopener'>Open PDF</a></div></div></div></section><section id='contact'><div class='wrap'><h2>Contact PRL</h2><p class='sub'>Questions about registration, rules, race-night support, partnerships or the league in general?</p><div class='card'><h3>Email</h3><p><a href='mailto:{CONTACT_EMAIL}' style='color:var(--orange);font-weight:900'>{CONTACT_EMAIL}</a></p><p>Use this address for driver support, registration questions, rule clarifications and partnership inquiries. For day-to-day league activity, join the <a href='{DISCORD_URL}' style='color:var(--orange);font-weight:900'>Pitmark Discord</a>.</p></div></div></section>
</main>
<footer><div class='wrap'>Pitmark Racing League · A Pitmark Racing Co. property · <a href='{DISCORD_URL}'>Pitmark Discord</a> · <a href='mailto:{CONTACT_EMAIL}'>{CONTACT_EMAIL}</a> · Leave Your Mark.</div></footer>
</body></html>""")
