from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from services import device_auth_service, discord_service
from utils.security import enforce_rate_limit, safe_html, validate_device_id

router = APIRouter()


@router.get("/status")
async def status() -> dict:
    return discord_service.status()


@router.get("/install")
async def install() -> dict:
    url = discord_service.install_url()
    if not url:
        raise HTTPException(status_code=503, detail="DISCORD_CLIENT_ID is not configured.")
    return {"install_url": url, "scope": ["bot", "applications.commands"], "permissions": "View Channels, Send Messages, Embed Links, Attach Files, Read Message History"}


@router.post("/link/start")
async def link_start(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-start", 20)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    try:
        return discord_service.create_link(device_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/link/status")
async def link_status(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-status", 120)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    return discord_service.link_status(device_id)


@router.post("/link/disconnect")
async def link_disconnect(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-disconnect", 30)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    return discord_service.disconnect(device_id)


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(request: Request, code: str = Query(..., min_length=1, max_length=4096), state: str = Query(..., min_length=10, max_length=4096)) -> HTMLResponse:
    enforce_rate_limit(request, "discord-oauth-callback", 60)
    try:
        result = await discord_service.complete_link(code, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result.status != "connected":
        return HTMLResponse(
            f"""<!doctype html><html><body style="background:#0b0c0d;color:#eee;font-family:Arial;padding:40px">
            <h1 style="color:#ff5500">Pitmark Discord Link Failed</h1>
            <p>{safe_html(result.error)}</p><p>You can close this window and return to Pitmark Racing Tools.</p>
            </body></html>""",
            status_code=400,
        )

    display = safe_html(result.global_name or result.username)
    return HTMLResponse(
        f"""<!doctype html><html><body style="background:#0b0c0d;color:#eee;font-family:Arial;padding:40px;text-align:center">
        <h1 style="color:#ff5500">Discord Connected</h1>
        <p>Pitmark Racing Tools is now linked to <strong>{display}</strong>.</p>
        <p>You can close this browser window and return to Pitmark.</p>
        <p style="color:#777">Leave Your Mark.</p>
        </body></html>"""
    )
