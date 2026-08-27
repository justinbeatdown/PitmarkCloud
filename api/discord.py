from fastapi import APIRouter
from models.schemas import DiscordStatusResponse
from services.discord_service import status as discord_status

router = APIRouter()


@router.get("/status", response_model=DiscordStatusResponse)
async def status() -> DiscordStatusResponse:
    return DiscordStatusResponse(**discord_status())


@router.get("/oauth/start")
async def oauth_start() -> dict:
    return {
        "status": "not_implemented",
        "message": "Discord OAuth is scaffolded but intentionally not enabled until app credentials are configured.",
    }
