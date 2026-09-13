from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from services import discord_hq_content
from services.discord_hq_common import DISCORD_API, discord_request, list_channels
from services.discord_hq_blueprint import (
    EMBED_LINKS,
    MANAGE_MESSAGES,
    PIN_MESSAGES,
    READ_MESSAGE_HISTORY,
    SEND_MESSAGES,
    VIEW_CHANNEL,
    overwrite,
)
from utils.config import settings

log = logging.getLogger("pitmark.discord.policies")

POLICY_CHANNEL = "policies"
POLICY_CATEGORY = "📌 START HERE"
POLICY_PANEL_TITLE = "Pitmark • 📚 POLICIES & LEGAL"
MANAGED_PANEL_PREFIX = "Pitmark • "

POLICY_LINKS = [
    ("Legal & Policies Hub", "https://pitmarkracing.com/pages/legal"),
    ("Website & Store Terms of Use", "https://pitmarkracing.com/pages/terms"),
    ("Store Privacy Policy", "https://pitmarkracing.com/policies/privacy-policy"),
    ("Return & Refund Policy", "https://pitmarkracing.com/policies/refund-policy"),
    ("Shipping Policy", "https://pitmarkracing.com/policies/shipping-policy"),
    ("Your Privacy Choices", "https://pitmarkracing.com/pages/data-sharing-opt-out"),
    ("PRT Software License & Terms", "https://pitmarkracing.com/pages/prt-terms"),
    ("PRT Privacy Notice", "https://pitmarkracing.com/pages/prt-privacy"),
    ("PRT Early Access Tester Agreement", "https://pitmarkracing.com/pages/prt-early-access-terms"),
    ("Media & Content Submission Terms", "https://pitmarkracing.com/pages/media-submission-terms"),
    ("Creator / Affiliate / Ambassador Terms", "https://pitmarkracing.com/pages/creator-affiliate-terms"),
]

_synced = False


def _configured() -> bool:
    return bool(settings.discord_bot_token and settings.discord_hq_guild_id)


async def _bot_id() -> str:
    response = await discord_request("GET", f"{DISCORD_API}/users/@me")
    return str(response.json()["id"])


def _find(
    channels: list[dict[str, Any]],
    *,
    name: str,
    typ: int | None = None,
) -> dict[str, Any] | None:
    for channel in channels:
        if str(channel.get("name") or "") != name:
            continue
        if typ is not None and int(channel.get("type", -1)) != typ:
            continue
        return channel
    return None


async def _ensure_channel(
    guild_id: str,
    channels: list[dict[str, Any]],
    bot_id: str,
) -> dict[str, Any]:
    category = _find(channels, name=POLICY_CATEGORY, typ=4)
    if not category:
        response = await discord_request(
            "POST",
            f"{DISCORD_API}/guilds/{guild_id}/channels",
            reason="Pitmark legal rollout: create Start Here category for policies",
            json={"name": POLICY_CATEGORY, "type": 4},
        )
        category = response.json()
        channels.append(category)

    channel = _find(channels, name=POLICY_CHANNEL, typ=0)
    permission_overwrites = [
        overwrite(guild_id, 0, deny=SEND_MESSAGES),
        overwrite(
            bot_id,
            1,
            allow=(
                VIEW_CHANNEL
                | SEND_MESSAGES
                | READ_MESSAGE_HISTORY
                | EMBED_LINKS
                | MANAGE_MESSAGES
                | PIN_MESSAGES
            ),
        ),
    ]
    payload = {
        "name": POLICY_CHANNEL,
        "type": 0,
        "topic": (
            "Official Pitmark Racing Co. and Pitmark Racing Tools policies, "
            "terms, privacy notices and legal resources."
        ),
        "parent_id": str(category["id"]),
        "permission_overwrites": permission_overwrites,
    }

    if channel:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel['id']}",
            reason="Pitmark legal rollout: keep policies channel current",
            json=payload,
        )
        return response.json()

    response = await discord_request(
        "POST",
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        reason="Pitmark legal rollout: create policies channel",
        json=payload,
    )
    created = response.json()
    channels.append(created)
    return created


async def _message_history(
    channel_id: str,
    *,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    """Read enough history to find older canonical managed panels."""
    messages: list[dict[str, Any]] = []
    before: str | None = None
    for _ in range(max_pages):
        params: dict[str, Any] = {"limit": 100}
        if before:
            params["before"] = before
        response = await discord_request(
            "GET",
            f"{DISCORD_API}/channels/{channel_id}/messages",
            params=params,
        )
        batch = list(response.json())
        if not batch:
            break
        messages.extend(batch)
        if len(batch) < 100:
            break
        before = str(batch[-1].get("id") or "")
        if not before:
            break
    return messages


def _managed_title(message: dict[str, Any]) -> str:
    embeds = message.get("embeds") or []
    if not embeds:
        return ""
    title = str(embeds[0].get("title") or "")
    return title if title.startswith(MANAGED_PANEL_PREFIX) else ""


async def _cleanup_duplicate_managed_panels(
    channels: list[dict[str, Any]],
    bot_id: str,
) -> dict[str, int]:
    """Undo accidental HQ repainting without touching user/staff messages."""
    channels_checked = 0
    duplicate_messages_removed = 0
    canonical_panels_found = 0

    for channel in channels:
        if int(channel.get("type", -1)) not in {0, 5}:
            continue
        channel_id = str(channel.get("id") or "")
        if not channel_id:
            continue

        history = await _message_history(channel_id)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for message in history:
            author_id = str((message.get("author") or {}).get("id") or "")
            if author_id != bot_id:
                continue
            title = _managed_title(message)
            if title:
                groups[title].append(message)

        if not groups:
            continue
        channels_checked += 1

        for messages in groups.values():
            messages.sort(key=lambda item: int(str(item.get("id") or "0")))
            keeper = messages[0]
            canonical_panels_found += 1
            duplicates = messages[1:]
            if not duplicates:
                continue

            if bool(keeper.get("pinned")) or any(bool(item.get("pinned")) for item in duplicates):
                try:
                    await discord_request(
                        "PUT",
                        f"{DISCORD_API}/channels/{channel_id}/messages/pins/{keeper['id']}",
                        reason="Pitmark HQ repair: preserve original managed panel pin",
                        expected={200, 204},
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("Could not restore original managed panel pin: %s", exc)

            for duplicate in duplicates:
                try:
                    await discord_request(
                        "DELETE",
                        f"{DISCORD_API}/channels/{channel_id}/messages/{duplicate['id']}",
                        reason="Pitmark HQ repair: remove duplicate managed panel",
                        expected={200, 204},
                    )
                    duplicate_messages_removed += 1
                except Exception as exc:  # noqa: BLE001
                    log.warning("Could not remove duplicate managed panel: %s", exc)

    return {
        "channels_checked": channels_checked,
        "canonical_panels_found": canonical_panels_found,
        "duplicates_removed": duplicate_messages_removed,
    }


async def _safe_hq_upsert_panel(
    channel: dict[str, Any],
    *,
    key: str,
    embed: dict[str, Any],
    components: list[dict[str, Any]] | None = None,
    pin: bool = True,
) -> str:
    """Idempotent replacement for the legacy recent-100-message upsert."""
    channel_id = str(channel["id"])
    title = f"{MANAGED_PANEL_PREFIX}{key}"
    embed = dict(embed)
    embed["title"] = title

    bot_id = await _bot_id()
    history = await _message_history(channel_id)
    matches = [
        message
        for message in history
        if str((message.get("author") or {}).get("id") or "") == bot_id
        and _managed_title(message) == title
    ]
    matches.sort(key=lambda item: int(str(item.get("id") or "0")))
    existing = matches[0] if matches else None

    payload: dict[str, Any] = {"embeds": [embed]}
    if components:
        payload["components"] = components

    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel_id}/messages/{existing['id']}",
            json=payload,
        )
        message = response.json()
    else:
        response = await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{channel_id}/messages",
            json=payload,
        )
        message = response.json()

    for duplicate in matches[1:]:
        try:
            await discord_request(
                "DELETE",
                f"{DISCORD_API}/channels/{channel_id}/messages/{duplicate['id']}",
                reason="Pitmark HQ sync repair: remove duplicate managed panel",
                expected={200, 204},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not remove duplicate HQ panel: %s", exc)

    if pin:
        try:
            await discord_request(
                "PUT",
                f"{DISCORD_API}/channels/{channel_id}/messages/pins/{message['id']}",
                reason="Pitmark HQ sync repair: preserve managed panel pin",
                expected={200, 204},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not pin managed HQ panel: %s", exc)

    return str(message["id"])


async def _upsert_policy_panel(channel: dict[str, Any], bot_id: str) -> str:
    channel_id = str(channel["id"])
    messages = await _message_history(channel_id)
    matches = [
        message
        for message in messages
        if str((message.get("author") or {}).get("id") or "") == bot_id
        and _managed_title(message) == POLICY_PANEL_TITLE
    ]
    matches.sort(key=lambda item: int(str(item.get("id") or "0")))
    existing = matches[0] if matches else None

    store_links = "\n".join(
        f"• [{label}]({url})" for label, url in POLICY_LINKS[:6]
    )
    prt_links = "\n".join(
        f"• [{label}]({url})" for label, url in POLICY_LINKS[6:9]
    )
    relationship_links = "\n".join(
        f"• [{label}]({url})" for label, url in POLICY_LINKS[9:]
    )

    embed = {
        "title": POLICY_PANEL_TITLE,
        "description": (
            "This is the official Discord index for Pitmark Racing Co. policies. "
            "The linked pages on **pitmarkracing.com** are the current public versions.\n\n"
            "If a policy is updated, use the website version linked here as the source of truth."
        ),
        "color": 0xFF5500,
        "fields": [
            {"name": "🛍️ Store & Customer Policies", "value": store_links, "inline": False},
            {"name": "🏎️ Pitmark Racing Tools", "value": prt_links, "inline": False},
            {"name": "📸 Media, Creators & Partners", "value": relationship_links, "inline": False},
            {
                "name": "✉️ Questions",
                "value": (
                    "Legal, privacy, rights and policy questions: "
                    "**contact@pitmarkracing.com**"
                ),
                "inline": False,
            },
        ],
        "footer": {
            "text": (
                "Pitmark Racing Co. • Leave Your Mark. • "
                "Updated September 13, 2026"
            )
        },
    }
    payload = {"embeds": [embed]}

    if existing:
        response = await discord_request(
            "PATCH",
            f"{DISCORD_API}/channels/{channel_id}/messages/{existing['id']}",
            json=payload,
        )
        message = response.json()
    else:
        response = await discord_request(
            "POST",
            f"{DISCORD_API}/channels/{channel_id}/messages",
            json=payload,
        )
        message = response.json()

    for duplicate in matches[1:]:
        try:
            await discord_request(
                "DELETE",
                f"{DISCORD_API}/channels/{channel_id}/messages/{duplicate['id']}",
                reason="Pitmark legal rollout: remove duplicate policy panel",
                expected={200, 204},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not remove duplicate Discord policy panel: %s", exc)

    try:
        await discord_request(
            "PUT",
            f"{DISCORD_API}/channels/{channel_id}/messages/pins/{message['id']}",
            reason="Pitmark legal rollout: pin official policy index",
            expected={200, 204},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not pin Discord policy panel: %s", exc)

    return str(message["id"])


async def ensure_policies(*, force: bool = False) -> dict[str, Any]:
    global _synced
    if _synced and not force:
        return {"configured": True, "synced": True, "cached": True}
    if not _configured():
        return {"configured": False, "synced": False}

    guild_id = str(settings.discord_hq_guild_id)
    try:
        channels = await list_channels(guild_id)
        bot_id = await _bot_id()
        cleanup = await _cleanup_duplicate_managed_panels(channels, bot_id)
        channel = await _ensure_channel(guild_id, channels, bot_id)
        message_id = await _upsert_policy_panel(channel, bot_id)
        _synced = True
        return {
            "configured": True,
            "synced": True,
            "cached": False,
            "channel_id": str(channel["id"]),
            "message_id": message_id,
            "cleanup": cleanup,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("Discord policy sync failed")
        return {
            "configured": True,
            "synced": False,
            "error": str(exc)[:500],
        }


# Patch the HQ content layer at import time. This keeps /hq sync compatible with
# the existing command path while replacing the unsafe recent-100-message upsert.
_original_sync_server_content = discord_hq_content.sync_server_content


async def _safe_sync_server_content(guild_id: str) -> dict[str, Any]:
    result = await _original_sync_server_content(guild_id)
    policies = await ensure_policies(force=True)
    result["policies_synced"] = bool(policies.get("synced"))
    result["duplicate_panels_removed"] = int(
        ((policies.get("cleanup") or {}).get("duplicates_removed") or 0)
    )
    return result


discord_hq_content._upsert_panel = _safe_hq_upsert_panel
discord_hq_content.sync_server_content = _safe_sync_server_content
