from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import logging

import discord
import httpx

from utils.config import settings
from services.discord_hq_common import log_named
from services import discord_hq_moderation

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


BUG_INTAKE_TITLE = "Thanks for reporting this — help us reproduce it"
_member_message_times: dict[tuple[int, int], deque[float]] = defaultdict(deque)
_flood_cooldowns: dict[tuple[int, int], float] = {}


def _is_hq_guild(guild: discord.Guild | None) -> bool:
    configured_id = (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()
    return bool(guild and configured_id and str(guild.id) == configured_id)


def _bug_intake_embed() -> discord.Embed:
    embed = discord.Embed(
        title=BUG_INTAKE_TITLE,
        description=(
            "A Pitmark team member will review this thread. The details below usually let us "
            "find the problem much faster. Add anything missing in a reply — you do not need "
            "to repost the thread."
        ),
        color=0xFF5500,
    )
    embed.add_field(
        name="Please include",
        value=(
            "• PRT version (shown at the bottom of the app)\n"
            "• Car, track, and session type\n"
            "• What you expected vs. what happened\n"
            "• Steps that make it happen again\n"
            "• Screenshot or short video, if possible"
        ),
        inline=False,
    )
    embed.add_field(
        name="If it crashed or froze",
        value=(
            "Tell us what else was running (streaming/recording included), whether the overlays "
            "returned, and attach the PRT diagnostic log if available."
        ),
        inline=False,
    )
    embed.add_field(
        name="Keep private information private",
        value=(
            "Do not post passwords, activation codes, order details, email addresses, or tokens. "
            "Open a private support ticket for account-specific help."
        ),
        inline=False,
    )
    embed.set_footer(text="Pitmark Racing Tools • Leave Your Mark.")
    return embed


async def _audit(guild: discord.Guild, text: str, *, moderation: bool = False) -> None:
    if not settings.discord_audit_logging_enabled or not _is_hq_guild(guild):
        return
    try:
        await log_named(str(guild.id), "moderation-log" if moderation else "bot-logs", text[:1900])
    except Exception:
        log.exception("Failed to write Discord audit event")


def _staff_exempt(member: discord.Member) -> bool:
    permissions = member.guild_permissions
    return bool(
        permissions.administrator
        or permissions.manage_guild
        or permissions.manage_messages
        or permissions.moderate_members
    )


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
        try:
            guild = next((item for item in self.guilds if _is_hq_guild(item)), None)
            if guild:
                role_map = {role.name: {"id": str(role.id)} for role in guild.roles}
                channel_map = {
                    channel.name: {"id": str(channel.id), "name": channel.name, "type": 0}
                    for channel in guild.channels
                }
                count = await discord_hq_moderation.sync_automod(
                    str(guild.id), role_map, channel_map
                )
                log.info("Synced %s Pitmark AutoMod rules on Gateway ready.", count)
        except Exception:
            # AutoMod repair must not prevent support intake or bot presence.
            log.exception("Failed to sync Pitmark AutoMod rules on Gateway ready.")

    async def on_thread_create(self, thread: discord.Thread) -> None:
        if not settings.discord_support_automation_enabled or not _is_hq_guild(thread.guild):
            return
        parent_name = str(getattr(thread.parent, "name", "") or "").lower()
        if parent_name != (settings.discord_bug_forum_name or "prt-bug-reports").strip().lower():
            return
        try:
            await thread.send(embed=_bug_intake_embed(), allowed_mentions=discord.AllowedMentions.none())
            await _audit(
                thread.guild,
                f"🐞 **BUG THREAD OPENED** • {thread.mention}\nOpened by: "
                f"<@{thread.owner_id}>\nThread ID: `{thread.id}`",
            )
        except discord.Forbidden:
            log.warning("Cannot reply to bug thread %s; check Send Messages in Threads permission.", thread.id)
        except Exception:
            log.exception("Failed to send bug-report intake reply")

    async def on_thread_delete(self, thread: discord.Thread) -> None:
        if _is_hq_guild(thread.guild):
            await _audit(thread.guild, f"🗑️ **THREAD DELETED** • `{thread.name}` (`{thread.id}`)")

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        if _is_hq_guild(channel.guild):
            await _audit(channel.guild, f"➕ **CHANNEL CREATED** • {channel.mention} (`{channel.id}`)")

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        if _is_hq_guild(channel.guild):
            await _audit(channel.guild, f"➖ **CHANNEL DELETED** • `#{channel.name}` (`{channel.id}`)")

    async def on_member_join(self, member: discord.Member) -> None:
        if not _is_hq_guild(member.guild):
            return
        age = datetime.now(timezone.utc) - member.created_at
        flags = []
        if member.bot:
            flags.append("bot account")
        if age < timedelta(days=1):
            flags.append("account under 24 hours old")
        suffix = f"\n⚠️ Review: {', '.join(flags)}" if flags else ""
        await _audit(
            member.guild,
            f"📥 **MEMBER JOINED** • {member.mention} (`{member.id}`)\n"
            f"Account created: <t:{int(member.created_at.timestamp())}:R>{suffix}",
            moderation=bool(flags),
        )

    async def on_member_remove(self, member: discord.Member) -> None:
        if _is_hq_guild(member.guild):
            await _audit(member.guild, f"📤 **MEMBER LEFT** • `{member}` (`{member.id}`)")

    async def on_message_delete(self, message: discord.Message) -> None:
        if message.guild and _is_hq_guild(message.guild) and not message.author.bot:
            await _audit(
                message.guild,
                f"🗑️ **MESSAGE DELETED** • {message.author.mention} in {message.channel.mention}\n"
                f"Message ID: `{message.id}`",
            )

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if (
            before.guild
            and _is_hq_guild(before.guild)
            and not before.author.bot
            and before.content != after.content
        ):
            await _audit(
                before.guild,
                f"✏️ **MESSAGE EDITED** • {before.author.mention} in {before.channel.mention}\n"
                f"Message ID: `{before.id}`",
            )

    async def on_message(self, message: discord.Message) -> None:
        if (
            not settings.discord_flood_protection_enabled
            or not message.guild
            or not _is_hq_guild(message.guild)
            or message.author.bot
            or not isinstance(message.author, discord.Member)
            or _staff_exempt(message.author)
        ):
            return

        now = asyncio.get_running_loop().time()
        key = (message.guild.id, message.author.id)
        window = max(3, int(settings.discord_flood_window_seconds))
        limit = max(4, int(settings.discord_flood_message_limit))
        timestamps = _member_message_times[key]
        while timestamps and timestamps[0] < now - window:
            timestamps.popleft()
        timestamps.append(now)
        if len(timestamps) < limit or _flood_cooldowns.get(key, 0) > now:
            return

        _flood_cooldowns[key] = now + 60
        timestamps.clear()
        minutes = max(1, min(60, int(settings.discord_flood_timeout_minutes)))
        try:
            await message.delete(reason="Pitmark flood protection")
            await message.author.timeout(
                timedelta(minutes=minutes),
                reason=f"Pitmark flood protection: {limit} messages in {window} seconds",
            )
            await _audit(
                message.guild,
                f"🚨 **FLOOD PROTECTION** • {message.author.mention}\n"
                f"Detected at least {limit} messages in {window}s; applied a {minutes}-minute timeout.",
                moderation=True,
            )
        except discord.Forbidden:
            await _audit(
                message.guild,
                f"⚠️ **FLOOD DETECTED — ACTION FAILED** • {message.author.mention}\n"
                "Check the bot's Manage Messages / Moderate Members permissions and role position.",
                moderation=True,
            )
        except Exception:
            log.exception("Discord flood-protection action failed")


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
    intents.guilds = True
    intents.guild_messages = True
    intents.members = settings.discord_privileged_intents_enabled
    intents.message_content = settings.discord_privileged_intents_enabled
    intents.moderation = True
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
