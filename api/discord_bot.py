from __future__ import annotations

import json
from json import JSONDecodeError

from fastapi import APIRouter, Header, HTTPException, Request

from services import discord_bot_service, discord_gateway_service, discord_service, guild_config_service
from services.database import database_status
from utils.security import MAX_REQUEST_BODY, enforce_rate_limit

router = APIRouter()


@router.get("/bot/status")
async def bot_status() -> dict:
    return {
        "interaction_endpoint_configured": discord_bot_service.interactions_configured(),
        "command_registration_configured": discord_bot_service.registration_configured(),
        "command_scope": "global",
        "gateway_presence": discord_gateway_service.state(),
        "configured_guilds": len(guild_config_service.all_enabled()),
        "database": database_status(),
        "install_url": discord_service.install_url(),
    }


@router.post("/bot/register")
async def register_bot_commands(request: Request, x_pitmark_admin_key: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "bot-register", 10, 300)
    if not discord_bot_service.validate_admin_key(x_pitmark_admin_key):
        raise HTTPException(status_code=401, detail="Invalid Pitmark admin key.")
    try:
        return await discord_bot_service.register_commands()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/interactions")
async def interactions(request: Request) -> dict:
    enforce_rate_limit(request, "discord-interactions", 300)
    raw = await request.body()
    if len(raw) > MAX_REQUEST_BODY:
        raise HTTPException(status_code=413, detail="Interaction payload too large.")
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")

    if not discord_bot_service.verify_signature(signature, timestamp, raw):
        raise HTTPException(status_code=401, detail="Invalid Discord interaction signature.")

    try:
        payload = json.loads(raw)
    except (JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Malformed Discord interaction payload.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Malformed Discord interaction payload.")
    interaction_type = payload.get("type")

    # Discord PING verification.
    if interaction_type == 1:
        return {"type": 1}

    # Application command.
    if interaction_type == 2:
        return await discord_bot_service.handle_command(
            payload, discord_service.find_link_by_discord_user_id
        )

    return {"type": 4, "data": {"content": "Unsupported interaction.", "flags": 64}}
