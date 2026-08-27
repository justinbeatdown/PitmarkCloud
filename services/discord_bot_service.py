from __future__ import annotations

import hmac
from typing import Any

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from utils.config import settings

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
    ]


async def register_guild_commands() -> dict[str, Any]:
    if not registration_configured():
        raise RuntimeError(
            "Bot registration needs DISCORD_CLIENT_ID, DISCORD_BOT_TOKEN, and DISCORD_GUILD_ID."
        )

    url = f"{DISCORD_API}/applications/{settings.discord_client_id}/guilds/{settings.discord_guild_id}/commands"
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    results = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for command in command_definitions():
            response = await client.post(url, headers=headers, json=command)
            response.raise_for_status()
            payload = response.json()
            results.append({
                "name": payload.get("name"),
                "id": payload.get("id"),
            })

    return {"registered": results, "guild_id": settings.discord_guild_id}


def _content(text: str, ephemeral: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {"content": text}
    if ephemeral:
        data["flags"] = 64
    return {"type": 4, "data": data}


def handle_command(payload: dict[str, Any], linked_identity_lookup) -> dict[str, Any]:
    data = payload.get("data") or {}
    name = data.get("name", "")
    user = ((payload.get("member") or {}).get("user") or payload.get("user") or {})
    discord_user_id = str(user.get("id") or "")

    if name == "pitmark":
        return _content(
            "**Pitmark Racing Tools** — iRacing telemetry, overlays, track maps, analysis, "
            "race cards, setup tools and more.\n\n"
            "Try `/status`, `/download`, `/support`, or `/account`.\n"
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

    return _content("Unknown Pitmark command.", ephemeral=True)


def validate_admin_key(supplied: str | None) -> bool:
    expected = settings.pitmark_admin_key
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
