from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import RedirectResponse

from services.control_auth import require_control_user

router = APIRouter()


@router.get('/control/early-access', include_in_schema=False)
def early_access_admin(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    require_control_user(request, x_pitmark_admin_key)
    return RedirectResponse(url='/control#analytics', status_code=302, headers={'Cache-Control':'no-store'})
