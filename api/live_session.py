from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from models.schemas import LiveSessionUpdate
from services import device_auth_service, live_session_service
from utils.security import enforce_rate_limit, validate_device_id

router = APIRouter()


@router.post("/update")
async def update_session(
    request: Request,
    payload: LiveSessionUpdate,
    device_id: str = Query(..., min_length=16, max_length=64),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    enforce_rate_limit(request, "session-update", 240)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    try:
        session = live_session_service.update_session(device_id, payload.model_dump())
        return {"accepted": True, "session": session}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/clear")
async def clear_session(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    enforce_rate_limit(request, "session-clear", 60)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    return {"cleared": live_session_service.clear_session(device_id)}


@router.get("/status")
async def session_status(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    enforce_rate_limit(request, "session-status", 120)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    session = live_session_service.get_for_device(device_id)
    if session is None:
        return {"active": False, "fresh": False, "session": None}
    return {
        "active": True,
        "fresh": live_session_service.is_fresh(session),
        "session": session,
    }
