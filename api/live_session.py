from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.schemas import LiveSessionUpdate
from services import live_session_service

router = APIRouter()


@router.post("/update")
async def update_session(
    payload: LiveSessionUpdate,
    device_id: str = Query(..., min_length=1, max_length=200),
) -> dict:
    try:
        session = live_session_service.update_session(device_id, payload.model_dump())
        return {"accepted": True, "session": session}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/clear")
async def clear_session(
    device_id: str = Query(..., min_length=1, max_length=200),
) -> dict:
    return {"cleared": live_session_service.clear_session(device_id)}


@router.get("/status")
async def session_status(
    device_id: str = Query(..., min_length=1, max_length=200),
) -> dict:
    session = live_session_service.get_for_device(device_id)
    if session is None:
        return {"active": False, "fresh": False, "session": None}
    return {
        "active": True,
        "fresh": live_session_service.is_fresh(session),
        "session": session,
    }
