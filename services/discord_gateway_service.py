from __future__ import annotations

import asyncio
import logging

import discord
import httpx

from utils.config import settings

log = logging.getLogger("pitmark.discord.gateway")
DISCORD_API = "https://discord.com/api/v10"


def configured() -> bool:
    return bool(settings.discord_gateway_enabled and settings.discord_bot_token)


def _activity() -> discord.BaseActivity | None:
    text = (settings.discord_presence_text or "Pitmark Racing Tools").strip()
    if not text:
        return None

    presence_type = (settings.discord_presence_type or "watching").strip().lower()

    if presence_type == "playing":
        return discord.Game(name=text)
    if presence_type == "listening":
        return discord.Activity(type=discord.ActivityType.listening, name=text)
    if presence_type == "competing":
        return discord.Activity(type=discord.ActivityType.competing, name=text)

    return discord.Activity(type=discord.ActivityType.watching, name=text)


def _link_button(label: str, url: str, emoji: str) -> dict:
    return {
        "type": 2,
        "style": 5,
        "label": label,
        "url": url,
        "emoji": {"name": emoji},
    }


def _official_links_payload(guild_id: str, support_channel_id: str | None) -> dict:
    support_line = (
        f"Use <#{support_channel_id}> for private help, bugs, setup help, or account questions."
        if support_channel_id
        else "Use the Pitmark support section for private help, bugs, setup help, or account questions."
    )
    support_url = (
        f"https://discord.com/channels/{guild_id}/{support_channel_id}"
        if support_channel_id
        else "https://discord.gg/jP6fQuW7dr"
    )

    return {
        "content": "",
        "embeds": [
            {
                "title": "Pitmark • 🔗 OFFICIAL PITMARK LINKS",
                "description": (
                    "Everything official, in one place — no mystery downloads, no random DMs, no sketchy mirrors.\n\n"
                    "🏁 **Pitmark Racing Co.**\nhttps://pitmarkracing.com/\n\n"
                    "🧰 **Pitmark Racing Tools**\nhttps://prt.pitmarkracing.com/\n\n"
                    "🧪 **PRT Early Access**\nhttps://prt.pitmarkracing.com/prt/apply\n\n"
                    "🔗 **Pitmark Links Hub**\nhttps://links.pitmarkracing.com/links\n\n"
                    "📸 **Instagram** — https://www.instagram.com/pitmarkracing\n"
                    "🎵 **TikTok** — https://www.tiktok.com/@pitmarkracing\n"
                    "📘 **Facebook** — https://www.facebook.com/profile.php?id=61593441036636\n"
                    "𝕏 **X** — https://x.com/pitmarkracing\n"
                    "▶️ **YouTube** — https://www.youtube.com/@pitmarkracing\n"
                    "💬 **Discord** — https://discord.gg/jP6fQuW7dr\n\n"
                    f"🛟 **Discord Support**\n{support_line}"
                ),
                "color": 16733440,
                "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
            }
        ],
        "components": [
            {
                "type": 1,
                "components": [
                    _link_button("Pitmark Website", "https://pitmarkracing.com/", "🏁"),
                    _link_button("Racing Tools", "https://prt.pitmarkracing.com/", "🧰"),
                    _link_button("Early Access", "https://prt.pitmarkracing.com/prt/apply", "🧪"),
                    _link_button("Links Hub", "https://links.pitmarkracing.com/links", "🔗"),
                    _link_button("Support", support_url, "🛟"),
                ],
            },
            {
                "type": 1,
                "components": [
                    _link_button("Instagram", "https://www.instagram.com/pitmarkracing", "📸"),
                    _link_button("TikTok", "https://www.tiktok.com/@pitmarkracing", "🎵"),
                    _link_button("Facebook", "https://www.facebook.com/profile.php?id=61593441036636", "📘"),
                    _link_button("X", "https://x.com/pitmarkracing", "✖️"),
                    _link_button("YouTube", "https://www.youtube.com/@pitmarkracing", "▶️"),
                ],
            },
            {
                "type": 1,
                "components": [
                    _link_button("Discord", "https://discord.gg/jP6fQuW7dr", "💬"),
                ],
            },
        ],
        "allowed_mentions": {"parse": []},
    }


async def _sync_official_links_message(bot_user_id: str) -> None:
    guild_id = (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()
    if not guild_id or not settings.discord_bot_token:
        log.info("Official links sync skipped: HQ guild or bot token not configured.")
        return

    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        channels_response = await client.get(f"{DISCORD_API}/guilds/{guild_id}/channels", headers=headers)
        channels_response.raise_for_status()
        channels = channels_response.json()

        links_channel = next(
            (
                channel for channel in channels
                if str(channel.get("name") or "").lower() == "pitmark-links" and int(channel.get("type") or 0) in {0, 5}
            ),
            None,
        )
        support_channel = next(
            (
                channel for channel in channels
                if str(channel.get("name") or "").lower() == "support-start-here" and int(channel.get("type") or 0) in {0, 5}
            ),
            None,
        )

        if not links_channel:
            log.warning("Official links sync skipped: #pitmark-links was not found in HQ guild %s.", guild_id)
            return

        channel_id = str(links_channel.get("id"))
        support_channel_id = str(support_channel.get("id")) if support_channel else None
        payload = _official_links_payload(guild_id, support_channel_id)

        messages_response = await client.get(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=headers,
            params={"limit": 50},
        )
        messages_response.raise_for_status()
        messages = messages_response.json()

        existing = None
        for message in messages:
            author_id = str((message.get("author") or {}).get("id") or "")
            if author_id != bot_user_id:
                continue
            embeds = message.get("embeds") or []
            title = str((embeds[0] if embeds else {}).get("title") or "")
            content = str(message.get("content") or "")
            if "OFFICIAL PITMARK LINKS" in title.upper() or "OFFICIAL PITMARK LINKS" in content.upper():
                existing = message
                break

        if existing:
            message_id = str(existing.get("id"))
            response = await client.patch(
                f"{DISCORD_API}/channels/{channel_id}/messages/{message_id}",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            log.info("Updated official Pitmark links message in #%s.", links_channel.get("name"))
            return

        response = await client.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        log.info("Created official Pitmark links message in #%s.", links_channel.get("name"))


class PitmarkPresenceClient(discord.Client):
    async def on_ready(self) -> None:
        await self.change_presence(
            status=discord.Status.online,
            activity=_activity(),
        )
        log.info(
            "Pitmark Discord Gateway connected as %s (%s)",
            self.user,
            getattr(self.user, "id", "unknown"),
        )
        try:
            await _sync_official_links_message(str(getattr(self.user, "id", "")))
        except Exception:
            # Presence and HTTP interactions must stay online even if the links card cannot sync.
            log.exception("Failed to sync official Pitmark links message.")


_client: PitmarkPresenceClient | None = None
_task: asyncio.Task | None = None


async def start() -> None:
    global _client, _task

    if not configured():
        log.info("Discord Gateway presence disabled or DISCORD_BOT_TOKEN missing.")
        return

    if _task and not _task.done():
        return

    intents = discord.Intents.none()
    _client = PitmarkPresenceClient(intents=intents)

    async def runner() -> None:
        try:
            await _client.start(settings.discord_bot_token)
        except asyncio.CancelledError:
            raise
        except Exception:
            # HTTP interactions remain independent even if Gateway presence fails.
            log.exception("Pitmark Discord Gateway connection stopped unexpectedly.")

    _task = asyncio.create_task(runner(), name="pitmark-discord-gateway")


async def stop() -> None:
    global _client, _task

    if _client and not _client.is_closed():
        try:
            await _client.close()
        except Exception:
            log.exception("Error closing Pitmark Discord Gateway client.")

    if _task:
        if not _task.done():
            _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    _client = None
    _task = None


def state() -> dict:
    return {
        "configured": configured(),
        "connected": bool(_client and _client.is_ready()),
        "user": str(_client.user) if _client and _client.user else None,
        "presence_text": settings.discord_presence_text,
        "presence_type": settings.discord_presence_type,
        "note": "Designed for an always-on Pitmark Cloud web service. HTTP interactions remain independent of Gateway presence.",
    }
