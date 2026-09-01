from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from services.discord_hq_blueprint import *
from utils.config import settings

log = logging.getLogger("pitmark.discord.hq")
DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"


def hq_install_url() -> str:
    if not settings.discord_client_id:
        return ""
    return f"{DISCORD_AUTHORIZE}?" + urlencode(
        {
            "client_id": settings.discord_client_id,
            "scope": "bot applications.commands",
            "permissions": str(
                settings.discord_hq_install_permissions or HQ_REQUIRED_BOT_PERMISSIONS
            ),
            "guild_id": settings.discord_hq_guild_id,
            "disable_guild_select": "true",
        }
    )


def headers(reason: str | None = None) -> dict[str, str]:
    result = {
        "Authorization": f"Bot {settings.discord_bot_token}",
        "Content-Type": "application/json",
    }
    if reason:
        result["X-Audit-Log-Reason"] = reason[:512]
    return result


async def discord_request(
    method: str,
    url: str,
    *,
    reason: str | None = None,
    json: Any = None,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
    expected: set[int] | None = None,
    max_retries: int = 10,
) -> httpx.Response:
    """Call Discord REST with explicit 429/backoff handling.

    Discord returns retry_after (seconds) when a route or the global bucket is
    rate-limited. The bootstrap intentionally performs many writes, so this
    helper waits for the bucket and resumes instead of aborting a partially
    completed idempotent build.
    """
    last_response: httpx.Response | None = None
    method = method.upper()

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries + 1):
            response = await client.request(
                method,
                url,
                headers=headers(reason),
                json=json,
                params=params,
            )
            last_response = response

            if response.status_code == 429:
                retry_after = 1.0
                try:
                    retry_after = float((response.json() or {}).get("retry_after") or 1.0)
                except (TypeError, ValueError, httpx.DecodingError):
                    try:
                        retry_after = float(response.headers.get("Retry-After") or 1.0)
                    except (TypeError, ValueError):
                        retry_after = 1.0

                # Small cushion keeps the request from landing on the exact
                # bucket-reset boundary. Discord retry_after is in seconds.
                wait = max(0.25, min(retry_after, 65.0)) + 0.20
                log.warning(
                    "Discord rate limit on %s %s; retrying in %.2fs (%s/%s, global=%s)",
                    method,
                    url,
                    wait,
                    attempt + 1,
                    max_retries + 1,
                    bool((response.json() or {}).get("global"))
                    if response.headers.get("content-type", "").startswith("application/json")
                    else False,
                )
                await asyncio.sleep(wait)
                continue

            if response.status_code >= 500 and attempt < max_retries:
                wait = min(0.5 * (2**attempt), 8.0)
                log.warning(
                    "Discord server error %s on %s %s; retrying in %.2fs",
                    response.status_code,
                    method,
                    url,
                    wait,
                )
                await asyncio.sleep(wait)
                continue

            if expected is not None:
                if response.status_code not in expected:
                    response.raise_for_status()
            else:
                response.raise_for_status()

            # A tiny pacing gap makes large bootstrap runs friendlier to
            # per-route buckets without making normal single actions sluggish.
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                await asyncio.sleep(0.08)
            return response

    if last_response is not None:
        last_response.raise_for_status()
    raise RuntimeError("Discord request failed without a response.")


async def preflight(guild_id: str, require_community: bool) -> dict[str, Any]:
    if not configured() or guild_id != settings.discord_hq_guild_id:
        raise RuntimeError(
            "Pitmark HQ guild/owner settings are not configured for this server."
        )

    r = await discord_request("GET", f"{DISCORD_API}/users/@me")
    bot_id = str(r.json()["id"])
    guild = (await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}")).json()
    roles = (
        await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/roles")
    ).json()
    member = (
        await discord_request(
            "GET", f"{DISCORD_API}/guilds/{guild_id}/members/{bot_id}"
        )
    ).json()

    role_ids = {guild_id, *[str(x) for x in member.get("roles") or []]}
    perms = 0
    for role in roles:
        if str(role.get("id")) in role_ids:
            perms |= int(role.get("permissions") or 0)
    if perms & ADMINISTRATOR:
        perms = (1 << 53) - 1

    checks = [
        (MANAGE_CHANNELS, "Manage Channels"),
        (MANAGE_ROLES, "Manage Roles"),
        (MANAGE_GUILD, "Manage Server"),
        (MANAGE_MESSAGES, "Manage Messages"),
        (MODERATE_MEMBERS, "Timeout Members"),
        (KICK_MEMBERS, "Kick Members"),
        (BAN_MEMBERS, "Ban Members"),
        (MOVE_MEMBERS, "Move Members"),
        (MENTION_EVERYONE, "Mention roles"),
    ]
    missing = [label for bit, label in checks if not perms & bit]
    community = "COMMUNITY" in (guild.get("features") or [])
    if require_community and not community:
        raise RuntimeError(
            "Enable Discord Community mode before bootstrap so Pitmark can create Forum channels."
        )
    return {
        "bot_user_id": bot_id,
        "permissions": perms,
        "missing_permissions": missing,
        "community": community,
    }


async def list_roles(guild_id: str) -> list[dict[str, Any]]:
    response = await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/roles")
    return list(response.json())


async def list_channels(guild_id: str) -> list[dict[str, Any]]:
    response = await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/channels")
    return list(response.json())


def _cache_channel(channels: list[dict[str, Any]], value: dict[str, Any]) -> None:
    value_id = str(value.get("id") or "")
    for index, channel in enumerate(channels):
        if str(channel.get("id") or "") == value_id:
            channels[index] = value
            return
    channels.append(value)


async def ensure_structure(
    guild_id: str,
    owner_user_id: str,
    *,
    repair_existing: bool = True,
) -> dict[str, Any]:
    pf = await preflight(guild_id, True)
    if pf["missing_permissions"]:
        raise RuntimeError(
            "Missing HQ bot permissions: "
            + ", ".join(pf["missing_permissions"])
            + ". Re-authorize: "
            + hq_install_url()
        )

    role_map = {str(r.get("name")): r for r in await list_roles(guild_id)}
    role_created = 0
    for name, color, perms in ROLE_SPECS:
        role, made = await ensure_role(
            guild_id,
            role_map.get(name),
            name,
            color,
            perms,
            repair_existing=repair_existing,
        )
        role_map[name] = role
        role_created += int(made)

    await assign_role(guild_id, owner_user_id, str(role_map["Pitmark Owner"]["id"]))

    # Fetch the guild channel list once, then update the in-memory cache as each
    # managed object is created/repaired. The old implementation re-fetched the
    # entire channel list after every single write and unnecessarily burned API
    # quota during bootstrap.
    channels = await list_channels(guild_id)
    channel_map: dict[str, dict[str, Any]] = {}
    cat_created = 0
    channel_created = 0
    bot_id = pf["bot_user_id"]

    for cat_name, children in PUBLIC_CATEGORY_SPECS:
        cat, made = await ensure_category(
            guild_id,
            channels,
            cat_name,
            [
                overwrite(
                    bot_id,
                    1,
                    allow=VIEW_CHANNEL
                    | SEND_MESSAGES
                    | READ_MESSAGE_HISTORY
                    | EMBED_LINKS
                    | ATTACH_FILES
                    | CONNECT
                    | SPEAK,
                )
            ],
            repair_existing=repair_existing,
        )
        cat_created += int(made)
        _cache_channel(channels, cat)

        for name, typ, topic, access, tags in children:
            ch, made_ch = await ensure_channel(
                guild_id,
                channels,
                cat,
                name,
                typ,
                topic,
                channel_overwrites(guild_id, role_map, bot_id, access),
                tags,
                repair_existing=repair_existing,
            )
            channel_map[name] = ch
            channel_created += int(made_ch)
            _cache_channel(channels, ch)
            if made_ch:
                await seed_channel(ch)

    for cat_name, audience, children in PRIVATE_CATEGORY_SPECS:
        cat, made = await ensure_category(
            guild_id,
            channels,
            cat_name,
            private_overwrites(guild_id, role_map, bot_id, audience),
            repair_existing=repair_existing,
        )
        cat_created += int(made)
        _cache_channel(channels, cat)

        for name, typ, topic in children:
            ch, made_ch = await ensure_channel(
                guild_id,
                channels,
                cat,
                name,
                typ,
                topic,
                [],
                None,
                repair_existing=repair_existing,
            )
            channel_map[name] = ch
            channel_created += int(made_ch)
            _cache_channel(channels, ch)

    return {
        "roles_created": role_created,
        "categories_created": cat_created,
        "channels_created": channel_created,
        "role_map": role_map,
        "channel_map": channel_map,
        "bot_user_id": bot_id,
    }


async def ensure_role(
    guild_id: str,
    existing: dict[str, Any] | None,
    name: str,
    color: int,
    perms: int,
    *,
    repair_existing: bool = True,
) -> tuple[dict[str, Any], bool]:
    payload = {
        "name": name,
        "color": color,
        "permissions": str(perms),
        "hoist": name.startswith("Pitmark ") and name != "Pitmark Developer",
        "mentionable": False,
    }
    if existing and not repair_existing:
        return existing, False
    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/guilds/{guild_id}/roles/{existing['id']}",
            reason="Pitmark HQ role sync",
            json=payload,
        )
        return response.json(), False
    response = await discord_request(
        "POST",
        f"{DISCORD_API}/guilds/{guild_id}/roles",
        reason="Pitmark HQ bootstrap",
        json=payload,
    )
    return response.json(), True


async def assign_role(guild_id: str, user_id: str, role_id: str) -> None:
    await discord_request(
        "PUT",
        f"{DISCORD_API}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        reason="Assign Pitmark Owner role",
        expected={200, 204},
    )


async def ensure_category(
    guild_id: str,
    channels: list[dict[str, Any]],
    name: str,
    overwrites: list[dict[str, Any]],
    *,
    repair_existing: bool = True,
) -> tuple[dict[str, Any], bool]:
    existing = next(
        (x for x in channels if x.get("type") == 4 and x.get("name") == name),
        None,
    )
    if existing and not repair_existing:
        return existing, False
    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{existing['id']}",
            reason="Pitmark HQ category sync",
            json={"permission_overwrites": overwrites},
        )
        return response.json(), False
    response = await discord_request(
        "POST",
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        reason="Pitmark HQ bootstrap",
        json={"name": name, "type": 4, "permission_overwrites": overwrites},
    )
    return response.json(), True


async def ensure_channel(
    guild_id: str,
    channels: list[dict[str, Any]],
    cat: dict[str, Any],
    name: str,
    typ: int,
    topic: str | None,
    overwrites: list[dict[str, Any]],
    tags: list[str] | None,
    *,
    repair_existing: bool = True,
) -> tuple[dict[str, Any], bool]:
    existing = next(
        (
            x
            for x in channels
            if x.get("type") == typ
            and x.get("name") == name
            and str(x.get("parent_id") or "") == str(cat["id"])
        ),
        None,
    )
    payload: dict[str, Any] = {
        "name": name,
        "type": typ,
        "parent_id": str(cat["id"]),
    }
    if topic and typ in {0, 5, 15}:
        payload["topic"] = topic
    if overwrites:
        payload["permission_overwrites"] = overwrites
    if typ == 15:
        payload.update(
            {
                "default_auto_archive_duration": 1440,
                "available_tags": [
                    {"name": x, "moderated": False} for x in (tags or [])[:20]
                ],
            }
        )
    if typ == 2:
        payload["bitrate"] = 64000

    if existing and not repair_existing:
        return existing, False
    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{existing['id']}",
            reason="Pitmark HQ channel sync",
            json={k: v for k, v in payload.items() if k != "type"},
        )
        return response.json(), False
    response = await discord_request(
        "POST",
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        reason="Pitmark HQ bootstrap",
        json=payload,
    )
    return response.json(), True


async def seed_channel(channel: dict[str, Any]) -> None:
    if int(channel.get("type") or 0) not in {0, 5}:
        return
    msgs = {
        "welcome": "🏁 **Welcome to Pitmark Racing Co.**\nThis is the live community and support hub for Pitmark Racing Tools, Pitmark services, racing leagues, partners and the racing community. **Leave Your Mark.**",
        "rules": "📜 **Pitmark Community Rules**\n1. Respect other members.\n2. No harassment, hate speech, threats, scams, piracy or spam.\n3. Keep content in the appropriate channel.\n4. Never post passwords, license keys, order details, addresses, email addresses or other sensitive information publicly.\n5. Staff decisions and Discord Terms of Service apply.",
        "pitmark-links": "🔗 **Pitmark Racing Co.**\nWebsite & Store: https://pitmarkracing.com\nPitmark Racing Tools: https://prt.pitmarkracing.com\nNeed help? Use the Support Center below.",
        "service-status": "🟢 **Pitmark services operational**\nThis channel is used for official service-status and incident updates.",
        "common-questions": "❓ **Common Questions**\nFor account, setup, product, order or technical help, open a private ticket in **support-start-here**. Never post sensitive account or order information in public channels.",
        "become-a-partner": "🤝 **Become a Pitmark Partner**\nInterested in partnering as a driver, league, track, creator or racing organization? Visit https://pitmarkracing.com or open a Partnership ticket in the Support Center.",
        "prt-announcements": "🏎️ **Pitmark Racing Tools**\nRelease notes, service notices and major Racing Tools updates will be posted here.",
    }
    if channel.get("name") in msgs:
        await send_message(
            str(channel["id"]), {"content": msgs[str(channel["name"])]}
        )


async def send_message(channel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await discord_request(
        "POST", f"{DISCORD_API}/channels/{channel_id}/messages", json=payload
    )
    return response.json()


async def upsert_panel(channel_id: str, title: str, payload: dict[str, Any]) -> None:
    response = await discord_request(
        "GET",
        f"{DISCORD_API}/channels/{channel_id}/messages",
        params={"limit": 50},
    )
    existing = next(
        (
            message
            for message in response.json()
            if (message.get("embeds") or [])
            and str(message["embeds"][0].get("title") or "") == title
        ),
        None,
    )
    if existing:
        await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel_id}/messages/{existing['id']}",
            json=payload,
        )
    else:
        await discord_request(
            "POST", f"{DISCORD_API}/channels/{channel_id}/messages", json=payload
        )


async def log_named(guild_id: str, name: str, text: str) -> None:
    ch = next(
        (
            x
            for x in await list_channels(guild_id)
            if x.get("name") == name and x.get("type") == 0
        ),
        None,
    )
    if ch:
        await send_message(str(ch["id"]), {"content": text})


async def edit_original(payload: dict[str, Any], content: str) -> None:
    app_id = str(payload.get("application_id") or settings.discord_client_id or "")
    token = str(payload.get("token") or "")
    if not app_id or not token:
        return
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for attempt in range(6):
                response = await client.patch(
                    f"{DISCORD_API}/webhooks/{app_id}/{token}/messages/@original",
                    json={"content": content[:1900]},
                )
                if response.status_code != 429:
                    response.raise_for_status()
                    return
                try:
                    retry_after = float(
                        (response.json() or {}).get("retry_after") or 1.0
                    )
                except (TypeError, ValueError, httpx.DecodingError):
                    retry_after = 1.0
                await asyncio.sleep(max(0.25, retry_after) + 0.20)
            response.raise_for_status()
    except Exception:
        log.exception("Failed to edit deferred Discord response")
