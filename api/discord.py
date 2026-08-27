from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from services import discord_service

router = APIRouter()


@router.get("/status")
async def status() -> dict:
    return discord_service.status()


@router.post("/link/start")
async def link_start(device_id: str = Query(..., min_length=1, max_length=200)) -> dict:
    try:
        return discord_service.create_link(device_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/link/status")
async def link_status(device_id: str = Query(..., min_length=1, max_length=200)) -> dict:
    return discord_service.link_status(device_id)


@router.post("/link/disconnect")
async def link_disconnect(device_id: str = Query(..., min_length=1, max_length=200)) -> dict:
    return discord_service.disconnect(device_id)


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(code: str, state: str) -> HTMLResponse:
    try:
        result = await discord_service.complete_link(code, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if result.status != "connected":
        return HTMLResponse(
            f"""<!doctype html><html><body style="background:#0b0c0d;color:#eee;font-family:Arial;padding:40px">
            <h1 style="color:#ff5500">Pitmark Discord Link Failed</h1>
            <p>{result.error}</p><p>You can close this window and return to Pitmark Racing Tools.</p>
            </body></html>""",
            status_code=400,
        )

    display = result.global_name or result.username
    return HTMLResponse(
        f"""<!doctype html><html><body style="background:#0b0c0d;color:#eee;font-family:Arial;padding:40px;text-align:center">
        <h1 style="color:#ff5500">Discord Connected</h1>
        <p>Pitmark Racing Tools is now linked to <strong>{display}</strong>.</p>
        <p>You can close this browser window and return to Pitmark.</p>
        <p style="color:#777">Leave Your Mark.</p>
        </body></html>"""
    )
