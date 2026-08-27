from datetime import datetime, timezone
from fastapi import APIRouter
from models.schemas import HealthResponse
from utils.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        environment=settings.environment,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
    )
