from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from services import device_auth_service, discord_service, live_session_service, result_service
from services.licensing import current_entitlements
from utils.security import enforce_rate_limit, validate_device_id

router = APIRouter()


def _identity(request: Request, device_id: str, token: str | None) -> tuple[str, dict]:
    enforce_rate_limit(request, "prt-mobile", 180)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise HTTPException(status_code=403, detail="Connect this PRT device to Discord first.")
    discord_user_id = str(link.get("discord_user_id") or "")
    if not discord_user_id:
        raise HTTPException(status_code=403, detail="Linked Discord identity is missing.")
    return discord_user_id, link


@router.get("/dashboard")
async def mobile_dashboard(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    discord_user_id, link = _identity(request, device_id, x_pitmark_device_token)
    recent = result_service.get_recent_for_discord_user(discord_user_id, 8)
    live = live_session_service.get_for_discord_user(discord_user_id)
    entitlements = current_entitlements(device_id)

    return {
        "driver": {
            "display_name": link.get("global_name") or link.get("username") or entitlements.display_name,
            "discord_connected": True,
            "plan": entitlements.plan.value,
            "status": entitlements.status,
        },
        "summary": result_service.get_driver_summary(discord_user_id),
        "live": {
            "active": bool(live),
            "fresh": live_session_service.is_fresh(live) if live else False,
            "session": live,
        },
        "recent_results": recent,
        "features": entitlements.features.model_dump(),
    }


@router.get("/sessions")
async def mobile_sessions(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    limit: int = Query(default=25, ge=1, le=50),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    discord_user_id, _ = _identity(request, device_id, x_pitmark_device_token)
    items = result_service.get_recent_for_discord_user(discord_user_id, limit)
    return {"items": items, "count": len(items)}


@router.get("/live")
async def mobile_live(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    discord_user_id, _ = _identity(request, device_id, x_pitmark_device_token)
    live = live_session_service.get_for_discord_user(discord_user_id)
    return {
        "active": bool(live),
        "fresh": live_session_service.is_fresh(live) if live else False,
        "session": live,
    }
