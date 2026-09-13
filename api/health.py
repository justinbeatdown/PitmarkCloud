from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from models.schemas import HealthResponse
from utils.config import settings

router = APIRouter()
_ASSET_DIR = Path(__file__).resolve().parent


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        environment=settings.environment,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/prt-timmy-logo.jpg", include_in_schema=False)
async def prt_timmy_logo():
    return FileResponse(
        _ASSET_DIR / "timmyneutron020-logo.jpg",
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )
