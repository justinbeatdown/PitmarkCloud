from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse, Response

from services.control_auth import require_control_user
from services.prt_applications import list_applications

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
LEGACY_APPLICATIONS_URL = "https://docs.google.com/spreadsheets/d/1RkAGF91DM-xGEUrnS4c6sTNud_PUajsGKL5So2Bybec/edit"


def _application_rows() -> str:
    rows = list_applications(limit=150)
    if not rows:
        return '<tr><td colspan="8" class="empty">No native Quick Apply applications yet.</td></tr>'
    output: list[str] = []
    for row in rows:
        created = escape((row.get("created_at") or "").replace("T", " ")[:19])
        email = escape(row.get("email") or "")
        output.append(
            "<tr>"
            f"<td>{created}</td>"
            f"<td><b>{escape(row.get('full_name') or '')}</b><br><a class='email' href='mailto:{email}'>{email}</a></td>"
            f"<td>{escape(row.get('iracing_name') or '')}<br><span>{escape(row.get('discord_username') or '—')}</span></td>"
            f"<td>{escape(row.get('disciplines') or '')}</td>"
            f"<td>{escape(row.get('race_frequency') or '')}</td>"
            f"<td>{escape(row.get('goals') or '—')}</td>"
            f"<td>{escape(row.get('source') or 'website')}<br><span>{escape(row.get('asset') or '')}</span></td>"
            f"<td>{escape(row.get('status') or 'new')}</td>"
            "</tr>"
        )
    return "".join(output)


@router.get("/control/early-access", include_in_schema=False)
def early_access_admin(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    native_count = len(list_applications(limit=200))
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRT Early Access Applications</title>
<style>
:root{{--orange:#ff5500;--bg:#070808;--panel:#101212;--line:#303434;--text:#f3f2ed;--muted:#8f9696}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
header{{padding:22px 28px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap}}
h1{{font-size:28px;margin:0;font-style:italic}}a{{color:#ff7837;text-decoration:none;font-weight:800}}main{{padding:24px 28px 60px;overflow:auto}}
.header-actions,.source-actions{{display:flex;gap:9px;align-items:center;flex-wrap:wrap}}.action{{display:inline-flex;align-items:center;justify-content:center;padding:9px 12px;border:1px solid #5a5f5f;border-radius:5px;background:#111414;color:#eee;font-size:10px;letter-spacing:.55px;text-transform:uppercase}}.action.primary{{border-color:#a33c0e;background:#281208;color:#ff7837}}
.summary{{display:grid;grid-template-columns:minmax(180px,260px) minmax(260px,1fr);gap:12px;margin:0 0 18px}}.summary-card{{border:1px solid var(--line);border-left:2px solid var(--orange);background:var(--panel);padding:17px}}.summary-card span{{display:block;color:var(--muted);font-size:10px;letter-spacing:.7px;text-transform:uppercase}}.summary-card strong{{display:block;font-size:34px;margin-top:4px}}.summary-card p{{margin:6px 0 0;color:var(--muted);font-size:12px;max-width:720px}}
.note{{max-width:980px;color:var(--muted);margin:0 0 20px}}table{{width:100%;border-collapse:collapse;min-width:1120px;background:var(--panel);border:1px solid var(--line)}}
th,td{{padding:12px 13px;border-bottom:1px solid #282c2c;text-align:left;vertical-align:top}}th{{font-size:10px;letter-spacing:.8px;color:#ff7837;background:#0b0d0d;position:sticky;top:0}}
td{{font-size:12px}}td span{{color:#7f8787;font-size:10px}}td .email{{font-size:10px;color:#9fa6a6}}.empty{{padding:32px;text-align:center;color:var(--muted)}}.pill{{display:inline-block;border:1px solid #743114;background:#211007;color:#ff7837;padding:6px 9px;font-size:10px;font-weight:900}}
@media(max-width:720px){{header,main{{padding-left:15px;padding-right:15px}}.summary{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header>
  <div><span class="pill">PRT EARLY ACCESS</span><h1>Applicant Center</h1></div>
  <div class="header-actions"><a class="action" href="/control">← CONTROL CENTER</a><a class="action primary" href="{LEGACY_APPLICATIONS_URL}" target="_blank" rel="noopener noreferrer">LEGACY FORM RESPONSES ↗</a></div>
</header>
<main>
<div class="summary">
  <div class="summary-card"><span>Native Quick Apply</span><strong>{native_count}</strong><p>Applications submitted directly through the PRT website.</p></div>
  <div class="summary-card"><span>Two intake sources during transition</span><p>New Quick Apply submissions are listed below. The original Google Form responses are still available from the Legacy Form Responses button so nothing gets lost while we move the funnel over.</p></div>
</div>
<p class="note">This is the Control Center home for PRT Early Access applicants. New Quick Apply notifications link here directly. Use the applicant email to reply/follow up; accepted testers still receive their activation code and setup instructions through the normal PRT process.</p>
<table>
<thead><tr><th>SUBMITTED</th><th>APPLICANT</th><th>iRACING / DISCORD</th><th>DISCIPLINES</th><th>FREQUENCY</th><th>WHAT THEY WANT</th><th>SOURCE</th><th>STATUS</th></tr></thead>
<tbody>{_application_rows()}</tbody>
</table>
</main></body></html>"""
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
