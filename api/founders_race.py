from __future__ import annotations

from html import escape

from fastapi import APIRouter, Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.control_auth import require_control_user
from services.founders_race import leaderboard, record_referral, referrer_card
from services.prt_applications import submit_application

router = APIRouter()


def _shell(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b0e"><title>{escape(title)}</title>
<style>
:root{{--orange:#ff5500;--bg:#080a0c;--panel:#111419;--line:rgba(255,255,255,.09);--text:#f4f5f5;--muted:#8b949d;--good:#55dc89;--bad:#ff7676}}
*{{box-sizing:border-box}}html,body{{margin:0;background:linear-gradient(180deg,#090b0e,#07090b);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;min-height:100%}}a{{color:inherit}}body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 78% 3%,rgba(255,85,0,.10),transparent 31%)}}
.wrap{{position:relative;width:min(1100px,calc(100% - 32px));margin:0 auto;padding:44px 0 72px}}.brand{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:34px}}.brand strong{{font-size:14px;letter-spacing:.12em;text-transform:uppercase}}.brand span{{color:var(--orange)}}
.hero{{border:1px solid var(--line);border-left:3px solid var(--orange);border-radius:18px;background:linear-gradient(145deg,#13171c,#0d1014);padding:28px;margin-bottom:18px}}.eyebrow{{color:#ff7d43;font-size:10px;font-weight:900;letter-spacing:.16em;text-transform:uppercase}}h1{{font-size:clamp(38px,7vw,72px);font-style:italic;letter-spacing:-.055em;line-height:.92;margin:8px 0 12px}}p{{color:#a1a8af;line-height:1.6}}.cta{{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:10px;background:var(--orange);color:white;text-decoration:none;font-size:11px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;border:0;cursor:pointer}}
.grid{{display:grid;grid-template-columns:1.25fr .75fr;gap:14px}}.panel{{border:1px solid var(--line);border-radius:16px;background:#101419;padding:20px}}.panel h2{{margin:0 0 12px;font-size:18px}}.standings{{display:grid;gap:8px}}.row{{display:grid;grid-template-columns:56px 1fr 90px;align-items:center;gap:10px;padding:12px;border:1px solid var(--line);border-radius:12px;background:#0c0f13}}.pos{{font-size:22px;font-weight:950;font-style:italic;color:#ff7d43}}.name{{font-weight:800}}.count{{text-align:right;font-size:20px;font-weight:950}}.count small{{display:block;color:var(--muted);font-size:8px;letter-spacing:.08em;text-transform:uppercase}}
.prizes{{display:grid;gap:8px}}.prize{{padding:12px;border:1px solid var(--line);border-radius:11px;background:#0c0f13}}.prize strong{{display:block;color:#ff7d43}}.muted{{color:var(--muted);font-size:12px}}.card{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}}.stat{{padding:14px;border:1px solid var(--line);border-radius:12px;background:#0b0f13}}.stat span{{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.1em}}.stat strong{{display:block;margin-top:4px;font-size:25px}}
form{{display:grid;gap:12px}}label{{font-size:10px;color:#aeb5bb;font-weight:800;letter-spacing:.05em;text-transform:uppercase}}input,select,textarea{{width:100%;margin-top:6px;padding:11px;border-radius:9px;border:1px solid var(--line);background:#090c10;color:white}}textarea{{min-height:90px;resize:vertical}}.checks{{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}}.check{{display:flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:9px;padding:10px;background:#0b0f13;font-size:12px;color:#d9dcdf;text-transform:none;letter-spacing:0}}.check input{{width:auto;margin:0}}.notice{{padding:12px;border-radius:10px;background:rgba(85,220,137,.08);border:1px solid rgba(85,220,137,.2);color:#aeeec5}}table{{width:100%;border-collapse:collapse;font-size:12px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:#818a93;font-size:9px;text-transform:uppercase;letter-spacing:.08em}}code{{color:#ff9b6b}}details{{margin-top:7px}}summary{{cursor:pointer;color:#d9dcdf}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.checks{{grid-template-columns:1fr}}.row{{grid-template-columns:48px 1fr 72px}}.card{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">{body}</div></body></html>""", headers={"Cache-Control":"no-store"})


def _standing_rows(rows: list[dict]) -> str:
    if not rows:
        return '<p class="muted">No qualified referrals yet. The green flag is waiting.</p>'
    shown = [row for row in rows if row["qualified"] > 0][:25]
    if not shown:
        return '<p class="muted">No qualified referrals yet. First activated referral takes P1.</p>'
    return "".join(
        f'<div class="row"><div class="pos">P{row["position"]}</div><div><div class="name">{escape(row["display_name"])}</div><div class="muted">{escape(row.get("milestone") or "Founding Tester")}</div></div><div class="count">{row["qualified"]}<small>qualified</small></div></div>'
        for row in shown
    )


@router.get("/founders-race", response_class=HTMLResponse, include_in_schema=False)
def founders_race_public():
    rows = leaderboard()
    body = f"""
    <div class="brand"><strong>PITMARK RACING TOOLS <span>FOUNDERS RACE</span></strong><a class="muted" href="/prt">PRT HOME</a></div>
    <section class="hero"><div class="eyebrow">EARLY ACCESS REFERRAL CHAMPIONSHIP</div><h1>BRING THE GRID.</h1><p>PRT Early Access testers earn position by bringing in new racers who are approved and actually activate PRT. Clicks and raw applications do not count. Qualified activations do.</p><a class="cta" href="/prt/apply">JOIN EARLY ACCESS</a></section>
    <div class="grid"><section class="panel"><h2>Live Standings</h2><div class="standings">{_standing_rows(rows)}</div></section>
    <aside class="panel"><h2>Prizes</h2><div class="prizes"><div class="prize"><strong>P1 · 12 MONTHS</strong><span class="muted">Highest paid PRT tier, free for one year.</span></div><div class="prize"><strong>P2 · 6 MONTHS</strong><span class="muted">Highest paid PRT tier.</span></div><div class="prize"><strong>P3 · 3 MONTHS</strong><span class="muted">Highest paid PRT tier.</span></div><div class="prize"><strong>5 + 10 REFERRALS</strong><span class="muted">Founder's Race milestone recognition. Milestones do not automatically alter paid entitlements.</span></div></div><p class="muted">Race ends when PRT leaves Early Access for its first public release. Pitmark verifies referrals and activation records before final rewards are issued.</p></aside></div>
    """
    return _shell("PRT Founder's Race", body)


@router.get("/founders-race/r/{code}", response_class=HTMLResponse, include_in_schema=False)
def founder_referral_page(code: str):
    card = referrer_card(code)
    if card is None:
        return RedirectResponse(url="/founders-race", status_code=302)
    next_text = "Finish strong — 10 Referral Club reached." if card["next_milestone"] is None else f'{max(0, card["next_milestone"] - card["qualified"])} more to the next milestone.'
    code_e = escape(card["referral_code"])
    name_e = escape(card["display_name"])
    body = f"""
    <div class="brand"><strong>PITMARK RACING TOOLS <span>FOUNDERS RACE</span></strong><a class="muted" href="/founders-race">STANDINGS</a></div>
    <section class="hero"><div class="eyebrow">REFERRED BY {name_e}</div><h1>JOIN THE EARLY GRID.</h1><p>Apply for PRT Early Access through this Founder's Race link. A referral only scores after Pitmark approves the application and the new tester activates PRT.</p></section>
    <div class="card"><div class="stat"><span>Position</span><strong>P{card["position"]}</strong></div><div class="stat"><span>Qualified</span><strong>{card["qualified"]}</strong></div><div class="stat"><span>Pending</span><strong>{card["pending"]}</strong></div></div><p class="muted">{escape(next_text)} · Referral code: <code>{code_e}</code></p>
    <section class="panel"><h2>Apply for PRT Early Access</h2><form method="post" action="/founders-race/r/{code_e}/apply">
      <label>Full name<input name="full_name" maxlength="120" required></label><label>Email<input name="email" type="email" maxlength="200" required></label><label>iRacing display name<input name="iracing_name" maxlength="120" required></label><label>Discord username <span class="muted">optional</span><input name="discord_username" maxlength="100"></label>
      <label>Disciplines</label><div class="checks"><label class="check"><input type="checkbox" name="disciplines" value="Oval"> Oval</label><label class="check"><input type="checkbox" name="disciplines" value="Sports Car"> Sports Car</label><label class="check"><input type="checkbox" name="disciplines" value="Formula"> Formula</label><label class="check"><input type="checkbox" name="disciplines" value="Dirt Oval"> Dirt Oval</label><label class="check"><input type="checkbox" name="disciplines" value="Dirt Road"> Dirt Road</label></div>
      <label>How often do you race?<select name="race_frequency" required><option value="">Choose one</option><option>Daily</option><option>Several times a week</option><option>Weekly</option><option>A few times a month</option></select></label><label>Current tools <span class="muted">optional</span><input name="current_tools" maxlength="320"></label><label>What would make PRT useful to you?<textarea name="goals" maxlength="1200"></textarea></label>
      <label class="check"><input type="checkbox" name="tester_agreement" value="yes" required> I can actively test PRT, report bugs, give honest feedback, and understand Early Access software may change.</label><input name="company_website" tabindex="-1" autocomplete="off" style="position:absolute;left:-10000px" aria-hidden="true"><button class="cta" type="submit">APPLY THROUGH {name_e}</button>
    </form></section>
    """
    return _shell(f"PRT Founder's Race · {card['display_name']}", body)


@router.post("/founders-race/r/{code}/apply", response_class=HTMLResponse, include_in_schema=False)
def founder_referred_apply(
    code: str,
    full_name: str = Form(...),
    email: str = Form(...),
    iracing_name: str = Form(...),
    discord_username: str = Form(default=""),
    disciplines: list[str] = Form(default=[]),
    race_frequency: str = Form(...),
    current_tools: str = Form(default=""),
    goals: str = Form(default=""),
    tester_agreement: str = Form(default=""),
    company_website: str = Form(default=""),
):
    card = referrer_card(code)
    if card is None:
        return RedirectResponse(url="/founders-race", status_code=302)
    if company_website.strip():
        return RedirectResponse(url="/founders-race", status_code=302)
    agreed = tester_agreement == "yes"
    try:
        result = submit_application(
            full_name=full_name,
            email=email,
            discord_username=discord_username,
            iracing_name=iracing_name,
            disciplines=", ".join(x.strip() for x in disciplines if x.strip())[:320],
            race_frequency=race_frequency,
            current_tools=current_tools,
            goals=goals,
            can_test=agreed,
            bug_reports=agreed,
            honest_feedback=agreed,
            expectations_agreed=agreed,
            campaign="founders_race_2026",
            source="tester_referral",
            asset=card["referral_code"],
            placement="founders-race",
        )
    except ValueError as exc:
        return _shell("PRT Founder's Race · Application", f'<div class="brand"><strong>PITMARK RACING TOOLS <span>FOUNDERS RACE</span></strong></div><section class="panel"><h2>Application needs one fix</h2><p>{escape(str(exc))}</p><a class="cta" href="/founders-race/r/{escape(code)}">GO BACK</a></section>')

    attribution = {"credited": False, "reason": "duplicate_application"}
    if result.get("application_id") and not result.get("duplicate"):
        attribution = record_referral(
            referral_code=code,
            application_id=int(result["application_id"]),
            applicant_email=email,
            applicant_name=full_name,
        )
    note = "Your application is in. If Pitmark approves you and you activate PRT, this referral becomes a qualified Founder's Race result."
    if attribution.get("reason") == "self_referral":
        note = "Your application is in, but self-referrals do not score in the Founder's Race."
    elif result.get("duplicate"):
        note = "We already have a recent application for this email, so a new referral was not added. Your existing application remains active."
    return _shell("PRT Founder's Race · Application received", f'<div class="brand"><strong>PITMARK RACING TOOLS <span>FOUNDERS RACE</span></strong></div><section class="hero"><div class="eyebrow">APPLICATION RECEIVED</div><h1>YOU\'RE ON THE BOARD.</h1><p>{escape(note)}</p><a class="cta" href="/founders-race">VIEW FOUNDERS RACE</a></section>')


@router.get("/control/founders-race", response_class=HTMLResponse, include_in_schema=False)
def founders_race_admin(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    require_control_user(request, x_pitmark_admin_key)
    rows = leaderboard()
    qualified_total = sum(row["qualified"] for row in rows)
    pending_total = sum(row["pending"] for row in rows)
    flagged_total = sum(row["flagged"] for row in rows)
    cards = []
    for row in rows:
        details = "".join(f'<tr><td>#{item["application_id"]}</td><td>{escape(item["applicant_name"] or "Applicant")}</td><td>{escape(item["applicant_email"])}</td><td>{escape(item["state"])}</td><td>{escape(item["fraud_reason"] or "—")}</td></tr>' for item in row["referrals"]) or '<tr><td colspan="5" class="muted">No referrals yet.</td></tr>'
        cards.append(f'''<section class="panel"><div class="row"><div class="pos">P{row["position"]}</div><div><div class="name">{escape(row["display_name"])}</div><div class="muted">{escape(row["email"])}</div></div><div class="count">{row["qualified"]}<small>qualified</small></div></div><p class="muted">Referral link: <code>https://prt.pitmarkracing.com/founders-race/r/{escape(row["referral_code"])}</code> · Pending {row["pending"]} · Flagged {row["flagged"]}</p><details><summary>Referral audit</summary><table><thead><tr><th>App</th><th>Name</th><th>Email</th><th>State</th><th>Fraud check</th></tr></thead><tbody>{details}</tbody></table></details></section>''')
    body = f'''<div class="brand"><strong>PITMARK CONTROL CENTER <span>FOUNDERS RACE</span></strong><a class="muted" href="/control/early-access">EARLY ACCESS</a></div><section class="hero"><div class="eyebrow">PRIVATE ADMIN VIEW · DO NOT ANNOUNCE</div><h1>FOUNDERS RACE.</h1><p>Only approved applicants with a redeemed PRT Early Access activation qualify. Self-referrals and duplicate referred emails are flagged and never score automatically. Rewards are tracked here only; this feature does not grant or bypass paid entitlements.</p></section><div class="card"><div class="stat"><span>Testers</span><strong>{len(rows)}</strong></div><div class="stat"><span>Qualified</span><strong>{qualified_total}</strong></div><div class="stat"><span>Pending / Flagged</span><strong>{pending_total} / {flagged_total}</strong></div></div>{''.join(cards)}'''
    return _shell("Founder's Race · Control Center", body)
