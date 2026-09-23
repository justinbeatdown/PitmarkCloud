from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from sqlalchemy import select

from services.database import SessionLocal
from services.racing_events import (
    SERIES_EVENT_CONFIG,
    get_racing_event_hub,
    get_series_event_schedule,
)
from services.racing_standings import (
    RacingStandingSnapshot,
    get_standings_snapshot_hub,
)
from services import race_center_accounts


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return clean[:120] or "racing"


def event_key(series_key: str, event: dict[str, Any]) -> str:
    raw = "|".join(
        (
            str(series_key or ""),
            str(event.get("start") or ""),
            str(event.get("name") or ""),
            str(event.get("venue") or ""),
        )
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    date = str(event.get("start") or "")[:10] or "event"
    return f"{date}-{slugify(event.get('name') or 'race')[:54]}-{digest}"


def _series_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("series_key") or ""): item
        for item in (snapshot.get("series") or [])
        if item.get("series_key")
    }


def _event_summary_map(hub: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("series_key") or ""): item
        for item in (hub.get("catalog") or [])
        if item.get("series_key")
    }


def _driver_key(series_key: str, name: str) -> str:
    return f"{series_key}:{re.sub(r'[^a-z0-9]+', '', str(name or '').lower())}"


def _team_key(name: str) -> str:
    return slugify(name)


def _track_name(event: dict[str, Any]) -> str | None:
    venue = " ".join(str(event.get("venue") or "").split()).strip()
    if venue:
        return venue
    title = " ".join(str(event.get("name") or "").split()).strip()
    match = re.search(
        r"(?:at|@)\s+(.+?(?:Speedway|Raceway|Motorsports Park|Motor Speedway|Dirt Track|Circuit|Dragway|Park))\b",
        title,
        flags=re.IGNORECASE,
    )
    return " ".join(match.group(1).split()).strip() if match else None


def _safe_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _standings_history(limit_per_series: int = 4) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    try:
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(RacingStandingSnapshot)
                    .order_by(RacingStandingSnapshot.series_key, RacingStandingSnapshot.fetched_at.desc())
                ).all()
            )
    except Exception:
        return {}

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if counts[row.series_key] >= limit_per_series:
            continue
        try:
            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
        entries = payload.get("entries") or []
        result[row.series_key].append(
            {
                "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
                "source_name": row.source_name,
                "source_url": row.source_url,
                "leader": entries[0] if entries else None,
                "field": len(entries),
            }
        )
        counts[row.series_key] += 1
    return dict(result)


def build_world(*, account_id: int | None = None) -> dict[str, Any]:
    now = _utcnow()
    standings = get_standings_snapshot_hub()
    event_hub = get_racing_event_hub()
    series_by_key = _series_map(standings)
    event_by_key = _event_summary_map(event_hub)

    series: list[dict[str, Any]] = []
    drivers: list[dict[str, Any]] = []
    teams_by_key: dict[str, dict[str, Any]] = {}
    tracks_by_key: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []

    configured_keys = list(dict.fromkeys([
        *SERIES_EVENT_CONFIG.keys(),
        *series_by_key.keys(),
        *event_by_key.keys(),
    ]))

    for key in configured_keys:
        standing = series_by_key.get(key) or {}
        event_info = event_by_key.get(key) or {}
        config = SERIES_EVENT_CONFIG.get(key) or {}
        entries = standing.get("entries") or []
        current_event = event_info.get("event") or standing.get("current_event") or None
        item = {
            "key": key,
            "name": standing.get("series_name") or event_info.get("series_name") or config.get("name") or key,
            "short_name": standing.get("short_name") or config.get("name") or key,
            "group": standing.get("group") or event_info.get("group") or config.get("group") or "Racing",
            "season": standing.get("season") or standings.get("season"),
            "leader": entries[0] if entries else None,
            "field": len(entries),
            "standings_status": standing.get("status") or ("tracked" if entries else "schedule"),
            "standings_updated_at": standing.get("fetched_at"),
            "next_event": current_event,
            "event_state": event_info.get("state") or standing.get("event_state"),
            "schedule_url": event_info.get("schedule_url") or standing.get("schedule_url") or config.get("schedule_url"),
            "watch_name": event_info.get("watch_name") or standing.get("watch_name") or config.get("watch_name"),
            "watch_url": event_info.get("watch_url") or standing.get("watch_url") or config.get("watch_url"),
            "logo_url": standing.get("logo_url") or event_info.get("logo_url") or config.get("logo_url"),
        }
        series.append(item)

        for entry in entries:
            driver = {
                "key": _driver_key(key, entry.get("name") or ""),
                "series_key": key,
                "series_name": item["name"],
                "name": entry.get("name"),
                "number": entry.get("number"),
                "team": entry.get("team"),
                "manufacturer": entry.get("manufacturer"),
                "position": entry.get("position"),
                "points": entry.get("points"),
                "wins": entry.get("wins"),
                "photo_url": entry.get("photo_url"),
            }
            drivers.append(driver)
            team = " ".join(str(entry.get("team") or "").split()).strip()
            if team:
                team_key = _team_key(team)
                target = teams_by_key.setdefault(
                    team_key,
                    {
                        "key": team_key,
                        "name": team,
                        "drivers": [],
                        "series": [],
                        "manufacturers": [],
                    },
                )
                if key not in target["series"]:
                    target["series"].append(key)
                manufacturer = entry.get("manufacturer")
                if manufacturer and manufacturer not in target["manufacturers"]:
                    target["manufacturers"].append(manufacturer)
                target["drivers"].append(
                    {
                        "name": entry.get("name"),
                        "number": entry.get("number"),
                        "series_key": key,
                        "position": entry.get("position"),
                        "points": entry.get("points"),
                    }
                )

        if current_event:
            e = dict(current_event)
            e.update(
                {
                    "key": event_key(key, current_event),
                    "series_key": key,
                    "series_name": item["name"],
                    "group": item["group"],
                    "watch_name": item["watch_name"],
                    "watch_url": item["watch_url"],
                    "schedule_url": item["schedule_url"],
                    "state": item["event_state"],
                }
            )
            events.append(e)
            track = _track_name(e)
            if track:
                track_key = slugify(track)
                target = tracks_by_key.setdefault(
                    track_key,
                    {
                        "key": track_key,
                        "name": track,
                        "location": e.get("location"),
                        "series": [],
                        "events": [],
                    },
                )
                if key not in target["series"]:
                    target["series"].append(key)
                target["events"].append(
                    {
                        "key": e["key"],
                        "series_key": key,
                        "series_name": item["name"],
                        "name": e.get("name"),
                        "start": e.get("start"),
                        "state": e.get("state"),
                    }
                )

    teams = sorted(teams_by_key.values(), key=lambda x: x["name"].lower())
    tracks = sorted(tracks_by_key.values(), key=lambda x: x["name"].lower())
    series.sort(key=lambda x: (x["group"], x["name"]))
    drivers.sort(key=lambda x: (x["name"] or "", x["series_name"]))

    follows = race_center_accounts.list_follows(account_id) if account_id else []
    followed_series = {str(x.get("key")) for x in follows if x.get("kind") == "series"}
    followed_drivers = {str(x.get("key")) for x in follows if x.get("kind") == "driver"}
    followed_tracks = {str(x.get("key")) for x in follows if x.get("kind") == "track"}
    followed_teams = {str(x.get("key")) for x in follows if x.get("kind") == "team"}

    briefing_items: list[dict[str, Any]] = []
    for item in series:
        if item["key"] not in followed_series:
            continue
        event = item.get("next_event")
        if event:
            briefing_items.append(
                {
                    "kind": "event",
                    "priority": 90 if item.get("event_state") == "live" else 70,
                    "title": f"{item['name']}: {event.get('name') or 'Next race'}",
                    "meta": event.get("start"),
                    "href": f"/race-center/event/{item['key']}/{event_key(item['key'], event)}",
                }
            )
        if item.get("leader"):
            briefing_items.append(
                {
                    "kind": "standings",
                    "priority": 55,
                    "title": f"{item['name']} leader: {item['leader'].get('name')}",
                    "meta": f"{item['leader'].get('points')} pts" if item["leader"].get("points") is not None else "",
                    "href": f"/race-center/series/{item['key']}",
                }
            )

    for driver in drivers:
        if driver["key"] not in followed_drivers:
            continue
        briefing_items.append(
            {
                "kind": "driver",
                "priority": 60,
                "title": f"{driver['name']} · {driver['series_name']}",
                "meta": f"P{driver['position']} · {driver['points']} pts" if driver.get("position") else driver["series_name"],
                "href": f"/race-center/driver/{driver['series_key']}/{driver['name']}",
            }
        )

    briefing_items.sort(key=lambda x: -int(x.get("priority") or 0))

    complete_identity = sum(
        1 for d in drivers if d.get("number") and d.get("team") and d.get("manufacturer")
    )
    photo_count = sum(1 for d in drivers if d.get("photo_url"))
    fresh_series = sum(1 for s in series if s.get("standings_status") == "fresh")
    schedule_coverage = sum(1 for s in series if s.get("schedule_url"))
    source_coverage = sum(1 for s in series if s.get("schedule_url") or s.get("standings_status") not in {None, "schedule"})

    history = _standings_history()

    return {
        "generated_at": now.isoformat(),
        "counts": {
            "series": len(series),
            "drivers": len(drivers),
            "teams": len(teams),
            "tracks": len(tracks),
            "current_events": len(events),
        },
        "series": series,
        "drivers": drivers,
        "teams": teams,
        "tracks": tracks,
        "events": events,
        "history": history,
        "briefing": {
            "series_followed": len(followed_series),
            "drivers_followed": len(followed_drivers),
            "tracks_followed": len(followed_tracks),
            "teams_followed": len(followed_teams),
            "items": briefing_items[:24],
        },
        "health": {
            "series_total": len(series),
            "standings_fresh": fresh_series,
            "schedule_coverage": schedule_coverage,
            "source_coverage": source_coverage,
            "drivers_total": len(drivers),
            "complete_driver_identity": complete_identity,
            "driver_photo_coverage": photo_count,
            "event_series_live": len(event_hub.get("live") or []),
            "event_series_next": len(event_hub.get("next") or []),
            "status": "healthy" if source_coverage >= max(1, int(len(series) * 0.8)) else "degraded",
        },
        "capabilities": {
            "tracks": True,
            "teams": True,
            "event_hubs": True,
            "race_day": True,
            "results_archive": True,
            "universal_search": True,
            "claims": True,
            "verification": True,
            "editorial_slots": True,
            "pwa": True,
        },
    }


def get_event_detail(series_key: str, key: str) -> dict[str, Any] | None:
    events = get_series_event_schedule(series_key)
    for raw in events:
        if event_key(series_key, raw) != key:
            continue
        event = dict(raw)
        event["key"] = key
        event["track_name"] = _track_name(event)
        event["track_key"] = slugify(event["track_name"]) if event.get("track_name") else None
        return event
    return None


def get_track_detail(track_key: str, *, series_hint: str = "") -> dict[str, Any] | None:
    target = slugify(track_key)
    series_keys = [series_hint] if series_hint in SERIES_EVENT_CONFIG else list(SERIES_EVENT_CONFIG)
    matches: list[dict[str, Any]] = []
    canonical = ""
    location = None
    for series_key in series_keys:
        for event in get_series_event_schedule(series_key):
            name = _track_name(event)
            if not name or slugify(name) != target:
                continue
            canonical = canonical or name
            location = location or event.get("location")
            matches.append(
                {
                    **event,
                    "key": event_key(series_key, event),
                    "series_key": series_key,
                    "series_name": (SERIES_EVENT_CONFIG.get(series_key) or {}).get("name"),
                }
            )
        if series_hint and matches:
            break
    if not matches:
        return None
    matches.sort(key=lambda x: x.get("start") or "")
    return {
        "key": target,
        "name": canonical,
        "location": location,
        "events": matches,
        "series": sorted({x["series_key"] for x in matches}),
        "upcoming": [x for x in matches if not x.get("completed")][:8],
        "recent": [x for x in matches if x.get("completed")][-8:],
    }


def get_team_detail(team_key: str) -> dict[str, Any] | None:
    world = build_world()
    target = slugify(team_key)
    return next((item for item in world["teams"] if item["key"] == target), None)
