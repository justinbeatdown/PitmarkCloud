from __future__ import annotations

import asyncio
import logging

import discord

from utils.config import settings

log = logging.getLogger("pitmark.discord.gateway")


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
        "note": "Best-effort on Render Free; bot goes Offline if the service sleeps.",
    }
