from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse, Response

from services.control_auth import require_control_user
from services.prt_applications import list_applications

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


def _application_rows() -> str:
    rows = list_applications(limit=150)
    if not rows:
        return '<tr><td colspan="8" class="empty">No native Quick Apply applications yet.</td></tr>'
    output: list[str] = []
    for row in rows:
        created = escape((row.get("created_at") or "").replace("T", " ")[:19])
        output.append(
            "<tr>"
            f"<td>{created}</td>"
            f"<td><b>{escape(row.get('full_name') or '')}</b><br><span>{escape(row.get('email') or '')}</span></td>"
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
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRT Early Access Applications</title>
<style>
:root{{--orange:#ff5500;--bg:#070808;--panel:#101212;--line:#303434;--text:#f3f2ed;--muted:#8f9696}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,Segoe UI,Arial,sans-serif}}
header{{padding:22px 28px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:18px}}
h1{{font-size:28px;margin:0;font-style:italic}}a{{color:#ff7837;text-decoration:none;font-weight:800}}main{{padding:24px 28px 60px;overflow:auto}}
.note{{max-width:900px;color:var(--muted);margin:0 0 20px}}table{{width:100%;border-collapse:collapse;min-width:1120px;background:var(--panel);border:1px solid var(--line)}}
th,td{{padding:12px 13px;border-bottom:1px solid #282c2c;text-align:left;vertical-align:top}}th{{font-size:10px;letter-spacing:.8px;color:#ff7837;background:#0b0d0d;position:sticky;top:0}}
td{{font-size:12px}}td span{{color:#7f8787;font-size:10px}}.empty{{padding:32px;text-align:center;color:var(--muted)}}.pill{{border:1px solid #743114;background:#211007;color:#ff7837;padding:6px 9px;font-size:10px;font-weight:900}}
</style>
</head>
<body>
<header><div><span class="pill">PRT QUICK APPLY</span><h1>Early Access Applications</h1></div><a href="/control#analytics">← CONTROL CENTER</a></header>
<main>
<p class="note">This page shows applications submitted through the new native PRT Quick Apply. The legacy Google Form remains separate during the transition. Application data is intentionally limited to what the applicant submits; the funnel does not store IP addresses, browser identifiers, referrers, or cookies.</p>
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
