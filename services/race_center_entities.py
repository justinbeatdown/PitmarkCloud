from __future__ import annotations

from datetime import datetime, timezone
import json
import re
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
        "movement": entry.get("movement"),
        "points_change": entry.get("points_change"),
    }


def build_entity_graph() -> dict[str, Any]:
    standings = get_standings_snapshot_hub()
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
                "movement": entry.get("movement"),
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

        if event:
            ekey = _event_key(series_key, event)
            track_key = _track_key(event)
            event_row = {
                "key": ekey,
                "series_key": series_key,
                "series_name": series.get("series_name"),
                "group": series.get("group"),
                "name": event.get("name") or event.get("title") or series.get("series_name"),
                "start": event.get("start"),
                "state": event_info.get("state"),
                "venue": event.get("venue") or event.get("track"),
                "location": event.get("location"),
                "broadcast": event.get("broadcast") or event_info.get("watch_name"),
                "watch_url": event_info.get("watch_url"),
                "schedule_url": event_info.get("schedule_url"),
                "track_key": track_key or None,
            }
            event_items.append(event_row)
            if track_key:
                track = tracks.setdefault(track_key, {
                    "key": track_key,
                    "name": event_row["venue"],
                    "location": event_row["location"],
                    "series": set(),
                    "events": [],
                })
                track["series"].add(series_key)
                track["events"].append({
                    "key": ekey,
                    "name": event_row["name"],
                    "start": event_row["start"],
                    "state": event_row["state"],
                    "series_key": series_key,
                    "series_name": event_row["series_name"],
                })

    for team in teams.values():
        team["series"] = sorted(team["series"])
    for track in tracks.values():
        track["series"] = sorted(track["series"])
        track["events"].sort(key=lambda x: str(x.get("start") or ""))

    event_items.sort(key=lambda x: str(x.get("start") or ""))
    series_items.sort(key=lambda x: (str(x.get("group") or ""), str(x.get("name") or "")))

    return {
        "generated_at": utcnow().isoformat(),
        "season": standings.get("season"),
        "series": series_items,
        "drivers": sorted(drivers.values(), key=lambda x: x["name"]),
        "teams": sorted(teams.values(), key=lambda x: x["name"]),
        "tracks": sorted(tracks.values(), key=lambda x: x["name"]),
        "events": event_items,
        "health": data_health(standings=standings),
    }


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
            return result
    return None


def my_racing_brief(follows: list[dict[str, Any]]) -> dict[str, Any]:
    graph = build_entity_graph()
    by_series = {str(x["key"]): x for x in graph["series"]}
    by_driver = {str(x["key"]): x for x in graph["drivers"]}
    by_track = {str(x["key"]): x for x in graph["tracks"]}
    by_team = {str(x["key"]): x for x in graph["teams"]}
    followed_series = {str(x.get("key") or "") for x in follows if x.get("kind") == "series"}
    followed_driver = {identity_key(str(x.get("label") or x.get("key") or "")) for x in follows if x.get("kind") == "driver"}
    followed_track = {str(x.get("key") or "") for x in follows if x.get("kind") == "track"}
    followed_team = {str(x.get("key") or "") for x in follows if x.get("kind") == "team"}

    events = [
        item for item in graph["events"]
        if item.get("series_key") in followed_series or item.get("track_key") in followed_track
    ]
    events.sort(key=lambda x: str(x.get("start") or ""))

    drivers = [by_driver[key] for key in followed_driver if key in by_driver]
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
