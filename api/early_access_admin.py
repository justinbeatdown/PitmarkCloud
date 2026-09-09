from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse, Response

from services.control_auth import require_control_user
from services.prt_applications import list_applications

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
LEGACY_APPLICATIONS_URL = "https://docs.google.com/spreadsheets/d/1RkAGF91DM-xGEUrnS4c6sTNud_PUajsGKL5So2Bybec/edit"
EASTERN = ZoneInfo("America/New_York")


def _submitted_label(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "Submitted recently"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(EASTERN)
        return dt.strftime("%b %-d, %Y · %-I:%M %p ET")
    except Exception:
        return escape(raw.replace("T", " ")[:16])


def _status_class(status: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"accepted", "approved", "active"}:
        return "good"
    if normalized in {"rejected", "declined"}:
        return "bad"
    return "new"


def _application_cards() -> str:
    rows = list_applications(limit=150)
    if not rows:
        return """
        <div class="empty-state">
          <div class="empty-icon">🏁</div>
          <strong>No Quick Apply applicants yet.</strong>
          <span>New PRT Early Access applications will show up here automatically.</span>
        </div>
        """

    cards: list[str] = []
    for row in rows:
        name = escape(row.get("full_name") or "Applicant")
        email = escape(row.get("email") or "")
        iracing = escape(row.get("iracing_name") or "Not provided")
        discord = escape(row.get("discord_username") or "Not provided")
        disciplines = escape(row.get("disciplines") or "Not provided")
        frequency = escape(row.get("race_frequency") or "Not provided")
        tools = escape(row.get("current_tools") or "Not provided")
        goals = escape(row.get("goals") or "No additional notes provided.")
        source = escape(row.get("source") or "website")
        asset = escape(row.get("asset") or "")
        status = escape(row.get("status") or "new")
        application_id = escape(str(row.get("id") or ""))
        submitted = _submitted_label(row.get("created_at"))
        status_class = _status_class(status)
        source_label = source if not asset else f"{source} · {asset}"

        cards.append(
            f"""
            <article class="app-card">
              <div class="app-card-head">
                <div class="identity">
                  <div class="avatar">{escape(name[:1].upper())}</div>
                  <div>
                    <div class="name-row"><h2>{name}</h2><span class="status {status_class}">{status}</span></div>
                    <p>{submitted}</p>
                  </div>
                </div>
                <div class="app-actions">
                  <a class="btn secondary" href="mailto:{email}">EMAIL APPLICANT</a>
                </div>
              </div>

              <div class="app-grid">
                <section>
                  <span class="label">iRACING</span>
                  <strong>{iracing}</strong>
                </section>
                <section>
                  <span class="label">DISCORD</span>
                  <strong>{discord}</strong>
                </section>
                <section>
                  <span class="label">RACES</span>
                  <strong>{frequency}</strong>
                </section>
                <section>
                  <span class="label">SOURCE</span>
                  <strong>{source_label}</strong>
                </section>
              </div>

              <div class="detail-grid">
                <section>
                  <span class="label">DISCIPLINES</span>
                  <p>{disciplines}</p>
                </section>
                <section>
                  <span class="label">CURRENT TOOLS</span>
                  <p>{tools}</p>
                </section>
              </div>

              <section class="goal-box">
                <span class="label">WHAT WOULD MAKE PRT USEFUL?</span>
                <p>{goals}</p>
              </section>

              <div class="app-footer">
                <a href="mailto:{email}">{email}</a>
                <span>APPLICATION #{application_id}</span>
              </div>
            </article>
            """
        )
    return "".join(cards)


@router.get("/control/early-access", include_in_schema=False)
def early_access_admin(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    applications = list_applications(limit=200)
    native_count = len(applications)
    new_count = sum(1 for row in applications if (row.get("status") or "new").strip().lower() == "new")
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b0e">
<title>PRT Applicants · Pitmark Control Center</title>
<link rel="icon" href="/control-favicon.png">
<style>
:root{{--orange:#ff5500;--orange2:#ff7431;--bg:#080a0c;--panel:#111419;--panel2:#171b20;--line:rgba(255,255,255,.085);--text:#f4f5f5;--muted:#848d96;--good:#55dc89;--bad:#ff7676}}
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;background:linear-gradient(180deg,#090b0e,#07090b 74%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 74% 8%,rgba(255,85,0,.08),transparent 28%);opacity:.8}}
a{{color:inherit}}
.shell{{position:relative;z-index:1;min-height:100vh}}
.topbar{{height:76px;padding:0 28px;border-bottom:1px solid var(--line);background:rgba(8,10,12,.94);display:flex;align-items:center;justify-content:space-between;gap:20px;position:sticky;top:0;z-index:20;backdrop-filter:blur(16px)}}
.brand{{display:flex;align-items:center;gap:16px;min-width:0}}.brand img{{width:154px;height:auto;display:block}}.brand-divider{{width:1px;height:32px;background:var(--line)}}.brand-copy small{{display:block;color:var(--orange2);font-size:9px;font-weight:900;letter-spacing:.15em;text-transform:uppercase}}.brand-copy strong{{display:block;margin-top:3px;font-size:16px;letter-spacing:-.01em}}
.top-actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:9px 13px;border-radius:9px;border:1px solid rgba(255,85,0,.46);background:rgba(255,85,0,.11);color:#ff854e!important;text-decoration:none!important;font-size:9px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}}.btn:hover{{background:rgba(255,85,0,.18)}}.btn.secondary{{border-color:var(--line);background:#14181d;color:#dce0e3!important}}.btn.secondary:hover{{border-color:rgba(255,255,255,.17);background:#181d22}}
main{{width:min(1260px,calc(100% - 40px));margin:0 auto;padding:48px 0 72px}}
.page-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:28px;margin-bottom:24px}}.eyebrow{{color:var(--orange2);font-size:10px;font-weight:900;letter-spacing:.16em;text-transform:uppercase}}h1{{margin:6px 0 7px;font-size:clamp(34px,5vw,58px);line-height:.96;letter-spacing:-.045em;font-style:italic}}.page-head p{{margin:0;color:#949ca4;max-width:660px;line-height:1.55}}.live{{display:inline-flex;align-items:center;gap:7px;color:#7f8991;font-size:10px;white-space:nowrap}}.live:before{{content:"";width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 10px rgba(85,220,137,.5)}}
.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:28px}}.metric{{border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,#12161b,#0d1014);padding:18px 19px;min-height:102px}}.metric span{{display:block;color:#7e8790;font-size:9px;font-weight:850;letter-spacing:.11em;text-transform:uppercase}}.metric strong{{display:block;margin-top:6px;font-size:31px;line-height:1;letter-spacing:-.04em}}.metric p{{margin:6px 0 0;color:#737c85;font-size:10px;line-height:1.4}}.metric.accent{{border-left:2px solid var(--orange)}}
.section-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:34px 1px 12px}}.section-head h2{{margin:0;font-size:16px;letter-spacing:-.015em}}.section-head span{{color:#727b84;font-size:10px}}
.app-list{{display:grid;gap:12px}}.app-card{{border:1px solid var(--line);border-radius:16px;background:linear-gradient(145deg,#12161b,#0d1014);overflow:hidden;box-shadow:0 16px 34px rgba(0,0,0,.16)}}.app-card-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 19px;border-bottom:1px solid var(--line)}}.identity{{display:flex;align-items:center;gap:12px;min-width:0}}.avatar{{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:rgba(255,85,0,.13);border:1px solid rgba(255,85,0,.22);color:#ff854e;font-size:17px;font-weight:900;flex:0 0 auto}}.name-row{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}.name-row h2{{margin:0;font-size:18px;letter-spacing:-.02em}}.identity p{{margin:4px 0 0;color:#737c84;font-size:10px}}.status{{display:inline-flex;padding:4px 7px;border-radius:999px;border:1px solid rgba(255,116,49,.25);background:rgba(255,85,0,.08);color:#ff854e;font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}.status.good{{border-color:rgba(85,220,137,.24);background:rgba(85,220,137,.07);color:var(--good)}}.status.bad{{border-color:rgba(255,118,118,.25);background:rgba(255,118,118,.07);color:var(--bad)}}
.app-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:1px solid var(--line)}}.app-grid section{{padding:15px 18px;border-right:1px solid var(--line);min-width:0}}.app-grid section:last-child{{border-right:0}}.label{{display:block;color:#737c84;font-size:8px;font-weight:900;letter-spacing:.11em;text-transform:uppercase}}.app-grid strong{{display:block;margin-top:5px;color:#e7e9e9;font-size:11px;line-height:1.35;overflow-wrap:anywhere}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--line)}}.detail-grid section{{padding:15px 18px}}.detail-grid section:first-child{{border-right:1px solid var(--line)}}.detail-grid p,.goal-box p{{margin:6px 0 0;color:#a4abb1;font-size:11px;line-height:1.55}}
.goal-box{{padding:16px 18px;background:rgba(255,255,255,.012)}}.app-footer{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 18px;border-top:1px solid var(--line);color:#69727a;font-size:9px}}.app-footer a{{color:#98a0a6;text-decoration:none}}.app-footer a:hover{{color:#ff854e}}.app-footer span{{font-weight:850;letter-spacing:.06em}}
.empty-state{{display:grid;place-items:center;text-align:center;min-height:260px;border:1px dashed rgba(255,255,255,.12);border-radius:16px;background:#0d1014;color:#848d96;padding:30px}}.empty-state .empty-icon{{font-size:28px;margin-bottom:8px}}.empty-state strong{{color:#e5e7e7;font-size:16px}}.empty-state span{{margin-top:6px;font-size:11px}}
.transition-note{{margin-top:18px;padding:15px 17px;border:1px solid var(--line);border-radius:12px;background:#0d1014;color:#78818a;font-size:10px;line-height:1.55}}.transition-note b{{color:#aab1b7}}
@media(max-width:820px){{.topbar{{height:auto;padding:13px 15px;align-items:flex-start}}.brand-divider,.brand-copy{{display:none}}.brand img{{width:130px}}main{{width:min(100% - 28px,1260px);padding-top:30px}}.page-head{{display:block}}.live{{margin-top:12px}}.metrics{{grid-template-columns:1fr}}.app-grid{{grid-template-columns:1fr 1fr}}.app-grid section:nth-child(2){{border-right:0}}.app-grid section:nth-child(-n+2){{border-bottom:1px solid var(--line)}}.detail-grid{{grid-template-columns:1fr}}.detail-grid section:first-child{{border-right:0;border-bottom:1px solid var(--line)}}}}
@media(max-width:540px){{.top-actions .btn.secondary{{display:none}}.page-head h1{{font-size:38px}}.app-card-head{{align-items:flex-start}}.app-actions{{display:none}}.app-grid{{grid-template-columns:1fr}}.app-grid section{{border-right:0!important;border-bottom:1px solid var(--line)}}.app-grid section:last-child{{border-bottom:0}}.app-footer{{align-items:flex-start;flex-direction:column}}}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar">
  <div class="brand">
    <img src="/control-logo-wide.png" alt="Pitmark Racing Co.">
    <span class="brand-divider"></span>
    <div class="brand-copy"><small>PRT EARLY ACCESS</small><strong>Applicant Center</strong></div>
  </div>
  <div class="top-actions">
    <a class="btn secondary" href="/control">← CONTROL CENTER</a>
    <a class="btn" href="{LEGACY_APPLICATIONS_URL}" target="_blank" rel="noopener noreferrer">LEGACY RESPONSES ↗</a>
  </div>
</header>

<main>
  <section class="page-head">
    <div>
      <span class="eyebrow">PRT TESTER PIPELINE</span>
      <h1>Early Access Applicants</h1>
      <p>Review the people asking to test PRT, understand what they race, then contact the right testers without digging through a spreadsheet.</p>
    </div>
    <span class="live">QUICK APPLY LIVE</span>
  </section>

  <section class="metrics">
    <article class="metric accent"><span>Quick Apply</span><strong>{native_count}</strong><p>Native PRT applications received.</p></article>
    <article class="metric"><span>Needs Review</span><strong>{new_count}</strong><p>Applications currently marked new.</p></article>
    <article class="metric"><span>Intake Sources</span><strong>2</strong><p>Quick Apply + legacy Google Form during transition.</p></article>
  </section>

  <div class="section-head"><h2>Applicants</h2><span>Newest first</span></div>
  <section class="app-list">{_application_cards()}</section>

  <div class="transition-note"><b>Legacy intake is still available.</b> New applications should come through Quick Apply. The old Google Form stays linked above during the transition so the original responses remain easy to reach.</div>
</main>
</div>
</body>
</html>"""
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@router.get("/links", response_class=HTMLResponse, include_in_schema=False)
def pitmark_links():
    return HTMLResponse(
        (ASSET_DIR / "links.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/links.css", include_in_schema=False)
def pitmark_links_css():
    return Response(
        (ASSET_DIR / "links.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )
