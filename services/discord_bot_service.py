from __future__ import annotations

import hmac
from typing import Any

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from utils.config import settings
from services import live_session_service

DISCORD_API = "https://discord.com/api/v10"


def interactions_configured() -> bool:
    return bool(settings.discord_public_key)


def registration_configured() -> bool:
    return bool(settings.discord_client_id and settings.discord_bot_token and settings.discord_guild_id)


def verify_signature(signature: str, timestamp: str, body: bytes) -> bool:
    if not settings.discord_public_key:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key))
        verify_key.verify(timestamp.encode("utf-8") + body, bytes.fromhex(signature))
        return True
    except (ValueError, BadSignatureError):
        return False


def command_definitions() -> list[dict[str, Any]]:
    # Guild commands update quickly while we are developing.
    return [
        {
            "name": "pitmark",
            "description": "About Pitmark Racing Tools and available Discord commands.",
            "type": 1,
        },
        {
            "name": "status",
            "description": "Check Pitmark Cloud and Discord integration status.",
            "type": 1,
        },
        {
            "name": "download",
            "description": "Get the Pitmark Racing Tools download/store link.",
            "type": 1,
        },
        {
            "name": "support",
            "description": "Get Pitmark Racing Tools support information.",
            "type": 1,
        },
        {
            "name": "account",
            "description": "Check whether your Discord identity is linked to Pitmark.",
            "type": 1,
        },
        {
            "name": "session",
            "description": "Show your live iRacing session from Pitmark Racing Tools.",
            "type": 1,
        },
    ]


async def register_guild_commands() -> dict[str, Any]:
    if not registration_configured():
        raise RuntimeError(
            "Bot registration needs DISCORD_CLIENT_ID, DISCORD_BOT_TOKEN, and DISCORD_GUILD_ID."
        )

    url = f"{DISCORD_API}/applications/{settings.discord_client_id}/guilds/{settings.discord_guild_id}/commands"
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.put(url, headers=headers, json=command_definitions())
        response.raise_for_status()
        payload = response.json()

    results = [
        {"name": command.get("name"), "id": command.get("id")}
        for command in payload
    ]
    return {"registered": results, "guild_id": settings.discord_guild_id}


def _content(text: str, ephemeral: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"content": text}
    if ephemeral:
        data["flags"] = 64
    return {"type": 4, "data": data}


def _lap_time(seconds: float) -> str:
    if not seconds or seconds <= 0:
        return "—"
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes}:{remaining:06.3f}" if minutes else f"{remaining:.3f}"


def _session_embed(session: dict[str, Any]) -> dict[str, Any]:
    delta = float(session.get("delta") or 0.0)
    delta_text = f"{delta:+.3f}s"
    pos = int(session.get("position") or 0)
    position_text = f"P{pos}" if pos > 0 else "—"

    fields = [
        {"name": "Track", "value": str(session.get("track_name") or "iRacing Session"), "inline": True},
        {"name": "Car", "value": str(session.get("car_name") or "Player Car"), "inline": True},
        {"name": "Position", "value": position_text, "inline": True},
        {"name": "Lap", "value": str(session.get("lap") or 0), "inline": True},
        {"name": "Best Lap", "value": _lap_time(float(session.get("best_lap_time") or 0.0)), "inline": True},
        {"name": "Current Lap", "value": _lap_time(float(session.get("current_lap_time") or 0.0)), "inline": True},
        {"name": "Delta", "value": delta_text, "inline": True},
        {"name": "Fuel", "value": f"{float(session.get('fuel_gallons') or 0.0):.1f} gal", "inline": True},
        {"name": "Fuel Range", "value": f"{float(session.get('fuel_laps_remaining') or 0.0):.1f} laps", "inline": True},
        {"name": "Speed", "value": f"{float(session.get('speed_mph') or 0.0):.0f} mph", "inline": True},
        {"name": "Gear / RPM", "value": f"{int(session.get('gear') or 0)} / {int(session.get('rpm') or 0):,}", "inline": True},
        {"name": "Flag / Incidents", "value": f"{session.get('flag_text') or 'GREEN'} / {int(session.get('incident_count') or 0)}x", "inline": True},
    ]

    return {
        "type": 4,
        "data": {
            "embeds": [{
                "title": "🏁 Live Pitmark Session",
                "description": "Live telemetry shared from **Pitmark Racing Tools**.",
                "color": 16733440,
                "fields": fields,
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }]
        },
    }


def handle_command(payload: dict[str, Any], linked_identity_lookup) -> dict[str, Any]:
    data = payload.get("data") or {}
    name = data.get("name", "")
    user = ((payload.get("member") or {}).get("user") or payload.get("user") or {})
    discord_user_id = str(user.get("id") or "")

    if name == "pitmark":
        return _content(
            "**Pitmark Racing Tools** — iRacing telemetry, overlays, track maps, analysis, "
            "race cards, setup tools and more.\n\n"
            "Try `/session`, `/status`, `/download`, `/support`, or `/account`.\n"
            "**Leave Your Mark.**"
        )

    if name == "status":
        return _content(
            "🟢 **Pitmark Cloud:** Online\n"
            "🟢 **Discord Bot:** Online\n"
            "🏁 **Pitmark Racing Tools:** Development"
        )

    if name == "download":
        return _content(
            "🏁 **Pitmark Racing Tools**\n"
            "Store/download information: https://pitmarkracing.com\n"
            "_Development builds may still be distributed directly to testers._"
        )

    if name == "support":
        invite = settings.discord_support_invite_url.strip()
        if invite:
            return _content(f"Need help with Pitmark Racing Tools?\n{invite}", ephemeral=True)
        return _content(
            "You're already in the Pitmark community server. Please use the designated support "
            "channel for bugs, setup help, or account questions.",
            ephemeral=True,
        )

    if name == "account":
        linked = linked_identity_lookup(discord_user_id)
        if linked:
            display = linked.get("global_name") or linked.get("username") or "Discord User"
            return _content(
                f"✅ **Discord linked to Pitmark**\nAccount: **{display}**\n"
                "Development entitlements are currently unlocked.",
                ephemeral=True,
            )
        return _content(
            "Your Discord account is not currently linked to this Pitmark Cloud instance.\n"
            "Open **Pitmark Racing Tools → Settings → Discord → Connect Discord**.",
            ephemeral=True,
        )


    if name == "session":
        linked = linked_identity_lookup(discord_user_id)
        if not linked:
            return _content(
                "Link Discord first in **Pitmark Racing Tools → Settings → Discord**.",
                ephemeral=True,
            )

        session = live_session_service.get_for_discord_user(discord_user_id)
        if not session:
            return _content(
                "No live Pitmark session has been published yet. Start Pitmark Racing Tools and enter an iRacing session.",
                ephemeral=True,
            )

        if not live_session_service.is_fresh(session):
            return _content(
                "Your last Pitmark session update is stale. Make sure Pitmark Racing Tools is open and iRacing telemetry is live.",
                ephemeral=True,
            )

        return _session_embed(session)

    return _content("Unknown Pitmark command.", ephemeral=True)


def validate_admin_key(supplied: str | None) -> bool:
    expected = settings.pitmark_admin_key
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
