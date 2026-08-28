from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import discord_service, guild_config_service, result_service
from utils.config import settings

router = APIRouter()


class RaceResultPayload(BaseModel):
    session_id: str = Field(default="", max_length=180)
    date: str = Field(default="", max_length=180)
    track_name: str = Field(default="Unknown Track", max_length=180)
    car_name: str = Field(default="Unknown Car", max_length=180)
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
async def publish_result(payload: RaceResultPayload, device_id: str = Query(..., min_length=6, max_length=180)) -> dict:
    try:
        return {"published": True, "result": result_service.publish_result(device_id, payload.model_dump())}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/result/latest")
async def latest_result(device_id: str = Query(..., min_length=6, max_length=180)) -> dict:
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
async def share_destinations(device_id: str = Query(..., min_length=6, max_length=180)) -> dict:
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
    return {
        "title": "🏁 PITMARK POST-RACE",
        "description": f"**{display_name}** • {result.get('track_name') or 'Unknown Track'}\n{result.get('car_name') or 'Unknown Car'}",
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


@router.post("/share/racecard")
async def share_racecard(
    device_id: str = Query(..., min_length=6, max_length=180),
    guild_id: str | None = Query(default=None, min_length=5, max_length=32),
) -> dict:
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise HTTPException(status_code=403, detail="Connect Discord in Pitmark Racing Tools first.")

    discord_user_id = str(link.get("discord_user_id") or "")
    result = result_service.get_latest_for_discord_user(discord_user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No completed race result has been published yet.")

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
