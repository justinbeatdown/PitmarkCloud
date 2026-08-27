from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from services import live_session_service

router = APIRouter()


@router.post("/update")
async def update_session(
    request: Request,
    device_id: str = Query(..., min_length=1, max_length=200),
) -> dict:
    payload = await request.json()
    try:
        session = live_session_service.update_session(device_id, payload)
        return {"accepted": True, "session": session}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/clear")
async def clear_session(
    device_id: str = Query(..., min_length=1, max_length=200),
) -> dict:
    return {"cleared": live_session_service.clear_session(device_id)}
