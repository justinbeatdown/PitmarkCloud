from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from services.control_auth import require_control_user
from services.pitmark_mail_identities import send_message as send_mail
from services.prt_application_admin import delete_application, set_application_status
from services.prt_applications import list_applications
from services.prt_licensing_store import create_early_access_invite, list_early_access_invites

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
LEGACY_APPLICATIONS_URL = "https://docs.google.com/spreadsheets/d/1RkAGF91DM-xGEUrnS4c6sTNud_PUajsGKL5So2Bybec/edit"
EASTERN = ZoneInfo("America/New_York")
PRT_URL = "https://prt.pitmarkracing.com/prt"


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
    if normalized == "accepted":
        return "good"
    if normalized == "hold":
        return "hold"
    if normalized == "declined":
        return "bad"
    return "new"


def _gmail_compose(email: str, name: str) -> str:
    query = urlencode(
        {
            "view": "cm",
            "fs": "1",
            "to": email,
            "su": "Pitmark Racing Tools Early Access",
            "body": f"Hi {name},\n\n",
        }
    )
    return f"https://mail.google.com/mail/?{query}"


def _acceptance_message(name: str, code: str) -> str:
    first = (name or "there").strip().split()[0]
    return f"""Hey {first},

You’ve been accepted into Pitmark Racing Tools Early Access.

PRT is still actively being developed, and that’s exactly why we want real iRacing drivers involved now. You’ll be helping us test features in actual race conditions, find bugs, and shape what PRT becomes before the public release.

Get started:
{PRT_URL}

Your Early Access code:
{code}

Install the latest PRT Early Access build from the link above, open PRT, go to Settings → Access & Licensing → PRT Early Access, paste the code, and choose ACTIVATE EARLY ACCESS. Your code is personal and binds to your PRT device when activated.

Once you’re installed, get some laps in and use PRT like you normally would during practice, qualifying, and races. We especially want feedback on:

• Overlay accuracy and responsiveness
• Radar / nearby-car behavior
• RPM, inputs, steering and telemetry
• Standings and race information
• Setup/install problems
• Anything confusing, broken, laggy, or just annoying
• Features you wish were there

Don’t worry about giving us polished feedback. Screenshots, quick messages, bug reports, or even “this feels weird” are useful.

Early Access is meant to be collaborative. Things may change quickly between builds as feedback comes in, and testers are directly influencing those changes.

After you activate PRT, we’ll also automatically send you your personal Founder’s Race Hub. That gives you your referral link, standings, milestones, and everything you need if you want to recruit other racers into Early Access.

Thanks for getting involved this early. We’re building PRT around actual racers instead of guessing what racers want.

Welcome aboard.

--
Justin Olson
Founder & Owner | Pitmark Racing Co.

🏁 Leave your mark.
{PRT_URL}
"""


def _application_by_id(application_id: int) -> dict | None:
    return next((row for row in list_applications(limit=500) if int(row.get("id") or 0) == int(application_id)), None)


def _has_invite_for_email(email: str) -> bool:
    needle = (email or "").strip().lower()
    if not needle:
        return False
    return any(
        (row.get("email") or "").strip().lower() == needle
        and (row.get("status") or "").strip().lower() not in {"revoked", "expired"}
        for row in list_early_access_invites(limit=500)
    )


def _application_cards(rows: list[dict]) -> str:
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
        raw_email = row.get("email") or ""
        email = escape(raw_email)
        iracing = escape(row.get("iracing_name") or "Not provided")
        discord = escape(row.get("discord_username") or "Not provided")
        disciplines = escape(row.get("disciplines") or "Not provided")
        frequency = escape(row.get("race_frequency") or "Not provided")
        tools = escape(row.get("current_tools") or "Not provided")
        goals = escape(row.get("goals") or "No additional notes provided.")
        source = escape(row.get("source") or "website")
        asset = escape(row.get("asset") or "")
        raw_status = (row.get("status") or "new").strip().lower()
        status = escape(raw_status)
        application_id = int(row.get("id") or 0)
        submitted = _submitted_label(row.get("created_at"))
        status_class = _status_class(status)
        source_label = source if not asset else f"{source} · {asset}"
        gmail_url = escape(_gmail_compose(raw_email, row.get("full_name") or "there"), quote=True)
        acceptance_action = ""
        if raw_status == "accepted":
            acceptance_action = f"""
              <form method="post" action="/control/early-access/{application_id}/send-acceptance">
                <button class="btn accept-mail" type="submit">SEND ACCEPTANCE EMAIL</button>
              </form>
            """

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
                <div class="app-actions">{acceptance_action}</div>
              </div>

              <div class="app-grid">
                <section><span class="label">iRACING</span><strong>{iracing}</strong></section>
                <section><span class="label">DISCORD</span><strong>{discord}</strong></section>
                <section><span class="label">RACES</span><strong>{frequency}</strong></section>
                <section><span class="label">SOURCE</span><strong>{source_label}</strong></section>
              </div>

              <div class="detail-grid">
                <section><span class="label">DISCIPLINES</span><p>{disciplines}</p></section>
                <section><span class="label">CURRENT TOOLS</span><p>{tools}</p></section>
              </div>

              <section class="goal-box">
                <span class="label">WHAT WOULD MAKE PRT USEFUL?</span>
                <p>{goals}</p>
              </section>

              <section class="decision-bar">
                <div class="decision-copy"><span class="label">REVIEW ACTION</span><p>Accept first, then use Send Acceptance Email to issue a fresh PRT code and send the full onboarding message directly through Pitmark Mail.</p></div>
                <div class="decision-actions">
                  <form method="post" action="/control/early-access/{application_id}/status"><input type="hidden" name="status" value="accepted"><button class="action-btn accept" type="submit">ACCEPT</button></form>
                  <form method="post" action="/control/early-access/{application_id}/status"><input type="hidden" name="status" value="hold"><button class="action-btn hold" type="submit">HOLD</button></form>
                  <form method="post" action="/control/early-access/{application_id}/status"><input type="hidden" name="status" value="declined"><button class="action-btn decline" type="submit">DECLINE</button></form>
                  <form method="post" action="/control/early-access/{application_id}/status"><input type="hidden" name="status" value="new"><button class="action-btn neutral" type="submit">MARK NEW</button></form>
                </div>
              </section>

              <div class="app-footer">
                <a href="mailto:{email}">{email}</a>
                <div class="footer-tools">
                  <span>APPLICATION #{application_id}</span>
                  <details class="delete-menu">
                    <summary>DELETE</summary>
                    <div class="delete-popover">
                      <strong>Permanently delete this application?</strong>
                      <p>This removes the Quick Apply record from PitmarkDB. It cannot be undone.</p>
                      <form method="post" action="/control/early-access/{application_id}/delete">
                        <label class="confirm-check"><input type="checkbox" name="confirm" value="yes" required> I understand this permanently deletes it.</label>
                        <button class="action-btn danger" type="submit">DELETE APPLICATION</button>
                      </form>
                    </div>
                  </details>
                </div>
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
    accepted_count = sum(1 for row in applications if (row.get("status") or "").strip().lower() == "accepted")
    hold_count = sum(1 for row in applications if (row.get("status") or "").strip().lower() == "hold")
    notice = ""
    if request.query_params.get("sent") == "1":
        notice = '<div class="notice good">Acceptance email sent and a fresh PRT Early Access code was issued.</div>'
    elif request.query_params.get("error") == "invite-exists":
        notice = '<div class="notice bad">This applicant already has an active Early Access invite. No second code or duplicate email was sent.</div>'
    elif request.query_params.get("error") == "mail":
        notice = '<div class="notice bad">The acceptance email could not be sent. Check Pitmark Mail / Gmail credentials before trying again.</div>'
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#090b0e">
<title>PRT Applicants · Pitmark Control Center</title>
<link rel="icon" href="/control-favicon.png">
<style>
:root{{--orange:#ff5500;--orange2:#ff7431;--bg:#080a0c;--panel:#111419;--panel2:#171b20;--line:rgba(255,255,255,.085);--text:#f4f5f5;--muted:#848d96;--good:#55dc89;--bad:#ff7676;--hold:#f3bb55}}
*{{box-sizing:border-box}}
html,body{{margin:0;min-height:100%;background:linear-gradient(180deg,#090b0e,#07090b 74%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
body:before{{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 74% 8%,rgba(255,85,0,.08),transparent 28%);opacity:.8}}
a{{color:inherit}}button,input{{font:inherit}}form{{margin:0}}
.shell{{position:relative;z-index:1;min-height:100vh}}
.topbar{{height:76px;padding:0 28px;border-bottom:1px solid var(--line);background:rgba(8,10,12,.94);display:flex;align-items:center;justify-content:space-between;gap:20px;position:sticky;top:0;z-index:20;backdrop-filter:blur(16px)}}
.brand{{display:flex;align-items:center;gap:16px;min-width:0}}.brand img{{width:154px;height:auto;display:block}}.brand-divider{{width:1px;height:32px;background:var(--line)}}.brand-copy small{{display:block;color:var(--orange2);font-size:9px;font-weight:900;letter-spacing:.15em;text-transform:uppercase}}.brand-copy strong{{display:block;margin-top:3px;font-size:16px;letter-spacing:-.01em}}
.top-actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:9px 13px;border-radius:9px;border:1px solid rgba(255,85,0,.46);background:rgba(255,85,0,.11);color:#ff854e!important;text-decoration:none!important;font-size:9px;font-weight:900;letter-spacing:.07em;text-transform:uppercase;cursor:pointer}}.btn:hover{{background:rgba(255,85,0,.18)}}.btn.secondary{{border-color:var(--line);background:#14181d;color:#dce0e3!important}}.btn.secondary:hover{{border-color:rgba(255,255,255,.17);background:#181d22}}.btn.accept-mail{{border-color:rgba(85,220,137,.38);background:rgba(85,220,137,.09);color:#76e69f!important}}
main{{width:min(1260px,calc(100% - 40px));margin:0 auto;padding:48px 0 72px}}
.page-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:28px;margin-bottom:24px}}.eyebrow{{color:var(--orange2);font-size:10px;font-weight:900;letter-spacing:.16em;text-transform:uppercase}}h1{{margin:6px 0 7px;font-size:clamp(34px,5vw,58px);line-height:.96;letter-spacing:-.045em;font-style:italic}}.page-head p{{margin:0;color:#949ca4;max-width:660px;line-height:1.55}}.live{{display:inline-flex;align-items:center;gap:7px;color:#7f8991;font-size:10px;white-space:nowrap}}.live:before{{content:"";width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 10px rgba(85,220,137,.5)}}
.notice{{margin:0 0 18px;padding:14px 16px;border:1px solid var(--line);border-radius:11px;background:#0d1115;font-size:10px;font-weight:800}}.notice.good{{border-color:rgba(85,220,137,.35);color:#9becb8}}.notice.bad{{border-color:rgba(255,118,118,.35);color:#ff9c9c}}
.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:28px}}.metric{{border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,#12161b,#0d1014);padding:18px 19px;min-height:102px}}.metric span{{display:block;color:#7e8790;font-size:9px;font-weight:850;letter-spacing:.11em;text-transform:uppercase}}.metric strong{{display:block;margin-top:6px;font-size:31px;line-height:1;letter-spacing:-.04em}}.metric p{{margin:6px 0 0;color:#737c85;font-size:10px;line-height:1.4}}.metric.accent{{border-left:2px solid var(--orange)}}
.section-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:34px 1px 12px}}.section-head h2{{margin:0;font-size:16px;letter-spacing:-.015em}}.section-head span{{color:#727b84;font-size:10px}}
.app-list{{display:grid;gap:12px}}.app-card{{border:1px solid var(--line);border-radius:16px;background:linear-gradient(145deg,#12161b,#0d1014);overflow:visible;box-shadow:0 16px 34px rgba(0,0,0,.16)}}.app-card-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 19px;border-bottom:1px solid var(--line)}}.identity{{display:flex;align-items:center;gap:12px;min-width:0}}.avatar{{display:grid;place-items:center;width:42px;height:42px;border-radius:12px;background:rgba(255,85,0,.13);border:1px solid rgba(255,85,0,.22);color:#ff854e;font-size:17px;font-weight:900;flex:0 0 auto}}.name-row{{display:flex;align-items:center;gap:9px;flex-wrap:wrap}}.name-row h2{{margin:0;font-size:18px;letter-spacing:-.02em}}.identity p{{margin:4px 0 0;color:#737c84;font-size:10px}}.status{{display:inline-flex;padding:4px 7px;border-radius:999px;border:1px solid rgba(255,116,49,.25);background:rgba(255,85,0,.08);color:#ff854e;font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}}.status.good{{border-color:rgba(85,220,137,.24);background:rgba(85,220,137,.07);color:var(--good)}}.status.hold{{border-color:rgba(243,187,85,.28);background:rgba(243,187,85,.08);color:var(--hold)}}.status.bad{{border-color:rgba(255,118,118,.25);background:rgba(255,118,118,.07);color:var(--bad)}}
.app-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-bottom:1px solid var(--line)}}.app-grid section{{padding:15px 18px;border-right:1px solid var(--line);min-width:0}}.app-grid section:last-child{{border-right:0}}.label{{display:block;color:#737c84;font-size:8px;font-weight:900;letter-spacing:.11em;text-transform:uppercase}}.app-grid strong{{display:block;margin-top:5px;color:#e7e9e9;font-size:11px;line-height:1.35;overflow-wrap:anywhere}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--line)}}.detail-grid section{{padding:15px 18px}}.detail-grid section:first-child{{border-right:1px solid var(--line)}}.detail-grid p,.goal-box p{{margin:6px 0 0;color:#a4abb1;font-size:11px;line-height:1.55}}
.goal-box{{padding:16px 18px;background:rgba(255,255,255,.012);border-bottom:1px solid var(--line)}}
.decision-bar{{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 18px;background:#0b0e12;border-bottom:1px solid var(--line)}}.decision-copy p{{margin:5px 0 0;color:#717a82;font-size:9px;line-height:1.45}}.decision-actions{{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}}.action-btn{{min-height:32px;padding:8px 11px;border-radius:8px;border:1px solid var(--line);background:#15191e;color:#d9dddf;font-size:8px;font-weight:900;letter-spacing:.07em;cursor:pointer}}.action-btn:hover{{filter:brightness(1.12)}}.action-btn.accept{{border-color:rgba(85,220,137,.3);background:rgba(85,220,137,.08);color:#73e89d}}.action-btn.hold{{border-color:rgba(243,187,85,.3);background:rgba(243,187,85,.08);color:#f6c66f}}.action-btn.decline,.action-btn.danger{{border-color:rgba(255,118,118,.3);background:rgba(255,118,118,.08);color:#ff8d8d}}.action-btn.neutral{{color:#949ca4}}
.app-footer{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 18px;color:#69727a;font-size:9px;border-radius:0 0 16px 16px}}.app-footer>a{{color:#98a0a6;text-decoration:none}}.app-footer>a:hover{{color:#ff854e}}.footer-tools{{display:flex;align-items:center;gap:12px}}.footer-tools>span{{font-weight:850;letter-spacing:.06em}}.delete-menu{{position:relative}}.delete-menu summary{{list-style:none;cursor:pointer;color:#7b838a;font-weight:900;letter-spacing:.07em}}.delete-menu summary::-webkit-details-marker{{display:none}}.delete-menu[open] summary{{color:#ff8d8d}}.delete-popover{{position:absolute;right:0;bottom:24px;width:300px;padding:14px;border:1px solid rgba(255,118,118,.25);border-radius:12px;background:#111419;box-shadow:0 18px 44px rgba(0,0,0,.48);z-index:30}}.delete-popover strong{{display:block;color:#f4f5f5;font-size:11px}}.delete-popover p{{margin:6px 0 10px;color:#8b949b;font-size:9px;line-height:1.45}}.confirm-check{{display:flex;align-items:flex-start;gap:7px;color:#a6adb3;font-size:9px;line-height:1.4;margin-bottom:10px}}.confirm-check input{{margin-top:1px;accent-color:#ff6a25}}
.empty-state{{display:grid;place-items:center;text-align:center;min-height:260px;border:1px dashed rgba(255,255,255,.12);border-radius:16px;background:#0d1014;color:#848d96;padding:30px}}.empty-state .empty-icon{{font-size:28px;margin-bottom:8px}}.empty-state strong{{color:#e5e7e7;font-size:16px}}.empty-state span{{margin-top:6px;font-size:11px}}
.transition-note{{margin-top:18px;padding:15px 17px;border:1px solid var(--line);border-radius:12px;background:#0d1014;color:#78818a;font-size:10px;line-height:1.55}}.transition-note b{{color:#aab1b7}}
@media(max-width:900px){{.metrics{{grid-template-columns:1fr 1fr}}.decision-bar{{align-items:flex-start;flex-direction:column}}.decision-actions{{justify-content:flex-start}}}}
@media(max-width:820px){{.topbar{{height:auto;padding:13px 15px;align-items:flex-start}}.brand-divider,.brand-copy{{display:none}}.brand img{{width:130px}}main{{width:min(100% - 28px,1260px);padding-top:30px}}.page-head{{display:block}}.live{{margin-top:12px}}.app-grid{{grid-template-columns:1fr 1fr}}.app-grid section:nth-child(2){{border-right:0}}.app-grid section:nth-child(-n+2){{border-bottom:1px solid var(--line)}}.detail-grid{{grid-template-columns:1fr}}.detail-grid section:first-child{{border-right:0;border-bottom:1px solid var(--line)}}}}
@media(max-width:540px){{.metrics{{grid-template-columns:1fr}}.top-actions .btn.secondary{{display:none}}.page-head h1{{font-size:38px}}.app-card-head{{align-items:flex-start}}.app-actions{{display:block}}.app-grid{{grid-template-columns:1fr}}.app-grid section{{border-right:0!important;border-bottom:1px solid var(--line)}}.app-grid section:last-child{{border-bottom:0}}.app-footer{{align-items:flex-start;flex-direction:column}}.footer-tools{{width:100%;justify-content:space-between}}.decision-actions form{{flex:1}}.decision-actions .action-btn{{width:100%}}.delete-popover{{left:0;right:auto;width:min(300px,calc(100vw - 46px))}}}}
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
      <p>Review, contact, sort and remove Quick Apply applicants without leaving Control Center.</p>
    </div>
    <span class="live">QUICK APPLY LIVE</span>
  </section>

  {notice}

  <section class="metrics">
    <article class="metric accent"><span>Total Applicants</span><strong>{native_count}</strong><p>Native Quick Apply records.</p></article>
    <article class="metric"><span>Needs Review</span><strong>{new_count}</strong><p>Applications currently marked new.</p></article>
    <article class="metric"><span>Accepted</span><strong>{accepted_count}</strong><p>Applicants approved for the next onboarding step.</p></article>
    <article class="metric"><span>On Hold</span><strong>{hold_count}</strong><p>Applicants intentionally parked for later.</p></article>
  </section>

  <div class="section-head"><h2>Applicants</h2><span>Newest first</span></div>
  <section class="app-list">{_application_cards(applications)}</section>

  <div class="transition-note"><b>Legacy intake is still available.</b> New applications should come through Quick Apply. The old Google Form stays linked above during the transition so the original responses remain easy to reach.</div>
</main>
</div>
</body>
</html>"""
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@router.post("/control/early-access/{application_id}/status", include_in_schema=False)
def update_early_access_status(
    application_id: int,
    request: Request,
    status: str = Form(...),
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    try:
        set_application_status(application_id, status)
    except (ValueError, LookupError):
        return RedirectResponse(url="/control/early-access?error=status", status_code=303)
    return RedirectResponse(url="/control/early-access?updated=1", status_code=303)


@router.post("/control/early-access/{application_id}/send-acceptance", include_in_schema=False)
def send_early_access_acceptance(
    application_id: int,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    row = _application_by_id(application_id)
    if not row:
        return RedirectResponse(url="/control/early-access?error=missing", status_code=303)
    if (row.get("status") or "").strip().lower() != "accepted":
        return RedirectResponse(url="/control/early-access?error=status", status_code=303)

    email = (row.get("email") or "").strip().lower()
    name = (row.get("full_name") or "Applicant").strip()
    if not email:
        return RedirectResponse(url="/control/early-access?error=mail", status_code=303)
    if _has_invite_for_email(email):
        return RedirectResponse(url="/control/early-access?error=invite-exists", status_code=303)

    invite = create_early_access_invite(
        applicant_name=name,
        email=email,
        discord=(row.get("discord_username") or "").strip(),
        notes=f"Issued from Applicant Center application #{application_id}",
        expires_days=14,
    )
    try:
        send_mail(
            to=[email],
            subject="You’re In — Welcome to PRT Early Access 🏁",
            text=_acceptance_message(name, invite["code"]),
            from_identity="justin",
        )
    except Exception:
        return RedirectResponse(url="/control/early-access?error=mail", status_code=303)
    return RedirectResponse(url="/control/early-access?sent=1", status_code=303)


@router.post("/control/early-access/{application_id}/delete", include_in_schema=False)
def delete_early_access_application(
    application_id: int,
    request: Request,
    confirm: str = Form(...),
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    if confirm != "yes":
        return RedirectResponse(url="/control/early-access?error=confirm", status_code=303)
    try:
        delete_application(application_id)
    except LookupError:
        return RedirectResponse(url="/control/early-access?error=missing", status_code=303)
    return RedirectResponse(url="/control/early-access?deleted=1", status_code=303)


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