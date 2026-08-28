from __future__ import annotations

import hmac
from typing import Any

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from utils.config import settings
from services import guild_config_service, live_session_service, result_service

DISCORD_API = "https://discord.com/api/v10"


def interactions_configured() -> bool:
    return bool(settings.discord_public_key)


def registration_configured() -> bool:
    if not (settings.discord_client_id and settings.discord_bot_token):
        return False
    return settings.discord_command_scope.lower() == "global" or bool(settings.discord_guild_id)


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
    return [
        {
            "name": "pitmark",
            "description": "Pitmark Racing Tools server setup and information.",
            "type": 1,
            "options": [
                {"name": "about", "description": "About Pitmark Racing Tools.", "type": 1},
                {
                    "name": "setup",
                    "description": "Choose this server's Pitmark sharing channel.",
                    "type": 1,
                    "options": [
                        {
                            "name": "channel",
                            "description": "Channel for Race Cards and app sharing.",
                            "type": 7,
                            "required": True,
                            "channel_types": [0, 5],
                        }
                    ],
                },
                {"name": "config", "description": "Show this server's Pitmark configuration.", "type": 1},
                {"name": "reset", "description": "Remove this server's Pitmark configuration.", "type": 1},
            ],
        },
        {"name": "status", "description": "Check Pitmark Cloud and Discord integration status.", "type": 1},
        {"name": "download", "description": "Get the Pitmark Racing Tools download/store link.", "type": 1},
        {"name": "support", "description": "Get Pitmark Racing Tools support information.", "type": 1},
        {"name": "account", "description": "Check whether your Discord identity is linked to Pitmark.", "type": 1},
        {"name": "session", "description": "Show your live iRacing session from Pitmark Racing Tools.", "type": 1},
        {"name": "driver", "description": "Show your linked Pitmark driver profile and recent stats.", "type": 1},
        {"name": "results", "description": "Show your recent Pitmark Racing Tools session results.", "type": 1},
        {"name": "racecard", "description": "Post your latest Pitmark post-race card in this channel.", "type": 1},
    ]


async def register_commands() -> dict[str, Any]:
    if not registration_configured():
        raise RuntimeError("Bot registration needs DISCORD_CLIENT_ID and DISCORD_BOT_TOKEN; guild scope also needs DISCORD_GUILD_ID.")

    scope = (settings.discord_command_scope or "global").strip().lower()
    if scope == "guild":
        url = f"{DISCORD_API}/applications/{settings.discord_client_id}/guilds/{settings.discord_guild_id}/commands"
    else:
        scope = "global"
        url = f"{DISCORD_API}/applications/{settings.discord_client_id}/commands"

    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.put(url, headers=headers, json=command_definitions())
        response.raise_for_status()
        payload = response.json()

    results = [{"name": command.get("name"), "id": command.get("id")} for command in payload]
    return {"registered": results, "scope": scope, "guild_id": settings.discord_guild_id if scope == "guild" else None}



register_guild_commands = register_commands


def _member_can_manage_guild(payload: dict[str, Any]) -> bool:
    member = payload.get("member") or {}
    try:
        permissions = int(member.get("permissions") or 0)
    except (TypeError, ValueError):
        permissions = 0
    return bool(permissions & (1 << 3) or permissions & (1 << 5))


def _pitmark_subcommand(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    options = data.get("options") or []
    if not options:
        return "about", []
    first = options[0] or {}
    return str(first.get("name") or "about"), list(first.get("options") or [])


def _option_value(options: list[dict[str, Any]], name: str) -> Any:
    for option in options:
        if option.get("name") == name:
            return option.get("value")
    return None


async def _discord_guild_name(guild_id: str) -> str:
    if not settings.discord_bot_token:
        return "Discord Server"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{DISCORD_API}/guilds/{guild_id}",
                headers={"Authorization": f"Bot {settings.discord_bot_token}"},
            )
        if response.is_success:
            return str(response.json().get("name") or "Discord Server")[:180]
    except Exception:
        pass
    return "Discord Server"



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



def _position(value: Any) -> str:
    try:
        pos = int(value or 0)
    except (TypeError, ValueError):
        pos = 0
    return f"P{pos}" if pos > 0 else "—"


def _racecard_embed(result: dict[str, Any], display_name: str) -> dict[str, Any]:
    start = int(result.get("starting_position") or 0)
    finish = int(result.get("finishing_position") or 0)
    change = start - finish if start > 0 and finish > 0 else None
    change_text = f"{change:+d}" if change is not None else "—"
    return {
        "type": 4,
        "data": {
            "embeds": [{
                "title": "🏁 PITMARK POST-RACE",
                "description": (
                    f"**{display_name}**\n"
                    f"**{result.get('track_name') or 'Unknown Track'}** • {result.get('car_name') or 'Unknown Car'}"
                ),
                "color": 16733440,
                "fields": [
                    {"name": "Start", "value": _position(start), "inline": True},
                    {"name": "Finish", "value": _position(finish), "inline": True},
                    {"name": "Positions", "value": change_text, "inline": True},
                    {"name": "Laps", "value": str(int(result.get("laps") or 0)), "inline": True},
                    {"name": "Best Lap", "value": _lap_time(float(result.get("best_lap_time") or 0.0)), "inline": True},
                    {"name": "Incidents", "value": f"{int(result.get('incidents') or 0)}x", "inline": True},
                    {"name": "Consistency", "value": f"{float(result.get('consistency') or 0.0):.0f}%", "inline": True},
                    {"name": "Avg Fuel/Lap", "value": f"{float(result.get('average_fuel_per_lap') or 0.0):.2f} gal", "inline": True},
                ],
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }]
        },
    }


def _driver_embed(display_name: str, summary: dict[str, Any], latest: dict[str, Any] | None) -> dict[str, Any]:
    fields = [
        {"name": "Recent Sessions", "value": str(int(summary.get("sessions") or 0)), "inline": True},
        {"name": "Recorded Laps", "value": str(int(summary.get("laps") or 0)), "inline": True},
        {"name": "Best Lap", "value": _lap_time(float(summary.get("best_lap_time") or 0.0)), "inline": True},
        {"name": "Avg Finish", "value": f"P{float(summary.get('avg_finish') or 0.0):.1f}" if float(summary.get('avg_finish') or 0.0) > 0 else "—", "inline": True},
        {"name": "Incidents", "value": f"{int(summary.get('incidents') or 0)}x", "inline": True},
    ]
    if latest:
        fields.append({
            "name": "Latest Result",
            "value": f"{latest.get('track_name') or 'Unknown Track'} • {_position(latest.get('finishing_position'))} • {_lap_time(float(latest.get('best_lap_time') or 0.0))}",
            "inline": False,
        })
    return {
        "type": 4,
        "data": {
            "embeds": [{
                "title": f"🏁 {display_name}",
                "description": "**Pitmark Driver Profile** • Stats from sessions published by Pitmark Racing Tools.",
                "color": 16733440,
                "fields": fields,
                "footer": {"text": "Development stats currently use the most recent 10 published sessions."},
            }]
        },
    }


def _results_embed(display_name: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    lines: list[str] = []
    for result in results:
        track = str(result.get("track_name") or "Unknown Track")
        finish = _position(result.get("finishing_position"))
        best = _lap_time(float(result.get("best_lap_time") or 0.0))
        laps = int(result.get("laps") or 0)
        incidents = int(result.get("incidents") or 0)
        lines.append(f"**{track}** — {finish} • {laps} laps • Best {best} • {incidents}x")
    return {
        "type": 4,
        "data": {
            "embeds": [{
                "title": f"📋 {display_name} — Recent Results",
                "description": "\n".join(lines),
                "color": 16733440,
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }]
        },
    }

async def handle_command(payload: dict[str, Any], linked_identity_lookup) -> dict[str, Any]:
    data = payload.get("data") or {}
    name = data.get("name", "")
    user = ((payload.get("member") or {}).get("user") or payload.get("user") or {})
    discord_user_id = str(user.get("id") or "")

    if name == "pitmark":
        subcommand, suboptions = _pitmark_subcommand(data)
        guild_id = str(payload.get("guild_id") or "")

        if subcommand == "about":
            return _content(
                "**Pitmark Racing Tools** — iRacing telemetry, overlays, track maps, analysis, race cards, setup tools and more.\n\n"
                "Try `/session`, `/driver`, `/results`, `/racecard`, `/status`, `/download`, `/support`, or `/account`.\n"
                "Server managers can use `/pitmark setup` to choose this server's app-sharing channel.\n"
                "**Leave Your Mark.**"
            )

        if not guild_id:
            return _content("Pitmark server configuration is only available inside a Discord server.", ephemeral=True)

        if subcommand == "config":
            config = guild_config_service.get(guild_id)
            if not config:
                return _content(
                    "Pitmark is installed here, but no app-sharing channel has been configured yet. "
                    "A server manager can run `/pitmark setup`.",
                    ephemeral=True,
                )
            channel = config.get("share_channel_id") or ""
            return _content(
                f"🏁 **Pitmark server configuration**\nApp Share channel: <#{channel}>\n"
                "Slash commands such as `/racecard`, `/results`, and `/session` respond in the channel where they are invoked, subject to Discord permissions.",
                ephemeral=True,
            )

        if subcommand in {"setup", "reset"} and not _member_can_manage_guild(payload):
            return _content("You need **Manage Server** (or Administrator) to change Pitmark server settings.", ephemeral=True)

        if subcommand == "reset":
            removed = guild_config_service.reset(guild_id)
            return _content(
                "Pitmark server configuration removed." if removed else "This server did not have a saved Pitmark configuration.",
                ephemeral=True,
            )

        if subcommand == "setup":
            channel_id = str(_option_value(suboptions, "channel") or "")
            if not channel_id:
                return _content("Choose a text channel for Pitmark sharing.", ephemeral=True)
            resolved = ((data.get("resolved") or {}).get("channels") or {}).get(channel_id) or {}
            channel_name = str(resolved.get("name") or channel_id)[:180]
            resolved_guild_id = str(resolved.get("guild_id") or guild_id)
            if resolved_guild_id != guild_id:
                return _content("That channel does not belong to this server.", ephemeral=True)
            guild_name = await _discord_guild_name(guild_id)
            guild_config_service.configure(guild_id, guild_name, channel_id, channel_name, discord_user_id)
            return _content(
                f"✅ **Pitmark configured for {guild_name}.**\nApp-shared Race Cards will post in <#{channel_id}>.\n"
                "You can change it any time with `/pitmark setup`.",
                ephemeral=True,
            )

        return _content("Unknown Pitmark configuration action.", ephemeral=True)

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


    if name in {"driver", "results", "racecard"}:
        linked = linked_identity_lookup(discord_user_id)
        if not linked:
            return _content(
                "Link Discord first in **Pitmark Racing Tools → Settings → Discord**.",
                ephemeral=True,
            )

        display = linked.get("global_name") or linked.get("username") or "Pitmark Driver"
        latest = result_service.get_latest_for_discord_user(discord_user_id)

        if name == "driver":
            return _driver_embed(str(display), result_service.get_driver_summary(discord_user_id), latest)

        if name == "results":
            recent = result_service.get_recent_for_discord_user(discord_user_id, 5)
            if not recent:
                return _content(
                    "No completed Pitmark results have been published yet. Finish a recorded iRacing session with Pitmark Racing Tools running.",
                    ephemeral=True,
                )
            return _results_embed(str(display), recent)

        if not latest:
            return _content(
                "No completed Pitmark result is available for a race card yet.",
                ephemeral=True,
            )
        return _racecard_embed(latest, str(display))

    return _content("Unknown Pitmark command.", ephemeral=True)


def validate_admin_key(supplied: str | None) -> bool:
    expected = settings.pitmark_admin_key
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))
