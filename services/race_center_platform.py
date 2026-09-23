from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import re
import unicodedata
from typing import Any

from sqlalchemy import select

from services.database import SessionLocal
from services.racing_events import get_racing_event_hub
from services.racing_standings import (
    RacingStandingSnapshot,
    get_standings_snapshot_hub,
)
from services import race_center_accounts


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str, fallback: str = "entity") -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text or fallback)[:180]


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event_key(series_key: str, event: dict[str, Any]) -> str:
    source_id = str(event.get("source_id") or "").strip()
    if source_id:
        return f"{series_key}:{source_id}"
    start = str(event.get("start") or "")[:10]
    name = slugify(str(event.get("name") or "event"), "event")
    return f"{series_key}:{start}:{name}"


def _track_key(event: dict[str, Any]) -> str | None:
    venue = str(event.get("venue") or "").strip()
    location = str(event.get("location") or "").strip()
    if not venue:
        return None
    return slugify(f"{venue}-{location}" if location else venue, "track")


def _series_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(series.get("series_key") or ""): series
        for series in payload.get("series") or []
        if str(series.get("series_key") or "").strip()
    }


def build_event_catalog(
    standings_payload: dict[str, Any] | None = None,
    event_hub: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    standings_payload = standings_payload or get_standings_snapshot_hub()
    event_hub = event_hub or get_racing_event_hub()
    standings = _series_map(standings_payload)
    events: list[dict[str, Any]] = []

    for item in event_hub.get("catalog") or []:
        series_key = str(item.get("series_key") or "").strip()
        if not series_key:
            continue
        series = standings.get(series_key) or {}
        full_events = list(item.get("events") or [])
        if not full_events and item.get("event"):
            full_events = [item.get("event")]

        for event in full_events:
            if not isinstance(event, dict):
                continue
            start = _parse_dt(event.get("start"))
            venue = str(event.get("venue") or "").strip() or None
            location = str(event.get("location") or "").strip() or None
            track_key = _track_key(event)
            key = _event_key(series_key, event)
            events.append(
                {
                    "key": key,
                    "series_key": series_key,
                    "series_name": item.get("series_name") or series.get("series_name") or series_key,
                    "series_short_name": series.get("short_name") or item.get("series_name") or series_key,
                    "group": item.get("group") or series.get("group") or "Racing",
                    "name": event.get("name") or item.get("series_name") or "Race event",
                    "start": start.isoformat() if start else event.get("start"),
                    "date_only": bool(event.get("date_only")),
                    "state": event.get("state") or "pre",
                    "completed": bool(event.get("completed")),
                    "broadcast": event.get("broadcast") or item.get("watch_name"),
                    "venue": venue,
                    "location": location,
                    "track_key": track_key,
                    "source_url": event.get("source_url") or item.get("schedule_url"),
                    "schedule_url": item.get("schedule_url"),
                    "watch_name": item.get("watch_name"),
                    "watch_url": item.get("watch_url"),
                    "series_logo": f"/standings-logo/{series_key}",
                }
            )

    # Dedupe event keys while preserving the richer record.
    by_key: dict[str, dict[str, Any]] = {}
    for event in events:
        current = by_key.get(event["key"])
        if current is None or sum(bool(v) for v in event.values()) > sum(bool(v) for v in current.values()):
            by_key[event["key"]] = event

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        state_rank = 0 if item.get("state") == "in" else 1 if not item.get("completed") else 2
        return state_rank, str(item.get("start") or "9999")

    return sorted(by_key.values(), key=sort_key)


def build_track_catalog(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracks: dict[str, dict[str, Any]] = {}
    now = utcnow()
    for event in events:
        key = str(event.get("track_key") or "").strip()
        venue = str(event.get("venue") or "").strip()
        if not key or not venue:
            continue
        row = tracks.setdefault(
            key,
            {
                "key": key,
                "name": venue,
                "location": event.get("location"),
                "series_keys": set(),
                "series_names": set(),
                "events": [],
                "next_event": None,
                "last_event": None,
            },
        )
        row["series_keys"].add(str(event.get("series_key") or ""))
        row["series_names"].add(str(event.get("series_name") or ""))
        row["events"].append(event)
        start = _parse_dt(event.get("start"))
        if not start:
            continue
        if start >= now and (
            row["next_event"] is None
            or start < (_parse_dt(row["next_event"].get("start")) or datetime.max.replace(tzinfo=timezone.utc))
        ):
            row["next_event"] = event
        if start < now and (
            row["last_event"] is None
            or start > (_parse_dt(row["last_event"].get("start")) or datetime.min.replace(tzinfo=timezone.utc))
        ):
            row["last_event"] = event

    out: list[dict[str, Any]] = []
    for row in tracks.values():
        row["series_keys"] = sorted(key for key in row["series_keys"] if key)
        row["series_names"] = sorted(name for name in row["series_names"] if name)
        row["event_count"] = len(row["events"])
        row["upcoming_count"] = sum(
            1 for event in row["events"]
            if (_parse_dt(event.get("start")) or datetime.min.replace(tzinfo=timezone.utc)) >= now
        )
        row["events"] = sorted(row["events"], key=lambda e: str(e.get("start") or ""))
        out.append(row)
    return sorted(out, key=lambda row: (row["name"].casefold(), row.get("location") or ""))


def build_team_catalog(standings_payload: dict[str, Any]) -> list[dict[str, Any]]:
    teams: dict[str, dict[str, Any]] = {}
    for series in standings_payload.get("series") or []:
        series_key = str(series.get("series_key") or "")
        series_name = str(series.get("series_name") or series_key)
        for entry in series.get("entries") or []:
            team = str(entry.get("team") or "").strip()
            if not team:
                continue
            key = slugify(team, "team")
            row = teams.setdefault(
                key,
                {
                    "key": key,
                    "name": team,
                    "manufacturers": set(),
                    "series": {},
                    "drivers": {},
                },
            )
            manufacturer = str(entry.get("manufacturer") or "").strip()
            if manufacturer:
                row["manufacturers"].add(manufacturer)
            row["series"][series_key] = series_name
            driver_key = f"{series_key}:{slugify(str(entry.get('name') or 'driver'), 'driver')}"
            row["drivers"][driver_key] = {
                "key": driver_key,
                "name": entry.get("name"),
                "number": entry.get("number"),
                "manufacturer": entry.get("manufacturer"),
                "series_key": series_key,
                "series_name": series_name,
                "position": entry.get("position"),
                "points": entry.get("points"),
                "photo_url": entry.get("photo_url"),
            }

    out: list[dict[str, Any]] = []
    for row in teams.values():
        row["manufacturers"] = sorted(row["manufacturers"])
        row["series"] = [
            {"key": key, "name": name}
            for key, name in sorted(row["series"].items(), key=lambda x: x[1].casefold())
        ]
        row["drivers"] = sorted(
            row["drivers"].values(),
            key=lambda d: (str(d.get("series_name") or ""), int(d.get("position") or 9999), str(d.get("name") or "")),
        )
        row["driver_count"] = len(row["drivers"])
        row["series_count"] = len(row["series"])
        out.append(row)
    return sorted(out, key=lambda row: row["name"].casefold())


def build_results_archive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [dict(event) for event in events if event.get("completed") or event.get("state") == "post"]
    completed.sort(key=lambda event: str(event.get("start") or ""), reverse=True)
    for event in completed:
        # Do not manufacture finishing orders. Until a structured result feed is
        # attached, Race Center points to the event's source-backed result page.
        event["results_status"] = "source-backed"
        event["results_url"] = event.get("source_url") or event.get("schedule_url")
    return completed


def build_data_health(
    standings_payload: dict[str, Any],
    event_hub: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    series_rows = list(standings_payload.get("series") or [])
    fresh = sum(1 for row in series_rows if not row.get("stale") and row.get("status") != "unavailable")
    stale = sum(1 for row in series_rows if row.get("stale"))
    unavailable = sum(1 for row in series_rows if row.get("status") == "unavailable")
    total_drivers = 0
    complete_identity = 0
    for row in series_rows:
        for driver in row.get("entries") or []:
            total_drivers += 1
            if driver.get("number") and driver.get("team") and driver.get("manufacturer"):
                complete_identity += 1

    schedule_catalog = list(event_hub.get("catalog") or [])
    scheduled = sum(1 for row in schedule_catalog if row.get("schedule_url"))
    next_events = sum(1 for event in events if not event.get("completed") and event.get("start"))
    tracks = len({event.get("track_key") for event in events if event.get("track_key")})
    return {
        "generated_at": utcnow().isoformat(),
        "standings": {
            "total": len(series_rows),
            "fresh": fresh,
            "stale": stale,
            "unavailable": unavailable,
        },
        "identity": {
            "drivers": total_drivers,
            "complete": complete_identity,
            "coverage_pct": round((complete_identity / total_drivers) * 100, 1) if total_drivers else 0,
        },
        "schedules": {
            "series": len(schedule_catalog),
            "with_source": scheduled,
            "events_indexed": len(events),
            "upcoming_events": next_events,
            "tracks_indexed": tracks,
            "warming": bool(event_hub.get("warming")),
        },
    }


def build_race_day(events: list[dict[str, Any]], *, hours: int = 36) -> list[dict[str, Any]]:
    now = utcnow()
    cutoff = now + timedelta(hours=max(1, hours))
    chosen: list[dict[str, Any]] = []
    for event in events:
        start = _parse_dt(event.get("start"))
        if event.get("state") == "in":
            chosen.append({**event, "race_day_state": "live"})
            continue
        if not start or event.get("completed"):
            continue
        if now - timedelta(hours=2) <= start <= cutoff:
            chosen.append({**event, "race_day_state": "today" if start.date() == now.date() else "upcoming"})
    chosen.sort(key=lambda event: (0 if event.get("race_day_state") == "live" else 1, str(event.get("start") or "")))
    return chosen[:18]


def build_platform() -> dict[str, Any]:
    standings = get_standings_snapshot_hub()
    event_hub = get_racing_event_hub()
    events = build_event_catalog(standings, event_hub)
    tracks = build_track_catalog(events)
    teams = build_team_catalog(standings)
    return {
        "generated_at": utcnow().isoformat(),
        "season": standings.get("season"),
        "tracks": tracks,
        "teams": teams,
        "events": events,
        "race_day": build_race_day(events),
        "archive": build_results_archive(events),
        "health": build_data_health(standings, event_hub, events),
    }


def build_my_racing_brief(user_id: int | None) -> dict[str, Any]:
    platform = build_platform()
    standings = get_standings_snapshot_hub()
    follows = race_center_accounts.list_follows(user_id) if user_id else []
    followed: dict[str, set[str]] = defaultdict(set)
    for follow in follows:
        followed[str(follow.get("kind") or "")].add(str(follow.get("key") or ""))

    alerts: list[dict[str, Any]] = []
    now = utcnow()

    for event in platform["events"]:
        series_key = str(event.get("series_key") or "")
        event_key = str(event.get("key") or "")
        track_key = str(event.get("track_key") or "")
        relevant = (
            series_key in followed["series"]
            or event_key in followed["event"]
            or (track_key and track_key in followed["track"])
        )
        if not relevant:
            continue
        start = _parse_dt(event.get("start"))
        if event.get("state") == "in":
            alerts.append({
                "priority": 100,
                "kind": "live",
                "title": f"{event.get('series_short_name') or event.get('series_name')} is live",
                "detail": event.get("name"),
                "href": f"/race-center/event/{event_key.replace(':', '~')}",
            })
        elif start and now <= start <= now + timedelta(hours=72):
            hours = max(0, int((start - now).total_seconds() // 3600))
            alerts.append({
                "priority": 85 if hours <= 12 else 70,
                "kind": "next",
                "title": f"{event.get('name')} is coming up",
                "detail": f"{event.get('series_short_name') or event.get('series_name')} · in {hours}h",
                "href": f"/race-center/event/{event_key.replace(':', '~')}",
            })

    for series in standings.get("series") or []:
        series_key = str(series.get("series_key") or "")
        entries = list(series.get("entries") or [])
        if series_key in followed["series"] and entries:
            leader = entries[0]
            alerts.append({
                "priority": 55,
                "kind": "leader",
                "title": f"{series.get('short_name') or series.get('series_name')} leader",
                "detail": f"{leader.get('name')} · {leader.get('points') or '—'} pts",
                "href": f"/race-center/series/{series_key}",
            })
        for entry in entries:
            driver_key = f"{series_key}:{str(entry.get('name') or '').strip().lower()}"
            if driver_key not in followed["driver"]:
                continue
            movement = entry.get("movement") if entry.get("movement_verified") else None
            detail = f"P{entry.get('position') or '—'} · {entry.get('points') or '—'} pts"
            if movement:
                detail += f" · {'▲' if movement > 0 else '▼'}{abs(int(movement))}"
            alerts.append({
                "priority": 60 if movement else 45,
                "kind": "driver",
                "title": str(entry.get("name") or "Followed driver"),
                "detail": detail,
                "href": f"/race-center/driver/{series_key}/{str(entry.get('name') or '')}",
            })

    for team in platform["teams"]:
        if team["key"] not in followed["team"]:
            continue
        leaders = sorted(team["drivers"], key=lambda d: int(d.get("position") or 9999))[:3]
        alerts.append({
            "priority": 40,
            "kind": "team",
            "title": team["name"],
            "detail": " · ".join(f"{d.get('name')} P{d.get('position') or '—'}" for d in leaders),
            "href": f"/race-center/team/{team['key']}",
        })

    alerts.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("title") or "")))
    return {
        "generated_at": utcnow().isoformat(),
        "follows": follows,
        "alerts": alerts[:24],
        "race_day": platform["race_day"],
    }


def standings_history(series_key: str, *, limit: int = 12) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RacingStandingSnapshot)
            .where(RacingStandingSnapshot.series_key == series_key)
            .order_by(RacingStandingSnapshot.fetched_at.desc())
            .limit(max(1, min(limit, 50)))
        ).all())
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
        entries = list(payload.get("entries") or [])
        out.append({
            "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
            "leader": entries[0] if entries else None,
            "top": entries[:10],
            "field_size": len(entries),
        })
    return out
