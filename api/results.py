from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, File, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from services import device_auth_service, discord_service, guild_config_service, result_service
from utils.config import settings
from utils.security import enforce_rate_limit, validate_device_id, validate_discord_id

router = APIRouter()


class RaceResultPayload(BaseModel):
    session_id: str = Field(default="", max_length=180)
    date: str = Field(default="", max_length=180)
    track_name: str = Field(default="Unknown Track", max_length=180)
    car_name: str = Field(default="Unknown Car", max_length=180)
    driver_name: str = Field(default="", max_length=180)
    session_type: str = Field(default="iRacing Session", max_length=180)
    laps: int = Field(default=0, ge=0, le=100000)
    best_lap_time: float = Field(default=0.0, ge=0, le=100000)
    average_lap_time: float = Field(default=0.0, ge=0, le=100000)
    starting_position: int = Field(default=0, ge=0, le=10000)
    finishing_position: int = Field(default=0, ge=0, le=10000)
    incidents: int = Field(default=0, ge=0, le=100000)
    consistency: float = Field(default=0.0, ge=0, le=100)
    average_fuel_per_lap: float = Field(default=0.0, ge=0, le=10000)


@router.post("/result/publish")
async def publish_result(request: Request, payload: RaceResultPayload, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "result-publish", 180)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    try:
        return {"published": True, "result": result_service.publish_result(device_id, payload.model_dump())}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/result/latest")
async def latest_result(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "result-latest", 120)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise HTTPException(status_code=403, detail="This device is not linked to Discord.")
    discord_user_id = str(link.get("discord_user_id") or "")
    return {"result": result_service.get_latest_for_discord_user(discord_user_id)}


async def _configured_destinations(device_id: str) -> list[dict[str, Any]]:
    try:
        user_guilds = await discord_service.user_guilds(device_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Discord could not return your server list. Reconnect Discord and try again.")

    memberships = {str(g.get("id") or ""): g for g in user_guilds if g.get("id")}
    destinations: list[dict[str, Any]] = []
    for config in guild_config_service.all_enabled():
        guild_id = str(config.get("guild_id") or "")
        membership = memberships.get(guild_id)
        if not membership:
            continue
        destinations.append({
            "guild_id": guild_id,
            "guild_name": str(config.get("guild_name") or membership.get("name") or "Discord Server"),
            "channel_id": str(config.get("share_channel_id") or ""),
            "channel_name": str(config.get("share_channel_name") or "Pitmark Channel"),
            "icon": membership.get("icon"),
        })
    destinations.sort(key=lambda x: x["guild_name"].lower())
    return destinations


@router.get("/share/destinations")
async def share_destinations(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "share-destinations", 120)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    destinations = await _configured_destinations(device_id)
    return {"destinations": destinations, "count": len(destinations)}


def _lap_time(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return "—"
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes}:{remaining:06.3f}" if minutes else f"{remaining:.3f}"


def racecard_embed(result: dict[str, Any], display_name: str = "Pitmark Driver") -> dict[str, Any]:
    start = int(result.get("starting_position") or 0)
    finish = int(result.get("finishing_position") or 0)
    start_text = f"P{start}" if start > 0 else "—"
    finish_text = f"P{finish}" if finish > 0 else "—"
    gain = start - finish if start > 0 and finish > 0 else 0
    gain_text = f"{gain:+d}" if start > 0 and finish > 0 else "—"
    display = str(result.get("driver_name") or display_name or "Pitmark Driver")
    return {
        "title": "🏁 PITMARK POST-RACE",
        "description": f"**{display}** • {result.get('track_name') or 'Unknown Track'}\n{result.get('car_name') or 'Unknown Car'}",
        "color": 16733440,
        "fields": [
            {"name": "Start", "value": start_text, "inline": True},
            {"name": "Finish", "value": finish_text, "inline": True},
            {"name": "Positions", "value": gain_text, "inline": True},
            {"name": "Laps", "value": str(int(result.get("laps") or 0)), "inline": True},
            {"name": "Best Lap", "value": _lap_time(float(result.get("best_lap_time") or 0.0)), "inline": True},
            {"name": "Incidents", "value": f"{int(result.get('incidents') or 0)}x", "inline": True},
        ],
        "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
    }


async def _resolve_share_destination(device_id: str, guild_id: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise HTTPException(status_code=403, detail="Connect Discord in Pitmark Racing Tools first.")

    destinations = await _configured_destinations(device_id)
    if not destinations:
        raise HTTPException(
            status_code=409,
            detail="No Pitmark-enabled Discord server is available. A server manager must run /pitmark setup first.",
        )

    destination = None
    if guild_id:
        destination = next((item for item in destinations if item["guild_id"] == guild_id), None)
        if destination is None:
            raise HTTPException(status_code=403, detail="That Discord server is not an available Pitmark destination for your account.")
    elif len(destinations) == 1:
        destination = destinations[0]
    else:
        raise HTTPException(status_code=409, detail="Choose which Discord server should receive this Race Card.")

    if not settings.discord_bot_token:
        raise HTTPException(status_code=503, detail="DISCORD_BOT_TOKEN is not configured.")
    return link, destination


@router.post("/share/racecard")
async def share_racecard(
    request: Request,
    device_id: str = Query(..., min_length=16, max_length=64),
    guild_id: str | None = Query(default=None, min_length=5, max_length=32),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    enforce_rate_limit(request, "share-racecard", 30)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    if guild_id is not None:
        guild_id = validate_discord_id(guild_id, "guild id")

    link, destination = await _resolve_share_destination(device_id, guild_id)
    discord_user_id = str(link.get("discord_user_id") or "")
    result = result_service.get_latest_for_discord_user(discord_user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No completed race result has been published yet.")

    channel_id = destination["channel_id"]
    display = link.get("global_name") or link.get("username") or "Pitmark Driver"
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    payload = {"embeds": [racecard_embed(result, str(display))]}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
    if not response.is_success:
        if response.status_code == 403:
            raise HTTPException(
                status_code=502,
                detail="Pitmark cannot post in that server's configured channel. Ask a server manager to check the bot's View Channel, Send Messages, and Embed Links permissions or run /pitmark setup again.",
            )
        raise HTTPException(status_code=502, detail=f"Discord rejected the share request ({response.status_code}).")

    body = response.json()
    return {
        "shared": True,
        "guild_id": destination["guild_id"],
        "guild_name": destination["guild_name"],
        "channel_id": channel_id,
        "channel_name": destination["channel_name"],
        "message_id": body.get("id"),
    }


@router.post("/share/racecard-image")
async def share_racecard_image(
    request: Request,
    file: UploadFile = File(...),
    device_id: str = Query(..., min_length=16, max_length=64),
    guild_id: str | None = Query(default=None, min_length=5, max_length=32),
    x_pitmark_device_token: str | None = Header(default=None),
) -> dict:
    """Upload the exact PNG rendered by PRT and post that same file to Discord."""
    enforce_rate_limit(request, "share-racecard-image", 30)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    if guild_id is not None:
        guild_id = validate_discord_id(guild_id, "guild id")

    if file.content_type not in {"image/png", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Race Card upload must be a PNG image.")
    png = await file.read(8 * 1024 * 1024 + 1)
    if not png:
        raise HTTPException(status_code=400, detail="Race Card PNG was empty.")
    if len(png) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Race Card PNG is too large for Discord upload.")
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="Uploaded Race Card is not a valid PNG file.")

    _, destination = await _resolve_share_destination(device_id, guild_id)
    channel_id = destination["channel_id"]
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    payload = {
        "content": "🏁 **PITMARK POST-RACE**\nOfficial Race Card generated by Pitmark Racing Tools.",
        "attachments": [{"id": 0, "filename": "pitmark-race-card.png", "description": "Official Pitmark post-race card"}],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            headers=headers,
            data={"payload_json": json.dumps(payload)},
            files={"files[0]": ("pitmark-race-card.png", png, "image/png")},
        )

    if not response.is_success:
        if response.status_code == 403:
            raise HTTPException(
                status_code=502,
                detail="Pitmark cannot upload Race Cards in that Discord channel. Check View Channel, Send Messages and Attach Files permissions.",
            )
        raise HTTPException(status_code=502, detail=f"Discord rejected the Race Card image ({response.status_code}).")

    body = response.json()
    return {
        "shared": True,
        "image_uploaded": True,
        "guild_id": destination["guild_id"],
        "guild_name": destination["guild_name"],
        "channel_id": channel_id,
        "channel_name": destination["channel_name"],
        "message_id": body.get("id"),
    }
