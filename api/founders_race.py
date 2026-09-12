from __future__ import annotations

from html import escape

from fastapi import APIRouter, Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.control_auth import require_control_user
from services.founders_race import leaderboard, record_referral, referrer_card
from services.prt_applications import submit_application

router = APIRouter()
CANONICAL = "https://prt.pitmarkracing.com"


def _shell(title: str, body: str, *, admin: bool = False) -> HTMLResponse:
    script = """
<script>
(function(){
  async function copyText(text, button){
    try{await navigator.clipboard.writeText(text);}
    catch(e){
      const ta=document.createElement('textarea'); ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
    }
    if(button){const old=button.textContent; button.textContent='COPIED ✓'; setTimeout(()=>button.textContent=old,1400);}
  }
  document.addEventListener('click', async function(e){
    const copy=e.target.closest('[data-copy]');
    if(copy){e.preventDefault(); await copyText(copy.getAttribute('data-copy')||'',copy); return;}
    const share=e.target.closest('[data-share]');
    if(share){
      e.preventDefault(); const url=share.getAttribute('data-share')||location.href;
      const text=share.getAttribute('data-share-text')||'Join PRT Early Access through my Founder\'s Race link.';
      if(navigator.share){try{await navigator.share({title:'PRT Founder\'s Race',text,url}); return;}catch(err){}}
      await copyText(url,share);
    }
  });
})();
</script>
"""
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b0e"><title>{escape(title)}</title>
<style>
:root{{--o:#ff5500;--o2:#ff8146;--bg:#07090b;--panel:#11151a;--panel2:#0c1014;--line:rgba(255,255,255,.09);--text:#f6f7f7;--muted:#8e979f;--good:#50da86;--bad:#ff7070}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}html,body{{margin:0;background:#07090b;color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;min-height:100%}}body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 79% 0,rgba(255,85,0,.14),transparent 33%),linear-gradient(180deg,rgba(255,255,255,.015),transparent 35%);z-index:0}}a{{color:inherit}}.wrap{{position:relative;z-index:1;width:min(1160px,calc(100% - 28px));margin:auto;padding:34px 0 70px}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:28px}}.brand{{font-weight:950;letter-spacing:.12em;font-size:13px;text-transform:uppercase}}.brand b{{color:var(--o)}}.nav{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}}.nav a{{font-size:11px;color:#a5adb4;text-transform:uppercase;font-weight:800;text-decoration:none}}.nav a:hover{{color:white}}
.hero{{position:relative;overflow:hidden;border:1px solid var(--line);border-left:4px solid var(--o);border-radius:22px;padding:34px;background:linear-gradient(145deg,#151a20,#0b0e12 70%);box-shadow:0 24px 70px rgba(0,0,0,.26)}}.hero:after{{content:"P1";position:absolute;right:-8px;bottom:-54px;font-size:220px;font-weight:1000;font-style:italic;line-height:1;color:rgba(255,255,255,.025)}}.eyebrow{{position:relative;z-index:1;color:var(--o2);font-size:10px;font-weight:950;letter-spacing:.18em;text-transform:uppercase}}h1{{position:relative;z-index:1;font-size:clamp(43px,8vw,82px);font-style:italic;letter-spacing:-.06em;line-height:.88;margin:9px 0 14px;text-transform:uppercase}}h2{{margin:0 0 14px;font-size:20px}}h3{{margin:0 0 7px;font-size:14px}}p{{color:#a6adb4;line-height:1.6}}.lead{{position:relative;z-index:1;max-width:760px;font-size:16px}}.actions{{position:relative;z-index:1;display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}}.btn{{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:10px;border:1px solid var(--line);background:#171b20;color:white;text-decoration:none;font-size:10px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}}.btn.primary{{background:var(--o);border-color:var(--o)}}.btn:hover{{filter:brightness(1.1)}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}}.kpi{{padding:16px;border:1px solid var(--line);border-radius:14px;background:#0d1115}}.kpi span{{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.12em;font-weight:800}}.kpi strong{{display:block;font-size:30px;margin-top:4px}}.kpi small{{color:#6f7981}}
.grid{{display:grid;grid-template-columns:1.35fr .65fr;gap:14px;margin-top:14px}}.panel{{border:1px solid var(--line);border-radius:18px;background:linear-gradient(160deg,#11161b,#0d1115);padding:22px}}.muted{{color:var(--muted);font-size:12px}}.orange{{color:var(--o2)}}
.podium{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px;align-items:end}}.pod{{position:relative;min-height:155px;padding:18px;border:1px solid var(--line);border-radius:16px;background:#0b0f13;overflow:hidden}}.pod.p1{{min-height:182px;border-color:rgba(255,85,0,.45);background:linear-gradient(180deg,rgba(255,85,0,.09),#0b0f13)}}.pod .p{{font-size:34px;font-weight:1000;font-style:italic;color:var(--o)}}.pod .n{{font-weight:900;margin-top:9px}}.pod .q{{font-size:28px;font-weight:1000;margin-top:12px}}.pod small{{display:block;color:var(--muted);text-transform:uppercase;font-size:8px;letter-spacing:.1em}}
.standings{{display:grid;gap:8px}}.row{{display:grid;grid-template-columns:58px 1fr 94px;align-items:center;gap:10px;padding:13px;border:1px solid var(--line);border-radius:12px;background:#0b0f13}}.pos{{font-size:23px;font-weight:1000;font-style:italic;color:var(--o2)}}.name{{font-weight:850}}.count{{text-align:right;font-size:22px;font-weight:1000}}.count small{{display:block;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.09em}}.tag{{display:inline-block;padding:4px 7px;border-radius:999px;background:rgba(255,85,0,.08);color:#ff9d70;font-size:8px;font-weight:900;letter-spacing:.07em;text-transform:uppercase;margin-top:4px}}
.steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.step{{padding:18px;border:1px solid var(--line);border-radius:14px;background:#0b0f13}}.step .num{{font-size:28px;font-weight:1000;color:var(--o)}}.prizes{{display:grid;gap:9px}}.prize{{padding:14px;border:1px solid var(--line);border-radius:12px;background:#0b0f13}}.prize strong{{display:block;color:var(--o2)}}
.linkbox{{padding:14px;border:1px solid rgba(255,85,0,.35);border-radius:12px;background:rgba(255,85,0,.055);word-break:break-all;font:700 12px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;color:#ffd1bc}}.sharecopy{{white-space:pre-wrap;padding:14px;border:1px dashed rgba(255,255,255,.15);border-radius:12px;background:#090c0f;color:#d6dade;font-size:12px;line-height:1.55}}.progress{{height:11px;border-radius:999px;background:#080a0d;border:1px solid var(--line);overflow:hidden}}.progress>span{{display:block;height:100%;background:linear-gradient(90deg,var(--o),#ff8d55)}}
form{{display:grid;gap:12px}}label{{font-size:10px;color:#aeb5bb;font-weight:850;letter-spacing:.05em;text-transform:uppercase}}input,select,textarea{{width:100%;margin-top:6px;padding:12px;border-radius:9px;border:1px solid var(--line);background:#090c10;color:white}}textarea{{min-height:90px;resize:vertical}}.checks{{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}}.check{{display:flex;align-items:center;gap:7px;border:1px solid var(--line);border-radius:9px;padding:10px;background:#0b0f13;font-size:12px;color:#d9dcdf;text-transform:none;letter-spacing:0}}.check input{{width:auto;margin:0}}
table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:#818a93;font-size:8px;text-transform:uppercase;letter-spacing:.08em}}details{{margin-top:9px}}summary{{cursor:pointer;color:#d9dcdf;font-weight:800}}.tester{{padding:18px;border:1px solid var(--line);border-radius:16px;background:#0b0f13;margin-top:11px}}.testerhead{{display:flex;justify-content:space-between;gap:12px;align-items:start}}.testerlinks{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:13px}}.linklabel{{font-size:8px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:5px}}
.footer{{margin-top:22px;padding-top:18px;border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#707980;font-size:10px;text-transform:uppercase;letter-spacing:.08em}}
@media(max-width:780px){{.grid,.steps,.podium,.testerlinks,.kpis{{grid-template-columns:1fr}}.pod,.pod.p1{{min-height:auto}}.top{{align-items:flex-start;flex-direction:column}}.hero{{padding:24px}}.row{{grid-template-columns:48px 1fr 72px}}.checks{{grid-template-columns:1fr}}.testerhead{{flex-direction:column}}}}
</style></head><body><div class="wrap">{body}</div>{script}</body></html>""", headers={"Cache-Control":"no-store"})


def _standing_rows(rows: list[dict], *, include_zero: bool = True) -> str:
    shown = rows if include_zero else [r for r in rows if r["qualified"] > 0]
    if not shown:
        return '<p class="muted">No qualified referrals yet. First activated referral takes P1.</p>'
    return "".join(
        f'<div class="row"><div class="pos">P{r["position"]}</div><div><div class="name">{escape(r["display_name"])}</div><div class="tag">{escape(r.get("milestone") or "Founding Tester")}</div></div><div class="count">{r["qualified"]}<small>qualified</small></div></div>'
        for r in shown[:50]
    )


def _podium(rows: list[dict]) -> str:
    top = rows[:3]
    if not top:
        return '<p class="muted">The grid is forming.</p>'
    cards = []
    for i, r in enumerate(top):
        cls = "pod p1" if i == 0 else "pod"
        prize = "12 months" if i == 0 else ("6 months" if i == 1 else "3 months")
        cards.append(f'<div class="{cls}"><div class="p">P{r["position"]}</div><div class="n">{escape(r["display_name"])}</div><div class="q">{r["qualified"]}</div><small>qualified · {prize} top tier</small></div>')
    return "".join(cards)


def _prizes() -> str:
    return """
    <div class="prizes">
      <div class="prize"><strong>P1 · 12 MONTHS</strong><span class="muted">Highest paid PRT tier, free for one year.</span></div>
      <div class="prize"><strong>P2 · 6 MONTHS</strong><span class="muted">Highest paid PRT tier.</span></div>
      <div class="prize"><strong>P3 · 3 MONTHS</strong><span class="muted">Highest paid PRT tier.</span></div>
      <div class="prize"><strong>5 + 10 QUALIFIED</strong><span class="muted">Founder’s Race milestone recognition and bragging rights.</span></div>
    </div>"""


@router.get("/founders-race", response_class=HTMLResponse, include_in_schema=False)
def founders_race_public():
    rows = leaderboard()
    q = sum(r["qualified"] for r in rows)
    p = sum(r["pending"] for r in rows)
    body = f"""
    <div class="top"><div class="brand">PITMARK RACING TOOLS <b>FOUNDER’S RACE</b></div><div class="nav"><a href="#standings">Standings</a><a href="#how">How it works</a><a href="#prizes">Prizes</a><a href="/prt">PRT Home</a></div></div>
    <section class="hero"><div class="eyebrow">EARLY ACCESS REFERRAL CHAMPIONSHIP · GREEN FLAG</div><h1>BRING<br>THE GRID.</h1><p class="lead">PRT’s founding testers are racing to grow the Early Access field. Recruit a racer, get them approved, get them activated — and move up the board.</p><div class="actions"><a class="btn primary" href="/prt/apply">Join Early Access</a><a class="btn" href="#standings">View the grid</a></div></section>
    <div class="kpis"><div class="kpi"><span>Founding Testers</span><strong>{len(rows)}</strong><small>eligible racers</small></div><div class="kpi"><span>Qualified</span><strong>{q}</strong><small>activated referrals</small></div><div class="kpi"><span>Pending</span><strong>{p}</strong><small>working through the pipeline</small></div><div class="kpi"><span>Finish Line</span><strong>v1.0</strong><small>first public release</small></div></div>
    <section class="panel"><div class="eyebrow">THE PODIUM</div><h2>Championship leaders</h2><div class="podium">{_podium(rows)}</div></section>
    <div class="grid" id="standings"><section class="panel"><div class="eyebrow">LIVE TIMING</div><h2>Starting Grid</h2><p class="muted">Every eligible founding tester is on the board. First qualified activation takes the lead.</p><div class="standings">{_standing_rows(rows)}</div></section><aside class="panel" id="prizes"><div class="eyebrow">WHAT’S ON THE LINE</div><h2>Prizes</h2>{_prizes()}<p class="muted">Rewards are verified at the finish. Founder’s Race does not bypass normal PRT pricing or entitlement controls.</p></aside></div>
    <section class="panel" id="how" style="margin-top:14px"><div class="eyebrow">HOW TO SCORE</div><h2>Clicks don’t count. Racers do.</h2><div class="steps"><div class="step"><div class="num">01</div><h3>Share your link</h3><p>Each Early Access tester gets a unique Founder’s Race recruit link.</p></div><div class="step"><div class="num">02</div><h3>They earn approval</h3><p>The racer applies through your link and goes through the normal Early Access review.</p></div><div class="step"><div class="num">03</div><h3>They activate PRT</h3><p>Your point becomes qualified only after the invite is redeemed and PRT is activated on a real device.</p></div></div></section>
    <section class="panel" style="margin-top:14px"><div class="eyebrow">RACE CONTROL</div><h2>Clean racing only.</h2><p>Self-referrals, duplicate applications, duplicate referred emails, and inactive testers do not score. Pitmark verifies the final board before rewards are issued. The race ends when PRT leaves Early Access for its first public release.</p></section>
    <div class="footer"><span>PRT Founder’s Race · Pitmark Racing Co.</span><span>Leave your mark.</span></div>
    """
    return _shell("PRT Founder’s Race", body)


@router.get("/founders-race/t/{code}", response_class=HTMLResponse, include_in_schema=False)
def founder_tester_hub(code: str):
    card = referrer_card(code)
    if card is None:
        return RedirectResponse(url="/founders-race", status_code=302)
    code_e = escape(card["referral_code"])
    name_e = escape(card["display_name"])
    recruit = f"{CANONICAL}/founders-race/r/{card['referral_code']}"
    hub = f"{CANONICAL}/founders-race/t/{card['referral_code']}"
    next_goal = card["next_milestone"] or 10
    pct = min(100, int((card["qualified"] / max(1, next_goal)) * 100))
    left = max(0, next_goal - card["qualified"])
    reward = "P1 · 12 months top tier" if card["position"] == 1 else ("P2 · 6 months top tier" if card["position"] == 2 else ("P3 · 3 months top tier" if card["position"] == 3 else "Chasing the podium"))
    social = f"I’m in the PRT Founder’s Race 🏁\n\nI’m helping build the Early Access grid for Pitmark Racing Tools. If you race iRacing and want to help shape PRT before public release, apply through my link:\n\n{recruit}\n\nLeave your mark."
    body = f"""
    <div class="top"><div class="brand">PITMARK RACING TOOLS <b>TESTER RACE HUB</b></div><div class="nav"><a href="/founders-race">Public Race</a><a href="/prt">PRT Home</a></div></div>
    <section class="hero"><div class="eyebrow">FOUNDING TESTER · {name_e}</div><h1>YOUR RACE.<br>YOUR LINK.</h1><p class="lead">Everything you need to run your Founder’s Race campaign is right here.</p><div class="actions"><button class="btn primary" data-copy="{escape(recruit, quote=True)}">Copy Recruit Link</button><button class="btn" data-share="{escape(recruit, quote=True)}" data-share-text="Join PRT Early Access through my Founder’s Race link.">Share</button><a class="btn" target="_blank" href="/founders-race/r/{code_e}">Open Recruit Page</a></div></section>
    <div class="kpis"><div class="kpi"><span>Position</span><strong>P{card["position"]}</strong><small>{escape(reward)}</small></div><div class="kpi"><span>Qualified</span><strong>{card["qualified"]}</strong><small>activated racers</small></div><div class="kpi"><span>Pending</span><strong>{card["pending"]}</strong><small>still in pipeline</small></div><div class="kpi"><span>Total Referred</span><strong>{card["total"]}</strong><small>all attributed apps</small></div></div>
    <div class="grid"><section class="panel"><div class="eyebrow">YOUR RECRUIT LINK</div><h2>Share this. This is what scores.</h2><div class="linkbox">{escape(recruit)}</div><div class="actions"><button class="btn primary" data-copy="{escape(recruit, quote=True)}">Copy Link</button><button class="btn" data-share="{escape(recruit, quote=True)}">Share Link</button></div><p class="muted">Your hub URL: {escape(hub)} · Referral code: {code_e}</p></section><aside class="panel"><div class="eyebrow">NEXT MILESTONE</div><h2>{left} to go</h2><p class="muted">{card["qualified"]} / {next_goal} qualified referrals</p><div class="progress"><span style="width:{pct}%"></span></div><p class="muted">Only approved, activated racers move this bar.</p></aside></div>
    <section class="panel" style="margin-top:14px"><div class="eyebrow">COPY + POST</div><h2>Ready-made social copy</h2><div class="sharecopy">{escape(social)}</div><div class="actions"><button class="btn primary" data-copy="{escape(social, quote=True)}">Copy Post</button></div></section>
    <section class="panel" style="margin-top:14px"><div class="eyebrow">HOW YOU SCORE</div><div class="steps"><div class="step"><div class="num">01</div><h3>Send the recruit link</h3><p>Your friend must apply through your personal link.</p></div><div class="step"><div class="num">02</div><h3>They get approved</h3><p>Pitmark reviews them normally. Approval alone is still pending.</p></div><div class="step"><div class="num">03</div><h3>They activate</h3><p>After invite redemption + device activation, your referral becomes qualified.</p></div></div></section>
    <div class="footer"><span>{name_e} · Founder’s Race Hub</span><span>Race clean. Bring the grid.</span></div>
    """
    return _shell(f"PRT Founder’s Race · {card['display_name']}", body)


@router.get("/founders-race/r/{code}", response_class=HTMLResponse, include_in_schema=False)
def founder_referral_page(code: str):
    card = referrer_card(code)
    if card is None:
        return RedirectResponse(url="/founders-race", status_code=302)
    code_e = escape(card["referral_code"])
    name_e = escape(card["display_name"])
    body = f"""
    <div class="top"><div class="brand">PITMARK RACING TOOLS <b>FOUNDER’S RACE</b></div><div class="nav"><a href="/founders-race">Standings</a><a href="/prt">PRT Home</a></div></div>
    <section class="hero"><div class="eyebrow">REFERRED BY {name_e}</div><h1>JOIN THE<br>EARLY GRID.</h1><p class="lead">You were invited into PRT Early Access by a founding tester. Apply below. If you’re approved and activate PRT, you’ll move {name_e} up the Founder’s Race board.</p></section>
    <div class="kpis"><div class="kpi"><span>Referrer</span><strong>P{card["position"]}</strong><small>{name_e}</small></div><div class="kpi"><span>Their Qualified</span><strong>{card["qualified"]}</strong><small>activated referrals</small></div><div class="kpi"><span>Status</span><strong>OPEN</strong><small>Early Access applications</small></div><div class="kpi"><span>Your Goal</span><strong>TEST</strong><small>race · report · improve</small></div></div>
    <div class="grid"><section class="panel"><div class="eyebrow">EARLY ACCESS APPLICATION</div><h2>Earn your spot on the grid</h2><form method="post" action="/founders-race/r/{code_e}/apply">
      <label>Full name<input name="full_name" maxlength="120" required></label><label>Email<input name="email" type="email" maxlength="200" required></label><label>iRacing display name<input name="iracing_name" maxlength="120" required></label><label>Discord username <span class="muted">optional</span><input name="discord_username" maxlength="100"></label>
      <label>Disciplines</label><div class="checks"><label class="check"><input type="checkbox" name="disciplines" value="Oval"> Oval</label><label class="check"><input type="checkbox" name="disciplines" value="Sports Car"> Sports Car</label><label class="check"><input type="checkbox" name="disciplines" value="Formula"> Formula</label><label class="check"><input type="checkbox" name="disciplines" value="Dirt Oval"> Dirt Oval</label><label class="check"><input type="checkbox" name="disciplines" value="Dirt Road"> Dirt Road</label></div>
      <label>How often do you race?<select name="race_frequency" required><option value="">Choose one</option><option>Daily</option><option>Several times a week</option><option>Weekly</option><option>A few times a month</option></select></label><label>Current tools <span class="muted">optional</span><input name="current_tools" maxlength="320"></label><label>What would make PRT useful to you?<textarea name="goals" maxlength="1200"></textarea></label>
      <label class="check"><input type="checkbox" name="tester_agreement" value="yes" required> I can actively test PRT, report bugs, give honest feedback, and understand Early Access software may change.</label><input name="company_website" tabindex="-1" autocomplete="off" style="position:absolute;left:-10000px" aria-hidden="true"><button class="btn primary" type="submit">Apply Through {name_e}</button>
    </form></section><aside class="panel"><div class="eyebrow">WHAT HAPPENS NEXT</div><div class="steps" style="grid-template-columns:1fr"><div class="step"><div class="num">01</div><h3>Application review</h3><p>Pitmark reviews you for Early Access.</p></div><div class="step"><div class="num">02</div><h3>Activation invite</h3><p>If accepted, you get the normal PRT activation flow.</p></div><div class="step"><div class="num">03</div><h3>Go racing</h3><p>Activate PRT, use it in real sessions, and send useful feedback.</p></div></div></aside></div>
    """
    return _shell(f"PRT Founder’s Race · Referred by {card['display_name']}", body)


@router.post("/founders-race/r/{code}/apply", response_class=HTMLResponse, include_in_schema=False)
def founder_referred_apply(
    code: str, full_name: str = Form(...), email: str = Form(...), iracing_name: str = Form(...),
    discord_username: str = Form(default=""), disciplines: list[str] = Form(default=[]),
    race_frequency: str = Form(...), current_tools: str = Form(default=""), goals: str = Form(default=""),
    tester_agreement: str = Form(default=""), company_website: str = Form(default=""),
):
    card = referrer_card(code)
    if card is None:
        return RedirectResponse(url="/founders-race", status_code=302)
    if company_website.strip():
        return RedirectResponse(url="/founders-race", status_code=302)
    agreed = tester_agreement == "yes"
    try:
        result = submit_application(
            full_name=full_name, email=email, discord_username=discord_username, iracing_name=iracing_name,
            disciplines=", ".join(x.strip() for x in disciplines if x.strip())[:320], race_frequency=race_frequency,
            current_tools=current_tools, goals=goals, can_test=agreed, bug_reports=agreed, honest_feedback=agreed,
            expectations_agreed=agreed, campaign="founders_race_2026", source="tester_referral",
            asset=card["referral_code"], placement="founders-race",
        )
    except ValueError as exc:
        return _shell("PRT Founder’s Race · Application", f'<div class="top"><div class="brand">PITMARK RACING TOOLS <b>FOUNDER’S RACE</b></div></div><section class="panel"><h2>Application needs one fix</h2><p>{escape(str(exc))}</p><a class="btn primary" href="/founders-race/r/{escape(code)}">Go back</a></section>')
    attribution = {"credited": False, "reason": "duplicate_application"}
    if result.get("application_id") and not result.get("duplicate"):
        attribution = record_referral(referral_code=code, application_id=int(result["application_id"]), applicant_email=email, applicant_name=full_name)
    note = "Your application is in. If Pitmark approves you and you activate PRT, this referral becomes a qualified Founder’s Race result."
    if attribution.get("reason") == "self_referral":
        note = "Your application is in, but self-referrals do not score in the Founder’s Race."
    elif result.get("duplicate"):
        note = "We already have a recent application for this email, so a new referral was not added. Your existing application remains active."
    body = f'<div class="top"><div class="brand">PITMARK RACING TOOLS <b>FOUNDER’S RACE</b></div></div><section class="hero"><div class="eyebrow">APPLICATION RECEIVED</div><h1>YOU’RE IN<br>THE PIPELINE.</h1><p class="lead">{escape(note)}</p><div class="actions"><a class="btn primary" href="/founders-race">View the Race</a><a class="btn" href="/prt">Explore PRT</a></div></section>'
    return _shell("PRT Founder’s Race · Application received", body)


@router.get("/control/founders-race", response_class=HTMLResponse, include_in_schema=False)
def founders_race_admin(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    require_control_user(request, x_pitmark_admin_key)
    rows = leaderboard()
    qualified_total = sum(r["qualified"] for r in rows)
    pending_total = sum(r["pending"] for r in rows)
    flagged_total = sum(r["flagged"] for r in rows)
    cards = []
    for r in rows:
        recruit = f"{CANONICAL}/founders-race/r/{r['referral_code']}"
        hub = f"{CANONICAL}/founders-race/t/{r['referral_code']}"
        details = "".join(
            f'<tr><td>#{item["application_id"]}</td><td>{escape(item["applicant_name"])}</td><td>{escape(item["applicant_email"])}</td><td>{escape(item["state"])}</td><td>{escape(item["fraud_reason"] or "—")}</td></tr>'
            for item in r["referrals"]
        ) or '<tr><td colspan="5" class="muted">No referrals yet.</td></tr>'
        cards.append(f"""
        <div class="tester"><div class="testerhead"><div><div class="eyebrow">P{r['position']} · {escape(r['referral_code'])}</div><h2 style="margin-top:5px">{escape(r['display_name'])}</h2><div class="muted">{escape(r['email'])}</div></div><div class="kpis" style="margin:0;grid-template-columns:repeat(3,92px)"><div class="kpi"><span>Q</span><strong>{r['qualified']}</strong></div><div class="kpi"><span>Pending</span><strong>{r['pending']}</strong></div><div class="kpi"><span>Flagged</span><strong>{r['flagged']}</strong></div></div></div>
        <div class="testerlinks"><div><div class="linklabel">Recruit link — give this to racers</div><div class="linkbox">{escape(recruit)}</div><div class="actions"><button class="btn primary" data-copy="{escape(recruit, quote=True)}">Copy Recruit Link</button><a class="btn" target="_blank" href="/founders-race/r/{escape(r['referral_code'])}">Open</a></div></div><div><div class="linklabel">Tester Race Hub — give this to the tester</div><div class="linkbox">{escape(hub)}</div><div class="actions"><button class="btn primary" data-copy="{escape(hub, quote=True)}">Copy Hub Link</button><a class="btn" target="_blank" href="/founders-race/t/{escape(r['referral_code'])}">Open Hub</a></div></div></div>
        <details><summary>Referral audit ({r['total']})</summary><div style="overflow:auto"><table><thead><tr><th>App</th><th>Name</th><th>Email</th><th>State</th><th>Flag</th></tr></thead><tbody>{details}</tbody></table></div></details></div>""")
    body = f"""
    <div class="top"><div class="brand">PITMARK CONTROL <b>FOUNDER’S RACE</b></div><div class="nav"><a href="/control">Control Center</a><a target="_blank" href="/founders-race">Public Race</a><a href="/control/early-access">Early Access</a></div></div>
    <section class="hero"><div class="eyebrow">RACE CONTROL · PRIVATE ADMIN</div><h1>RUN<br>THE FIELD.</h1><p class="lead">Distribute tester hubs, copy recruit links, watch the pipeline, and audit anything suspicious.</p></section>
    <div class="kpis"><div class="kpi"><span>Eligible Testers</span><strong>{len(rows)}</strong></div><div class="kpi"><span>Qualified</span><strong>{qualified_total}</strong></div><div class="kpi"><span>Pending</span><strong>{pending_total}</strong></div><div class="kpi"><span>Flagged</span><strong>{flagged_total}</strong></div></div>
    <section class="panel"><div class="eyebrow">DISTRIBUTION</div><h2>Tester links + race hubs</h2><p class="muted">Recruit link = what the tester shares publicly. Tester Race Hub = their own campaign dashboard with copy/share tools and progress.</p>{''.join(cards) if cards else '<p class="muted">No eligible Early Access testers found yet.</p>'}</section>
    <div class="footer"><span>Founder’s Race Admin</span><span>Rewards remain subject to normal entitlement controls.</span></div>
    """
    return _shell("PRT Founder’s Race · Admin", body, admin=True)
