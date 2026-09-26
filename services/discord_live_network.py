from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any

import discord

from services import guild_config_service, persistent_store
from services.racing_events import get_racing_event_hub
from utils.config import settings

log = logging.getLogger("pitmark.discord.live_network")

ALERT_PREFIX = "discord_live_network_config:"
DEDUPE_PREFIX = "discord_live_network_posted:"
MANUAL_EVENTS_KEY = "discord_live_network_manual_events"
POLL_PREFIX = "discord_poll:"
RACE_CENTER_URL = "https://links.pitmarkracing.com/race-center"


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return value


def _csv_tokens(value: str | None) -> list[str]:
    return [
        token.strip().casefold()
        for token in str(value or "").split(",")
        if token.strip()
    ]


def has_alert_config(guild_id: str) -> bool:
    return persistent_store.get_runtime_state(f"{ALERT_PREFIX}{guild_id}") is not None


def get_alert_config(guild_id: str) -> dict[str, Any]:
    raw = persistent_store.get_runtime_state(f"{ALERT_PREFIX}{guild_id}")
    value = _loads(raw, {})
    if not isinstance(value, dict):
        value = {}
    return {
        "enabled": bool(value.get("enabled", False)),
        "channel_id": str(value.get("channel_id") or ""),
        "series": [str(x).casefold() for x in value.get("series") or [] if str(x).strip()],
        "tracks": [str(x).casefold() for x in value.get("tracks") or [] if str(x).strip()],
        "updated_by": str(value.get("updated_by") or ""),
    }


def set_alert_config(
    guild_id: str,
    *,
    enabled: bool,
    channel_id: str = "",
    series: str | None = None,
    tracks: str | None = None,
    updated_by: str = "",
) -> dict[str, Any]:
    current = get_alert_config(guild_id)
    value = {
        "enabled": bool(enabled),
        "channel_id": str(channel_id or current.get("channel_id") or ""),
        "series": _csv_tokens(series) if series is not None else current.get("series", []),
        "tracks": _csv_tokens(tracks) if tracks is not None else current.get("tracks", []),
        "updated_by": str(updated_by or current.get("updated_by") or ""),
    }
    persistent_store.set_runtime_state(
        f"{ALERT_PREFIX}{guild_id}",
        json.dumps(value, separators=(",", ":"), sort_keys=True),
    )
    return value


def _event_search_text(item: dict[str, Any]) -> str:
    event = item.get("event") or {}
    return " ".join(
        str(value or "")
        for value in (
            item.get("series_name"),
            item.get("series_key"),
            item.get("group"),
            event.get("name"),
            event.get("venue"),
            event.get("location"),
        )
    ).casefold()


def matches_config(item: dict[str, Any], config: dict[str, Any]) -> bool:
    if not config.get("enabled"):
        return False
    haystack = _event_search_text(item)
    series = [str(x).casefold() for x in config.get("series") or []]
    tracks = [str(x).casefold() for x in config.get("tracks") or []]
    if series and not any(token in haystack for token in series):
        return False
    if tracks and not any(token in haystack for token in tracks):
        return False
    return True


def event_key(item: dict[str, Any]) -> str:
    event = item.get("event") or {}
    raw = "|".join(
        str(value or "")
        for value in (
            item.get("series_key"),
            item.get("series_name"),
            event.get("name"),
            event.get("start"),
            event.get("venue"),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _parse_start(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _discord_time(value: str | None) -> str:
    parsed = _parse_start(value)
    if not parsed:
        return "Start time unavailable"
    stamp = int(parsed.timestamp())
    return f"<t:{stamp}:F> • <t:{stamp}:R>"


def event_embed(item: dict[str, Any], *, live: bool | None = None) -> discord.Embed:
    event = item.get("event") or {}
    is_live = bool(item.get("state") == "live" if live is None else live)
    title = str(event.get("name") or item.get("series_name") or "Racing Event")[:250]
    series = str(item.get("series_name") or "Racing")
    venue = str(event.get("venue") or event.get("location") or "Venue TBA")
    state_label = "🔴 LIVE NOW" if is_live else "🗓️ UP NEXT"

    embed = discord.Embed(
        title=f"{state_label} • {title}",
        description=f"**{series}**\n{venue}\n{_discord_time(event.get('start'))}",
        color=0xFF5500,
    )
    broadcast = str(event.get("broadcast") or item.get("watch_name") or "").strip()
    if broadcast:
        embed.add_field(name="Watch", value=broadcast[:1000], inline=True)

    links: list[str] = [f"[Race Center]({RACE_CENTER_URL})"]
    watch_url = str(item.get("watch_url") or event.get("event_url") or "").strip()
    official_url = str(event.get("source_url") or item.get("schedule_url") or "").strip()
    timing_url = str(event.get("timing_url") or "").strip()
    results_url = str(event.get("results_url") or "").strip()
    if watch_url.startswith("http"):
        links.append(f"[Watch / Event]({watch_url})")
    if timing_url.startswith("http"):
        links.append(f"[Timing]({timing_url})")
    if results_url.startswith("http"):
        links.append(f"[Results]({results_url})")
    if official_url.startswith("http") and official_url != watch_url:
        links.append(f"[Official]({official_url})")
    embed.add_field(name="Links", value=" • ".join(links)[:1000], inline=False)
    embed.set_footer(text="Pitmark Race Center Live Network • Leave Your Mark.")
    return embed


def _manual_events() -> list[dict[str, Any]]:
    value = _loads(persistent_store.get_runtime_state(MANUAL_EVENTS_KEY), [])
    if not isinstance(value, list):
        return []
    now = datetime.now(timezone.utc)
    kept: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        expires = _parse_start(str(item.get("expires_at") or ""))
        if expires and expires < now:
            continue
        kept.append(item)
    if kept != value:
        persistent_store.set_runtime_state(MANUAL_EVENTS_KEY, json.dumps(kept, separators=(",", ":")))
    return kept


def add_manual_live_event(
    *,
    title: str,
    series: str = "Grassroots / Community",
    track: str = "",
    watch_url: str = "",
    info_url: str = "",
    duration_minutes: int = 180,
    submitted_by: str = "",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    duration = max(30, min(720, int(duration_minutes or 180)))
    item = {
        "state": "live",
        "series_key": "manual-community",
        "series_name": str(series or "Grassroots / Community")[:120],
        "group": "Community Submission",
        "watch_name": "Community live event",
        "watch_url": str(watch_url or "")[:1000],
        "schedule_url": str(info_url or "")[:1000],
        "event": {
            "name": str(title or "Community race")[:250],
            "start": now.isoformat(),
            "venue": str(track or "")[:180] or None,
            "location": None,
            "broadcast": None,
            "event_url": str(watch_url or "")[:1000] or None,
            "source_url": str(info_url or "")[:1000] or None,
        },
        "submitted_by": str(submitted_by or ""),
        "expires_at": (now + timedelta(minutes=duration)).isoformat(),
    }
    events = _manual_events()
    events.append(item)
    persistent_store.set_runtime_state(
        MANUAL_EVENTS_KEY,
        json.dumps(events[-100:], separators=(",", ":")),
    )
    return item


def live_items() -> list[dict[str, Any]]:
    hub = get_racing_event_hub(force=False)
    items = list(hub.get("live") or [])
    items.extend(_manual_events())
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = event_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def upcoming_items(limit: int = 8) -> list[dict[str, Any]]:
    hub = get_racing_event_hub(force=False)
    return list(hub.get("next") or [])[: max(1, min(10, int(limit or 8)))]


def live_response_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "type": 4,
            "data": {
                "content": f"🏁 Nothing is marked live in Race Center right now.\n{RACE_CENTER_URL}",
            },
        }
    embeds = [event_embed(item, live=True).to_dict() for item in items[:10]]
    return {"type": 4, "data": {"embeds": embeds}}


def upcoming_response_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "type": 4,
            "data": {
                "content": f"🏁 Race Center does not have a confirmed upcoming event in the current feed yet.\n{RACE_CENTER_URL}",
            },
        }
    embeds = [event_embed(item, live=False).to_dict() for item in items[:10]]
    return {"type": 4, "data": {"embeds": embeds}}


async def watch(bot: discord.Client) -> None:
    interval = max(60, int(getattr(settings, "discord_live_network_poll_seconds", 120)))
    while True:
        try:
            await run_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Race Center Live Network cycle failed")
        await asyncio.sleep(interval)


async def run_once(bot: discord.Client) -> int:
    items = await asyncio.to_thread(live_items)
    if not items:
        return 0

    configs = guild_config_service.all_enabled()
    posted = 0
    for guild_config in configs:
        guild_id = str(guild_config.get("guild_id") or "")
        alert_config = get_alert_config(guild_id)
        if not alert_config.get("enabled"):
            continue
        channel_id = str(alert_config.get("channel_id") or guild_config.get("share_channel_id") or "")
        if not channel_id:
            continue
        channel = bot.get_channel(int(channel_id)) if channel_id.isdigit() else None
        if channel is None or not callable(getattr(channel, "send", None)):
            continue

        for item in items:
            if not matches_config(item, alert_config):
                continue
            key = event_key(item)
            dedupe_key = f"{DEDUPE_PREFIX}{guild_id}:{key}"
            if persistent_store.get_runtime_state(dedupe_key):
                continue
            try:
                await channel.send(
                    embed=event_embed(item, live=True),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                log.exception("Failed to post Race Center live event %s to guild %s", key, guild_id)
                continue
            persistent_store.set_runtime_state(dedupe_key, datetime.now(timezone.utc).isoformat())
            posted += 1
    return posted


def _poll_key(poll_id: str) -> str:
    return f"{POLL_PREFIX}{poll_id}"


def _poll_components(poll_id: str, options: list[str]) -> list[dict[str, Any]]:
    buttons = []
    labels = ["A", "B", "C", "D", "E"]
    for index, option in enumerate(options[:5]):
        buttons.append(
            {
                "type": 2,
                "style": 2,
                "label": f"{labels[index]} • {option}"[:80],
                "custom_id": f"pitmark_poll:{poll_id}:{index}",
            }
        )
    return [{"type": 1, "components": buttons}]


def _poll_embed(state: dict[str, Any]) -> dict[str, Any]:
    options = list(state.get("options") or [])
    votes = dict(state.get("votes") or {})
    counts = [0 for _ in options]
    for raw_index in votes.values():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(counts):
            counts[index] += 1
    labels = ["A", "B", "C", "D", "E"]
    lines = [
        f"**{labels[index]}. {option}** — {counts[index]} vote{'s' if counts[index] != 1 else ''}"
        for index, option in enumerate(options)
    ]
    return {
        "title": f"📊 {str(state.get('question') or 'Pitmark Poll')[:240]}",
        "description": "\n".join(lines),
        "color": 16733440,
        "footer": {
            "text": f"{len(votes)} total vote{'s' if len(votes) != 1 else ''} • Click an option to vote or change your vote."
        },
    }


def create_poll(
    *,
    guild_id: str,
    user_id: str,
    question: str,
    options: list[str],
) -> dict[str, Any]:
    clean = [str(option).strip()[:70] for option in options if str(option).strip()]
    if len(clean) < 2:
        raise ValueError("A poll needs at least two options.")
    clean = clean[:5]
    seed = f"{guild_id}|{user_id}|{question}|{time_token()}"
    poll_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    state = {
        "id": poll_id,
        "guild_id": str(guild_id or ""),
        "created_by": str(user_id or ""),
        "question": str(question or "Pitmark Poll").strip()[:240],
        "options": clean,
        "votes": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    persistent_store.set_runtime_state(_poll_key(poll_id), json.dumps(state, separators=(",", ":")))
    return {
        "type": 4,
        "data": {
            "embeds": [_poll_embed(state)],
            "components": _poll_components(poll_id, clean),
            "allowed_mentions": {"parse": []},
        },
    }


def time_token() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def vote_poll(custom_id: str, user_id: str) -> dict[str, Any]:
    try:
        _, poll_id, raw_index = custom_id.split(":", 2)
        index = int(raw_index)
    except (ValueError, TypeError):
        return {"type": 4, "data": {"content": "That poll button is invalid.", "flags": 64}}

    state = _loads(persistent_store.get_runtime_state(_poll_key(poll_id)), None)
    if not isinstance(state, dict):
        return {"type": 4, "data": {"content": "That poll is no longer available.", "flags": 64}}

    options = list(state.get("options") or [])
    if index < 0 or index >= len(options):
        return {"type": 4, "data": {"content": "That poll option is invalid.", "flags": 64}}

    votes = dict(state.get("votes") or {})
    votes[str(user_id)] = index
    state["votes"] = votes
    persistent_store.set_runtime_state(_poll_key(poll_id), json.dumps(state, separators=(",", ":")))
    return {
        "type": 7,
        "data": {
            "embeds": [_poll_embed(state)],
            "components": _poll_components(poll_id, options),
            "allowed_mentions": {"parse": []},
        },
    }
