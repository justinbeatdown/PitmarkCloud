from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from services.control_auth import require_control_user

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


@router.get('/control/early-access', include_in_schema=False)
def early_access_admin(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    return RedirectResponse(url='/control#analytics', status_code=302, headers={'Cache-Control':'no-store'})


@router.get('/links', response_class=HTMLResponse, include_in_schema=False)
def pitmark_links():
    return HTMLResponse(
        (ASSET_DIR / 'links.html').read_text(encoding='utf-8'),
        headers={'Cache-Control': 'no-store'},
    )


@router.get('/links.css', include_in_schema=False)
def pitmark_links_css():
    return Response(
        (ASSET_DIR / 'links.css').read_text(encoding='utf-8'),
        media_type='text/css',
        headers={'Cache-Control': 'no-store'},
    )
