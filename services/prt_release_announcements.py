from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import discord
import httpx

from services import persistent_store
from services.prt_versions import compare_versions
from utils.config import settings

log = logging.getLogger("pitmark.discord.prt_release")

STATE_KEY = "prt_release_last_announced_version"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_CHANGE_ITEMS = 30
MAX_FIELD_CHARS = 1000
_unpersisted_announced_versions: set[str] = set()


def _clean_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        lines: list[str] = []
        for raw in value.replace("\r", "").split("\n"):
            line = raw.strip().lstrip("-•* ").strip()
            if line:
                lines.append(line)
        return lines
    return []


def normalize_release(manifest: dict[str, Any]) -> dict[str, Any]:
    version = str(manifest.get("version") or "").strip().lstrip("v")
    if not version:
        raise ValueError("PRT release manifest is missing version")

    notes_payload = manifest.get("releaseNotes")
    source = manifest
    if notes_payload is not None:
        if not isinstance(notes_payload, dict):
            raise ValueError(f"PRT release {version} has invalid releaseNotes payload")
        notes_version = str(notes_payload.get("version") or "").strip().lstrip("v")
        if not notes_version or notes_version != version:
            raise ValueError(
                f"PRT release-note version mismatch: manifest={version} notes={notes_version or 'missing'}"
            )
        source = notes_payload

    changes = _clean_lines(source.get("changes")) or _clean_lines(source.get("notes"))
    if not changes and source is not manifest:
        changes = _clean_lines(manifest.get("changes")) or _clean_lines(manifest.get("notes"))
    if not changes:
        raise ValueError(f"PRT release {version} has no release notes")

    title = str(source.get("title") or manifest.get("title") or f"PRT v{version}").strip()
    summary = str(
        source.get("summary")
        or manifest.get("summary")
        or "A new Pitmark Racing Tools build is available."
    ).strip()

    return {
        "version": version,
        "title": title[:256],
        "summary": summary[:4000],
        "changes": changes[:MAX_CHANGE_ITEMS],
        "required": bool(manifest.get("required", False)),
    }


def _change_chunks(changes: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""
    for item in changes:
        line = f"• {item}".strip()
        if len(line) > MAX_FIELD_CHARS:
            line = line[: MAX_FIELD_CHARS - 3].rstrip() + "..."
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= MAX_FIELD_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line
    if current:
        chunks.append(current)
    return chunks[:8]


def build_release_embed(release: dict[str, Any]) -> discord.Embed:
    version = str(release["version"])
    embed = discord.Embed(
        title=f"🏁 PRT v{version} IS LIVE",
        description=str(release.get("summary") or "A new Pitmark Racing Tools build is available."),
        color=0xFF5500,
    )

    for index, chunk in enumerate(_change_chunks(list(release.get("changes") or []))):
        embed.add_field(
            name="What changed" if index == 0 else "What changed — continued",
            value=chunk,
            inline=False,
        )

    embed.add_field(
        name="Update",
        value=(
            "Open PRT to update automatically, or download the latest Windows build from "
            "https://prt.pitmarkracing.com/"
        ),
        inline=False,
    )
    if release.get("required"):
        embed.add_field(
            name="Update status",
            value="This release is marked as a required update.",
            inline=False,
        )
    embed.set_footer(text="Pitmark Racing Co. • Leave Your Mark.")
    return embed


async def fetch_manifest(client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    target = (settings.prt_release_manifest_url or "").strip()
    if not target.startswith("https://"):
        raise ValueError("PRT release manifest URL must use HTTPS")

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    try:
        async with client.stream(
            "GET",
            target,
            headers={"Cache-Control": "no-cache", "User-Agent": "PitmarkCloud-ReleaseWatcher/1.0"},
        ) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_MANIFEST_BYTES:
                    raise ValueError("PRT release manifest exceeded 64 KiB")
        payload = json.loads(bytes(raw).decode("utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("PRT release manifest must be a JSON object")
        return payload
    finally:
        if owns_client:
            await client.aclose()


def _hq_guild(bot: discord.Client):
    target = (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()
    if not target:
        return None
    return next((guild for guild in getattr(bot, "guilds", []) if str(guild.id) == target), None)


def _channel_type_name(channel: Any) -> str:
    channel_type = getattr(channel, "type", "")
    if isinstance(channel_type, str):
        return channel_type.strip().lower()
    return str(getattr(channel_type, "name", channel_type) or "").strip().lower()


def _announcement_channel(guild: Any):
    wanted = (settings.prt_release_announcement_channel or "prt-announcements").strip().lower()
    for channel in getattr(guild, "channels", []):
        if str(getattr(channel, "name", "")).strip().lower() != wanted:
            continue
        if _channel_type_name(channel) not in {"text", "news"}:
            continue
        if callable(getattr(channel, "send", None)):
            return channel
    return None


async def run_once(
    bot: discord.Client,
    *,
    fetcher: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    get_state: Callable[[str], str | None] | None = None,
    set_state: Callable[[str, str], None] | None = None,
) -> str:
    fetch_release = fetcher or fetch_manifest
    read_state = get_state or persistent_store.get_runtime_state
    write_state = set_state or persistent_store.set_runtime_state

    try:
        release = normalize_release(await fetch_release())
    except Exception:
        log.exception("Unable to load valid PRT release manifest")
        return "failed"

    version = release["version"]
    try:
        previous = read_state(STATE_KEY)
    except Exception:
        log.exception("Unable to read PRT release announcement state")
        return "failed"

    if previous is None:
        try:
            write_state(STATE_KEY, version)
        except Exception:
            log.exception("Unable to bootstrap PRT release announcement state")
            return "failed"
        log.info("Bootstrapped PRT release announcement baseline at v%s.", version)
        return "bootstrapped"

    comparison = compare_versions(version, previous)
    if comparison is None:
        log.warning(
            "Ignoring unparseable PRT release manifest version %r; latest accepted is v%s.",
            version,
            previous,
        )
        return "stale"
    if comparison < 0:
        log.warning(
            "Ignoring stale PRT release manifest v%s; latest accepted is v%s.",
            version,
            previous,
        )
        return "stale"
    if comparison == 0 or version in _unpersisted_announced_versions:
        return "unchanged"

    guild = _hq_guild(bot)
    channel = _announcement_channel(guild) if guild is not None else None
    if channel is None:
        log.warning(
            "PRT release v%s is unannounced because #%s was not found in the Pitmark HQ guild.",
            version,
            settings.prt_release_announcement_channel,
        )
        return "no-channel"

    try:
        await channel.send(
            embed=build_release_embed(release),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except Exception:
        log.exception("Failed to post PRT v%s release announcement to Discord", version)
        return "failed"

    try:
        write_state(STATE_KEY, version)
    except Exception:
        _unpersisted_announced_versions.add(version)
        log.exception(
            "PRT v%s was posted to Discord but durable announcement state could not be saved; "
            "this process will suppress duplicates until restart.",
            version,
        )
        return "failed"

    _unpersisted_announced_versions.discard(version)
    log.info("Posted PRT v%s release announcement to #%s.", version, settings.prt_release_announcement_channel)
    return "posted"


async def watch(bot: discord.Client) -> None:
    if not settings.prt_release_announcements_enabled:
        log.info("PRT release announcements disabled.")
        return

    interval = max(30, int(settings.prt_release_poll_seconds))
    while True:
        try:
            status = await run_once(bot)
            if status in {"posted", "bootstrapped"}:
                log.info("PRT release announcement watcher: %s", status)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("PRT release announcement watcher cycle failed")
        await asyncio.sleep(interval)
