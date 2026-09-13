from __future__ import annotations

import logging
from typing import Any

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


def _find(channels: list[dict[str, Any]], *, name: str, typ: int | None = None) -> dict[str, Any] | None:
    for channel in channels:
        if str(channel.get("name") or "") != name:
            continue
        if typ is not None and int(channel.get("type", -1)) != typ:
            continue
        return channel
    return None


async def _ensure_channel(guild_id: str, channels: list[dict[str, Any]], bot_id: str) -> dict[str, Any]:
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
        "topic": "Official Pitmark Racing Co. and Pitmark Racing Tools policies, terms, privacy notices and legal resources.",
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
    return response.json()


async def _recent_messages(channel_id: str) -> list[dict[str, Any]]:
    response = await discord_request(
        "GET",
        f"{DISCORD_API}/channels/{channel_id}/messages",
        params={"limit": 100},
    )
    return list(response.json())


async def _upsert_policy_panel(channel: dict[str, Any]) -> str:
    channel_id = str(channel["id"])
    messages = await _recent_messages(channel_id)
    existing = next(
        (
            message
            for message in messages
            if (message.get("embeds") or [])
            and str(message["embeds"][0].get("title") or "") == POLICY_PANEL_TITLE
        ),
        None,
    )

    store_links = "\n".join(
        f"• [{label}]({url})"
        for label, url in POLICY_LINKS[:6]
    )
    prt_links = "\n".join(
        f"• [{label}]({url})"
        for label, url in POLICY_LINKS[6:9]
    )
    relationship_links = "\n".join(
        f"• [{label}]({url})"
        for label, url in POLICY_LINKS[9:]
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
                "value": "Legal, privacy, rights and policy questions: **contact@pitmarkracing.com**",
                "inline": False,
            },
        ],
        "footer": {"text": "Pitmark Racing Co. • Leave Your Mark. • Updated September 13, 2026"},
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

    try:
        await discord_request(
            "PUT",
            f"{DISCORD_API}/channels/{channel_id}/messages/pins/{message['id']}",
            reason="Pitmark legal rollout: pin official policy index",
            expected={200, 204},
        )
    except Exception as exc:  # noqa: BLE001 - pin failure should not undo channel sync
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
        channel = await _ensure_channel(guild_id, channels, bot_id)
        message_id = await _upsert_policy_panel(channel)
        _synced = True
        return {
            "configured": True,
            "synced": True,
            "cached": False,
            "channel_id": str(channel["id"]),
            "message_id": message_id,
        }
    except Exception as exc:  # noqa: BLE001 - status endpoint should remain available
        log.exception("Discord policy sync failed")
        return {
            "configured": True,
            "synced": False,
            "error": str(exc)[:500],
        }
