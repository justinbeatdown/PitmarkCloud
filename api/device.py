from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services import device_auth_service
from utils.security import enforce_rate_limit

router = APIRouter()


class DeviceRegistration(BaseModel):
    device_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    device_secret: str = Field(min_length=32, max_length=128)


@router.post("/register")
async def register_device(request: Request, payload: DeviceRegistration) -> dict:
    enforce_rate_limit(request, "device-register", 20, 300)
    try:
        return device_auth_service.register(payload.device_id, payload.device_secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
