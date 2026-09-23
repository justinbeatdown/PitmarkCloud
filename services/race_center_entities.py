from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import re
import threading
import unicodedata
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.racing_events import get_racing_event_hub
from services.racing_standings import RacingStandingSnapshot, get_standings_snapshot_hub


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:180] or "unknown"


def identity_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower())


class RaceCenterEntityClaim(Base):
    __tablename__ = "race_center_entity_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_key", name="uq_race_center_entity_claim"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    entity_name: Mapped[str] = mapped_column(String(180), default="")
    evidence_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterEntityProfile(Base):
    __tablename__ = "race_center_entity_profiles"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_key", name="uq_race_center_entity_profile"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    bio: Mapped[str] = mapped_column(Text, default="")
    website_url: Mapped[str] = mapped_column(Text, default="")
    shop_url: Mapped[str] = mapped_column(Text, default="")
    contact_url: Mapped[str] = mapped_column(Text, default="")
    hero_url: Mapped[str] = mapped_column(Text, default="")
    sponsors_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterNotificationPreference(Base):
    __tablename__ = "race_center_notification_preferences"

    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    race_day: Mapped[bool] = mapped_column(Boolean, default=True)
    live_now: Mapped[bool] = mapped_column(Boolean, default=True)
    results_posted: Mapped[bool] = mapped_column(Boolean, default=True)
    standings_move: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_change: Mapped[bool] = mapped_column(Boolean, default=True)
    editorial: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterEditorialLink(Base):
    __tablename__ = "race_center_editorial_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    title: Mapped[str] = mapped_column(String(240))
    url: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_graph_lock = threading.Lock()
_graph_cache: dict[str, Any] = {"at": None, "value": None}


def _event_key(series_key: str, event: dict[str, Any]) -> str:
    date = str(event.get("start") or event.get("date") or "")[:10]
    name = str(event.get("name") or event.get("title") or "event")
    return slugify(f"{series_key}-{date}-{name}")


def _track_key(event: dict[str, Any]) -> str:
    venue = str(event.get("venue") or event.get("track") or "").strip()
    location = str(event.get("location") or "").strip()
    return slugify(f"{venue}-{location}") if venue else ""


def _entry_identity(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(entry.get("name") or "").strip(),
        "number": entry.get("number"),
        "team": entry.get("team"),
        "manufacturer": entry.get("manufacturer"),
        "photo_url": entry.get("photo_url"),
        "position": entry.get("position"),
        "points": entry.get("points"),
        "starts": entry.get("starts"),
        "wins": entry.get("wins"),
        "movement": entry.get("movement"),
        "points_change": entry.get("points_change"),
    }


def build_entity_graph(force: bool = False) -> dict[str, Any]:
    now = utcnow()
    with _graph_lock:
        cached_at = _graph_cache.get("at")
        cached_value = _graph_cache.get("value")
        ttl = 60 if (cached_value or {}).get("warming") else 300
        if (
            not force
            and cached_at
            and cached_value
            and (now - cached_at).total_seconds() < ttl
        ):
            return cached_value

    standings = get_standings_snapshot_hub()
    # Event sources are refreshed by the dedicated background sync loop. Public
    # graph requests never trigger dozens of remote schedule fetches themselves.
    events = get_racing_event_hub()
    event_series = events.get("series") or {}

    series_items: list[dict[str, Any]] = []
    drivers: dict[str, dict[str, Any]] = {}
    teams: dict[str, dict[str, Any]] = {}
    tracks: dict[str, dict[str, Any]] = {}
    event_items: list[dict[str, Any]] = []

    for series in standings.get("series") or []:
        series_key = str(series.get("series_key") or "")
        entries = list(series.get("entries") or [])
        event_info = event_series.get(series_key) or {}
        event = event_info.get("event") or None
        series_row = {
            "key": series_key,
            "name": series.get("series_name"),
            "short_name": series.get("short_name"),
            "group": series.get("group"),
            "season": series.get("season"),
            "status": series.get("status"),
            "stale": bool(series.get("stale")),
            "leader": _entry_identity(entries[0]) if entries else None,
            "field_size": len(entries),
            "official_url": series.get("official_url"),
            "schedule_url": event_info.get("schedule_url"),
            "watch_name": event_info.get("watch_name"),
            "watch_url": event_info.get("watch_url"),
            "logo_url": series.get("series_logo_url") or event_info.get("logo_url"),
            "event_state": event_info.get("state"),
            "event": event,
        }
        series_items.append(series_row)

        for entry in entries:
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            dkey = identity_key(name)
            row = drivers.setdefault(dkey, {
                "key": dkey,
                "name": name,
                "number": entry.get("number"),
                "team": entry.get("team"),
                "manufacturer": entry.get("manufacturer"),
                "photo_url": entry.get("photo_url"),
                "series": [],
            })
            for field in ("number", "team", "manufacturer", "photo_url"):
                if not row.get(field) and entry.get(field):
                    row[field] = entry.get(field)
            row["series"].append({
                "series_key": series_key,
                "series_name": series.get("series_name"),
                "position": entry.get("position"),
                "points": entry.get("points"),
                "starts": entry.get("starts"),
                "wins": entry.get("wins"),
                "top5s": entry.get("top5s") if entry.get("top5s") is not None else entry.get("top_5s"),
                "top10s": entry.get("top10s") if entry.get("top10s") is not None else entry.get("top_10s"),
                "movement": entry.get("movement"),
                "official_url": series.get("official_url"),
                "schedule_url": event_info.get("schedule_url"),
            })

            team_name = str(entry.get("team") or "").strip()
            if team_name:
                tkey = slugify(team_name)
                team = teams.setdefault(tkey, {
                    "key": tkey,
                    "name": team_name,
                    "manufacturer": entry.get("manufacturer"),
                    "drivers": [],
                    "series": set(),
                })
                if not team.get("manufacturer") and entry.get("manufacturer"):
                    team["manufacturer"] = entry.get("manufacturer")
                if not any(item.get("name") == name for item in team["drivers"]):
                    team["drivers"].append({
                        "name": name,
                        "driver_key": dkey,
                        "number": entry.get("number"),
                        "series_key": series_key,
                    })
                team["series"].add(series_key)

        event_rows = list(event_info.get("events") or [])
        if not event_rows and event:
            event_rows = [event]
        chosen_key = _event_key(series_key, event) if event else None
        for event_row_source in event_rows:
            if not isinstance(event_row_source, dict):
                continue
            ekey = _event_key(series_key, event_row_source)
            track_key = _track_key(event_row_source)
            raw_state = str(event_row_source.get("state") or "").lower()
            normalized_state = (
                "live" if raw_state in {"in", "live"}
                else "recent" if raw_state in {"post", "completed"}
                else "next" if ekey == chosen_key and event_info.get("state") == "next"
                else "schedule"
            )
            event_row = {
                "key": ekey,
                "event_id": event_row_source.get("event_id"),
                "series_key": series_key,
                "series_name": series.get("series_name"),
                "group": series.get("group"),
                "name": event_row_source.get("name") or event_row_source.get("title") or series.get("series_name"),
                "start": event_row_source.get("start"),
                "state": normalized_state,
                "venue": event_row_source.get("venue") or event_row_source.get("track"),
                "location": event_row_source.get("location"),
                "broadcast": event_row_source.get("broadcast") or event_info.get("watch_name"),
                "event_url": event_row_source.get("event_url"),
                "source_url": event_row_source.get("source_url"),
                "watch_url": event_info.get("watch_url"),
                "schedule_url": event_info.get("schedule_url"),
                "track_key": track_key or None,
                "classes": list(event_row_source.get("classes") or event_row_source.get("divisions") or []),
                "entry_list": list(event_row_source.get("entry_list") or event_row_source.get("entries") or []),
                "qualifying": list(event_row_source.get("qualifying") or []),
                "heats": list(event_row_source.get("heats") or []),
                "features": list(event_row_source.get("features") or event_row_source.get("feature") or []),
                "starting_lineup": list(event_row_source.get("starting_lineup") or event_row_source.get("lineup") or []),
                "results": list(event_row_source.get("results") or []),
                "related_drivers": [_entry_identity(entry) for entry in entries[:48]],
                "championship_context": {
                    "leader": _entry_identity(entries[0]) if entries else None,
                    "field_size": len(entries),
                    "season": series.get("season"),
                },
                "source_urls": sorted({
                    str(value)
                    for value in (
                        event_row_source.get("source_url"),
                        event_row_source.get("event_url"),
                        event_info.get("schedule_url"),
                        event_info.get("watch_url"),
                    )
                    if value
                }),
                "provenance": {
                    "generated_at": now.isoformat(),
                    "confidence": "source-backed" if (
                        event_row_source.get("source_url")
                        or event_row_source.get("event_url")
                        or event_info.get("schedule_url")
                    ) else "derived",
                },
            }
            event_items.append(event_row)
            if track_key:
                track = tracks.setdefault(track_key, {
                    "key": track_key,
                    "name": event_row["venue"],
                    "location": event_row["location"],
                    "track_type": event_row_source.get("track_type"),
                    "surface": event_row_source.get("surface"),
                    "length": event_row_source.get("length"),
                    "configuration": event_row_source.get("configuration"),
                    "official_url": event_row_source.get("track_url") or event_row_source.get("official_url"),
                    "social_links": list(event_row_source.get("social_links") or []),
                    "photo_url": event_row_source.get("photo_url"),
                    "photo_license": event_row_source.get("photo_license"),
                    "photo_attribution": event_row_source.get("photo_attribution"),
                    "series": set(),
                    "events": [],
                    "source_urls": set(),
                })
                if not track.get("location") and event_row.get("location"):
                    track["location"] = event_row.get("location")
                for field in ("track_type", "surface", "length", "configuration", "official_url", "photo_url", "photo_license", "photo_attribution"):
                    if not track.get(field) and event_row_source.get(field):
                        track[field] = event_row_source.get(field)
                for link in event_row_source.get("social_links") or []:
                    if link and link not in track["social_links"]:
                        track["social_links"].append(link)
                for source in (event_row.get("source_url"), event_row.get("schedule_url"), event_row_source.get("track_url"), event_row_source.get("official_url")):
                    if source:
                        track["source_urls"].add(str(source))
                track["series"].add(series_key)
                track["events"].append({
                    "key": ekey,
                    "name": event_row["name"],
                    "start": event_row["start"],
                    "state": event_row["state"],
                    "series_key": series_key,
                    "series_name": event_row["series_name"],
                })

    for driver in drivers.values():
        driver_series = {str(row.get("series_key") or "") for row in driver.get("series") or []}
        driver["stats"] = {
            "starts": sum(int(row.get("starts") or 0) for row in driver.get("series") or []),
            "wins": sum(int(row.get("wins") or 0) for row in driver.get("series") or []),
            "top5s": sum(int(row.get("top5s") or 0) for row in driver.get("series") or []),
            "top10s": sum(int(row.get("top10s") or 0) for row in driver.get("series") or []),
        }
        driver["upcoming_events"] = [
            {
                "key": event.get("key"),
                "name": event.get("name"),
                "start": event.get("start"),
                "state": event.get("state"),
                "series_key": event.get("series_key"),
                "series_name": event.get("series_name"),
                "venue": event.get("venue"),
                "location": event.get("location"),
                "track_key": event.get("track_key"),
            }
            for event in event_items
            if str(event.get("series_key") or "") in driver_series
            and event.get("state") in {"live", "next", "schedule"}
        ][:16]

        recent_results = []
        raced_tracks: dict[str, dict[str, Any]] = {}
        wanted = identity_key(str(driver.get("name") or ""))
        for event in reversed(event_items):
            matched = None
            for result in event.get("results") or []:
                if not isinstance(result, dict):
                    continue
                result_name = str(result.get("name") or result.get("driver") or "").strip()
                if result_name and identity_key(result_name) == wanted:
                    matched = result
                    break
            if not matched:
                continue
            recent_results.append({
                "event_key": event.get("key"),
                "event_name": event.get("name"),
                "series_key": event.get("series_key"),
                "series_name": event.get("series_name"),
                "start": event.get("start"),
                "track_key": event.get("track_key"),
                "venue": event.get("venue"),
                "position": matched.get("position"),
                "status": matched.get("status"),
            })
            if event.get("track_key"):
                raced_tracks[str(event["track_key"])] = {
                    "key": event.get("track_key"),
                    "name": event.get("venue"),
                    "location": event.get("location"),
                }
            if len(recent_results) >= 12:
                break
        driver["recent_results"] = recent_results
        driver["tracks_raced"] = sorted(raced_tracks.values(), key=lambda row: str(row.get("name") or ""))
        source_urls = sorted({
            str(value)
            for series_row in driver.get("series") or []
            for value in (series_row.get("official_url"), series_row.get("schedule_url"))
            if value
        })
        driver["source_urls"] = source_urls
        driver["provenance"] = {
            "generated_at": now.isoformat(),
            "confidence": "source-backed" if source_urls else "derived",
            "identity_key": driver.get("key"),
        }

    for team in teams.values():
        team["series"] = sorted(team["series"])
        team_series = set(team["series"])
        team["cars"] = sorted({
            str(driver.get("number"))
            for driver in team.get("drivers") or []
            if driver.get("number") not in (None, "")
        })
        manufacturers = sorted({
            str(driver.get("manufacturer") or "")
            for driver in drivers.values()
            if slugify(str(driver.get("team") or "")) == str(team.get("key") or "")
            and str(driver.get("manufacturer") or "").strip()
        })
        team["manufacturers"] = manufacturers
        if not team.get("manufacturer") and manufacturers:
            team["manufacturer"] = manufacturers[0]
        team["upcoming_events"] = [
            {
                "key": event.get("key"),
                "name": event.get("name"),
                "start": event.get("start"),
                "state": event.get("state"),
                "series_key": event.get("series_key"),
                "series_name": event.get("series_name"),
                "venue": event.get("venue"),
                "track_key": event.get("track_key"),
            }
            for event in event_items
            if str(event.get("series_key") or "") in team_series
            and event.get("state") in {"live", "next", "schedule"}
        ][:16]
        recent_results = []
        team_key = identity_key(str(team.get("name") or ""))
        for event in reversed(event_items):
            for result in event.get("results") or []:
                if not isinstance(result, dict):
                    continue
                result_team = str(result.get("team") or "").strip()
                if not result_team or identity_key(result_team) != team_key:
                    continue
                recent_results.append({
                    "event_key": event.get("key"),
                    "event_name": event.get("name"),
                    "series_key": event.get("series_key"),
                    "series_name": event.get("series_name"),
                    "start": event.get("start"),
                    "venue": event.get("venue"),
                    "driver": result.get("name") or result.get("driver"),
                    "number": result.get("number"),
                    "position": result.get("position"),
                })
                if len(recent_results) >= 16:
                    break
            if len(recent_results) >= 16:
                break
        team["recent_results"] = recent_results
        source_urls = sorted({
            str(value)
            for series_row in series_items
            if str(series_row.get("key") or "") in team_series
            for value in (series_row.get("official_url"), series_row.get("schedule_url"))
            if value
        })
        team["source_urls"] = source_urls
        team["provenance"] = {
            "generated_at": now.isoformat(),
            "confidence": "source-backed" if source_urls else "derived",
        }
    for track in tracks.values():
        track["series"] = sorted(track["series"])
        track["events"].sort(key=lambda x: str(x.get("start") or ""))
        track["source_urls"] = sorted(track.get("source_urls") or [])
        related = []
        seen_driver_keys: set[str] = set()
        track_series = set(track["series"])
        for driver in drivers.values():
            if not any(str(row.get("series_key") or "") in track_series for row in driver.get("series") or []):
                continue
            dkey = str(driver.get("key") or "")
            if not dkey or dkey in seen_driver_keys:
                continue
            seen_driver_keys.add(dkey)
            related.append({
                "key": dkey,
                "name": driver.get("name"),
                "number": driver.get("number"),
                "team": driver.get("team"),
                "photo_url": driver.get("photo_url"),
                "series": [
                    row for row in (driver.get("series") or [])
                    if str(row.get("series_key") or "") in track_series
                ],
            })
        track["related_drivers"] = sorted(related, key=lambda row: str(row.get("name") or ""))[:48]
        track["provenance"] = {
            "source_urls": track["source_urls"],
            "generated_at": now.isoformat(),
            "confidence": "source-backed" if track["source_urls"] else "derived",
        }

    event_items.sort(key=lambda x: str(x.get("start") or ""))
    series_items.sort(key=lambda x: (str(x.get("group") or ""), str(x.get("name") or "")))

    value = {
        "generated_at": utcnow().isoformat(),
        "season": standings.get("season"),
        "series": series_items,
        "drivers": sorted(drivers.values(), key=lambda x: x["name"]),
        "teams": sorted(teams.values(), key=lambda x: x["name"]),
        "tracks": sorted(tracks.values(), key=lambda x: x["name"]),
        "events": event_items,
        "health": data_health(standings=standings),
        "warming": bool(events.get("warming")),
    }
    with _graph_lock:
        _graph_cache["at"] = now
        _graph_cache["value"] = value
    return value


def data_health(*, standings: dict[str, Any] | None = None) -> dict[str, Any]:
    standings = standings or get_standings_snapshot_hub()
    series = list(standings.get("series") or [])
    driver_count = 0
    complete_identity = 0
    missing_identity = 0
    stale_series: list[dict[str, str]] = []
    unavailable_series: list[dict[str, str]] = []

    for item in series:
        if item.get("status") == "stale":
            stale_series.append({"key": str(item.get("series_key") or ""), "name": str(item.get("series_name") or "")})
        elif item.get("status") == "unavailable":
            unavailable_series.append({"key": str(item.get("series_key") or ""), "name": str(item.get("series_name") or "")})
        for entry in item.get("entries") or []:
            driver_count += 1
            if entry.get("number") and entry.get("team") and entry.get("manufacturer"):
                complete_identity += 1
            else:
                missing_identity += 1

    summary = standings.get("summary") or {}
    return {
        "series_total": len(series),
        "fresh_series": int(summary.get("live") or 0),
        "stale_series_count": len(stale_series),
        "unavailable_series_count": len(unavailable_series),
        "drivers_seen": driver_count,
        "complete_driver_identity": complete_identity,
        "incomplete_driver_identity": missing_identity,
        "stale_series": stale_series[:20],
        "unavailable_series": unavailable_series[:20],
        "last_snapshot_at": summary.get("last_snapshot_at"),
    }


def graph_search(query: str, limit: int = 24) -> list[dict[str, Any]]:
    q = str(query or "").strip().casefold()
    if not q:
        return []
    graph = build_entity_graph()
    results: list[tuple[int, dict[str, Any]]] = []

    def score(text: str) -> int:
        hay = text.casefold()
        if hay == q:
            return 120
        if hay.startswith(q):
            return 100
        if q in hay:
            return 70
        return 0

    for driver in graph["drivers"]:
        hay = " ".join(str(x or "") for x in (driver.get("name"), driver.get("number"), driver.get("team"), driver.get("manufacturer")))
        s = score(hay)
        if s:
            results.append((s + 10, {"type": "driver", **driver}))
    for series in graph["series"]:
        hay = " ".join(str(x or "") for x in (series.get("name"), series.get("short_name"), series.get("group")))
        s = score(hay)
        if s:
            results.append((s + 8, {"type": "series", **series}))
    for team in graph["teams"]:
        s = score(" ".join(str(x or "") for x in (team.get("name"), team.get("manufacturer"))))
        if s:
            results.append((s + 6, {"type": "team", **team}))
    for track in graph["tracks"]:
        s = score(" ".join(str(x or "") for x in (track.get("name"), track.get("location"))))
        if s:
            results.append((s + 5, {"type": "track", **track}))
    for event in graph["events"]:
        s = score(" ".join(str(x or "") for x in (event.get("name"), event.get("series_name"), event.get("venue"), event.get("location"))))
        if s:
            results.append((s + 4, {"type": "event", **event}))

    results.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    return [item for _, item in results[:max(1, min(limit, 60))]]


def entity_detail(entity_type: str, entity_key: str) -> dict[str, Any] | None:
    graph = build_entity_graph()
    key = str(entity_key or "").strip()
    collection = {
        "series": graph["series"],
        "driver": graph["drivers"],
        "team": graph["teams"],
        "track": graph["tracks"],
        "event": graph["events"],
    }.get(str(entity_type or "").strip().lower())
    if collection is None:
        return None
    for item in collection:
        if str(item.get("key") or "") == key:
            result = dict(item)
            result["type"] = entity_type
            result["editorial"] = editorial_for_entity(entity_type, key)
            result["owner_content"] = entity_owner_content(entity_type, key)
            result["verification"] = entity_verification(entity_type, key)
            return result
    return None


def my_racing_brief(follows: list[dict[str, Any]]) -> dict[str, Any]:
    graph = build_entity_graph()
    by_series = {str(x["key"]): x for x in graph["series"]}
    by_driver = {str(x["key"]): x for x in graph["drivers"]}
    by_track = {str(x["key"]): x for x in graph["tracks"]}
    by_team = {str(x["key"]): x for x in graph["teams"]}
    followed_series = {str(x.get("key") or "") for x in follows if x.get("kind") == "series"}
    followed_driver: set[str] = set()
    for item in follows:
        if item.get("kind") != "driver":
            continue
        label = str(item.get("label") or "").strip()
        raw_key = str(item.get("key") or "").strip()
        fallback_name = raw_key.split(":", 1)[1] if ":" in raw_key else raw_key
        key = identity_key(label or fallback_name)
        if key:
            followed_driver.add(key)
    followed_track = {str(x.get("key") or "") for x in follows if x.get("kind") == "track"}
    followed_team = {str(x.get("key") or "") for x in follows if x.get("kind") == "team"}

    drivers = [by_driver[key] for key in followed_driver if key in by_driver]
    driver_series = {
        str(series.get("series_key") or "")
        for driver in drivers
        for series in (driver.get("series") or [])
        if series.get("series_key")
    }
    team_series = {
        str(series_key)
        for key in followed_team
        if key in by_team
        for series_key in (by_team[key].get("series") or [])
    }
    relevant_series = followed_series | driver_series | team_series

    events = [
        item for item in graph["events"]
        if item.get("series_key") in relevant_series or item.get("track_key") in followed_track
    ]
    events.sort(key=lambda x: str(x.get("start") or ""))

    movers = []
    for driver in drivers:
        for series in driver.get("series") or []:
            move = series.get("movement")
            if move not in (None, 0, "0"):
                movers.append({
                    "driver": driver.get("name"),
                    "driver_key": driver.get("key"),
                    "series_key": series.get("series_key"),
                    "series_name": series.get("series_name"),
                    "movement": move,
                    "position": series.get("position"),
                })

    return {
        "generated_at": utcnow().isoformat(),
        "counts": {
            "series": len(followed_series),
            "drivers": len(followed_driver),
            "tracks": len(followed_track),
            "teams": len(followed_team),
        },
        "series": [by_series[key] for key in followed_series if key in by_series],
        "drivers": drivers,
        "tracks": [by_track[key] for key in followed_track if key in by_track],
        "teams": [by_team[key] for key in followed_team if key in by_team],
        "live": [x for x in events if x.get("state") == "live"],
        "upcoming": [x for x in events if x.get("state") in {"next", "schedule"}][:12],
        "movement": movers[:12],
    }


def race_day_brief(follows: list[dict[str, Any]]) -> dict[str, Any]:
    brief = my_racing_brief(follows)
    now = utcnow()
    followed_series = {str(x.get("key") or "") for x in follows if x.get("kind") == "series"}
    followed_tracks = {str(x.get("key") or "") for x in follows if x.get("kind") == "track"}

    def start_dt(item: dict[str, Any]) -> datetime | None:
        raw = str(item.get("start") or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

    def relevance(item: dict[str, Any]) -> tuple[int, str]:
        if str(item.get("track_key") or "") in followed_tracks:
            return 40, "FOLLOWED TRACK"
        if str(item.get("series_key") or "") in followed_series:
            return 30, "FOLLOWED SERIES"
        return 10, "YOUR RACING"

    candidates = [*(brief.get("live") or []), *(brief.get("upcoming") or [])]
    rows: list[dict[str, Any]] = []
    for item in candidates:
        when = start_dt(item)
        if item.get("state") != "live":
            if not when or when < now - timedelta(hours=2) or when > now + timedelta(hours=30):
                continue
        score, reason = relevance(item)
        enriched = dict(item)
        enriched["race_day_reason"] = reason
        enriched["race_day_score"] = score + (100 if item.get("state") == "live" else 0)
        rows.append(enriched)

    rows.sort(key=lambda item: (-int(item.get("race_day_score") or 0), str(item.get("start") or "")))
    return {
        "generated_at": brief.get("generated_at"),
        "live": [item for item in rows if item.get("state") == "live"][:6],
        "upcoming": [item for item in rows if item.get("state") != "live"][:8],
        "movement": brief.get("movement") or [],
        "counts": brief.get("counts") or {},
        "window_hours": 30,
    }


def notification_preferences(user_id: int) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.get(RaceCenterNotificationPreference, user_id)
        if row is None:
            row = RaceCenterNotificationPreference(user_id=user_id)
            db.add(row)
            db.commit()
            db.refresh(row)
        return {
            "race_day": bool(row.race_day),
            "live_now": bool(row.live_now),
            "results_posted": bool(row.results_posted),
            "standings_move": bool(row.standings_move),
            "schedule_change": bool(row.schedule_change),
            "editorial": bool(row.editorial),
        }


def update_notification_preferences(user_id: int, values: dict[str, Any]) -> dict[str, Any]:
    allowed = {"race_day", "live_now", "results_posted", "standings_move", "schedule_change", "editorial"}
    with SessionLocal() as db:
        row = db.get(RaceCenterNotificationPreference, user_id)
        if row is None:
            row = RaceCenterNotificationPreference(user_id=user_id)
            db.add(row)
        for key in allowed:
            if key in values:
                setattr(row, key, bool(values[key]))
        row.updated_at = utcnow()
        db.commit()
    return notification_preferences(user_id)


def submit_entity_claim(
    user_id: int,
    *,
    entity_type: str,
    entity_key: str,
    entity_name: str,
    evidence_url: str = "",
    note: str = "",
) -> dict[str, Any]:
    kind = str(entity_type or "").strip().lower()
    if kind not in {"driver", "team", "track", "series"}:
        raise ValueError("Claims are supported for drivers, teams, tracks, and series.")
    key = str(entity_key or "").strip()[:220]
    if not key:
        raise ValueError("Entity key is required.")
    with SessionLocal() as db:
        row = db.scalar(select(RaceCenterEntityClaim).where(
            RaceCenterEntityClaim.user_id == user_id,
            RaceCenterEntityClaim.entity_type == kind,
            RaceCenterEntityClaim.entity_key == key,
        ))
        if row is None:
            row = RaceCenterEntityClaim(user_id=user_id, entity_type=kind, entity_key=key)
            db.add(row)
        row.entity_name = str(entity_name or "")[:180]
        row.evidence_url = str(evidence_url or "")[:4000]
        row.note = str(note or "")[:4000]
        row.status = "pending"
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return {"id": row.id, "status": row.status, "entity_type": row.entity_type, "entity_key": row.entity_key}


def entity_claims_for_user(user_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterEntityClaim).where(
            RaceCenterEntityClaim.user_id == user_id
        ).order_by(RaceCenterEntityClaim.created_at.desc())).all())
    return [
        {
            "id": row.id,
            "entity_type": row.entity_type,
            "entity_key": row.entity_key,
            "entity_name": row.entity_name,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def editorial_for_entity(entity_type: str, entity_key: str, limit: int = 12) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterEditorialLink).where(
            RaceCenterEditorialLink.entity_type == str(entity_type or "").strip().lower(),
            RaceCenterEditorialLink.entity_key == str(entity_key or "").strip(),
        ).order_by(RaceCenterEditorialLink.published_at.desc()).limit(max(1, min(limit, 30)))).all())
    return [
        {
            "title": row.title,
            "url": row.url,
            "summary": row.summary,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }
        for row in rows
    ]


def series_archive(series_key: str, season: int | None = None, limit: int = 24) -> dict[str, Any]:
    season = int(season or utcnow().year)
    key = str(series_key or "").strip()
    if not key:
        return {"series_key": key, "season": season, "snapshots": []}
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RacingStandingSnapshot)
            .where(
                RacingStandingSnapshot.series_key == key,
                RacingStandingSnapshot.season == season,
            )
            .order_by(RacingStandingSnapshot.fetched_at.desc())
            .limit(max(1, min(limit, 80)))
        ).all())
    snapshots = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
        entries = list(payload.get("entries") or [])
        snapshots.append({
            "id": row.id,
            "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "field_size": len(entries),
            "leader": _entry_identity(entries[0]) if entries else None,
            "top_three": [_entry_identity(item) for item in entries[:3]],
        })
    return {
        "series_key": key,
        "season": season,
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
    }


def alerts_for_user(follows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    brief = my_racing_brief(follows)
    alerts: list[dict[str, Any]] = []
    for event in brief.get("live") or []:
        alerts.append({
            "type": "live_now",
            "priority": 100,
            "title": f"{event.get('series_name') or 'Racing'} is live",
            "body": event.get("name") or "Race Center live event",
            "url": f"/race-center/event/{event.get('key')}",
        })
    for event in brief.get("upcoming") or []:
        alerts.append({
            "type": "race_day",
            "priority": 80,
            "title": event.get("name") or "Upcoming race",
            "body": f"{event.get('series_name') or ''} · {eventWhenText(event.get('start'))}",
            "url": f"/race-center/event/{event.get('key')}",
        })
    for move in brief.get("movement") or []:
        alerts.append({
            "type": "standings_move",
            "priority": 60,
            "title": f"{move.get('driver')} moved in the standings",
            "body": f"{move.get('series_name') or ''} · P{move.get('position') or '—'}",
            "url": f"/race-center/driver/{move.get('series_key')}/{move.get('driver')}",
        })
    alerts.sort(key=lambda item: -int(item.get("priority") or 0))
    return alerts[:20]


def eventWhenText(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "time from official schedule"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%b %d · %H:%M UTC")
    except Exception:
        return raw


def entity_verification(entity_type: str, entity_key: str) -> dict[str, Any]:
    kind = str(entity_type or "").strip().lower()
    key = str(entity_key or "").strip()
    with SessionLocal() as db:
        approved = db.scalar(select(RaceCenterEntityClaim).where(
            RaceCenterEntityClaim.entity_type == kind,
            RaceCenterEntityClaim.entity_key == key,
            RaceCenterEntityClaim.status == "approved",
        ).order_by(RaceCenterEntityClaim.updated_at.desc()).limit(1))
    return {
        "claimed": bool(approved),
        "verified": bool(approved),
        "label": "Verified owner" if approved else "Unclaimed",
    }


def entity_owner_content(entity_type: str, entity_key: str) -> dict[str, Any] | None:
    kind = str(entity_type or "").strip().lower()
    key = str(entity_key or "").strip()
    with SessionLocal() as db:
        row = db.scalar(select(RaceCenterEntityProfile).where(
            RaceCenterEntityProfile.entity_type == kind,
            RaceCenterEntityProfile.entity_key == key,
        ))
        if row is None:
            return None
        try:
            sponsors = json.loads(row.sponsors_json or "[]")
        except Exception:
            sponsors = []
        return {
            "bio": row.bio,
            "website_url": row.website_url,
            "shop_url": row.shop_url,
            "contact_url": row.contact_url,
            "hero_url": row.hero_url,
            "sponsors": sponsors if isinstance(sponsors, list) else [],
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


def update_entity_owner_content(
    user_id: int,
    *,
    entity_type: str,
    entity_key: str,
    bio: str = "",
    website_url: str = "",
    shop_url: str = "",
    contact_url: str = "",
    hero_url: str = "",
    sponsors: list[str] | None = None,
) -> dict[str, Any]:
    kind = str(entity_type or "").strip().lower()
    key = str(entity_key or "").strip()
    with SessionLocal() as db:
        claim = db.scalar(select(RaceCenterEntityClaim).where(
            RaceCenterEntityClaim.user_id == user_id,
            RaceCenterEntityClaim.entity_type == kind,
            RaceCenterEntityClaim.entity_key == key,
            RaceCenterEntityClaim.status == "approved",
        ).limit(1))
        if claim is None:
            raise ValueError("A verified claim is required before editing this racing profile.")

        row = db.scalar(select(RaceCenterEntityProfile).where(
            RaceCenterEntityProfile.entity_type == kind,
            RaceCenterEntityProfile.entity_key == key,
        ))
        if row is None:
            row = RaceCenterEntityProfile(entity_type=kind, entity_key=key, owner_user_id=user_id)
            db.add(row)
        elif row.owner_user_id != user_id:
            raise ValueError("This racing profile is controlled by another verified owner.")

        row.bio = str(bio or "")[:5000]
        row.website_url = str(website_url or "")[:4000]
        row.shop_url = str(shop_url or "")[:4000]
        row.contact_url = str(contact_url or "")[:4000]
        row.hero_url = str(hero_url or "")[:4000]
        row.sponsors_json = json.dumps([str(x)[:180] for x in (sponsors or []) if str(x).strip()][:30])
        row.updated_at = utcnow()
        db.commit()
    return entity_owner_content(kind, key) or {}


def review_entity_claim(claim_id: int, *, status: str) -> dict[str, Any]:
    clean = str(status or "").strip().lower()
    if clean not in {"approved", "denied", "pending"}:
        raise ValueError("Claim status must be approved, denied, or pending.")
    with SessionLocal() as db:
        row = db.get(RaceCenterEntityClaim, int(claim_id))
        if row is None:
            raise ValueError("Claim not found.")
        row.status = clean
        row.updated_at = utcnow()
        db.commit()
        return {
            "id": row.id,
            "status": row.status,
            "entity_type": row.entity_type,
            "entity_key": row.entity_key,
            "user_id": row.user_id,
        }


def attach_editorial(
    *,
    entity_type: str,
    entity_key: str,
    title: str,
    url: str,
    summary: str = "",
    published_at: datetime | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = RaceCenterEditorialLink(
            entity_type=str(entity_type or "").strip().lower()[:24],
            entity_key=str(entity_key or "").strip()[:220],
            title=str(title or "").strip()[:240],
            url=str(url or "").strip()[:4000],
            summary=str(summary or "").strip()[:4000],
            published_at=published_at or utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id}
