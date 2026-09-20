from __future__ import annotations

import copy
import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal

log = logging.getLogger("pitmark.racing_standings")

USER_AGENT = "PitmarkRacingStandings/1.0 (+https://pitmarkracing.com)"
CACHE_SECONDS = 20 * 60

SERIES: tuple[dict[str, str], ...] = (
    {
        "key": "nascar-cup",
        "name": "NASCAR Cup Series",
        "short_name": "Cup",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-premier",
        "official_url": "https://www.nascar.com/standings/nascar-cup-series/",
    },
    {
        "key": "nascar-oreilly",
        "name": "NASCAR O'Reilly Auto Parts Series",
        "short_name": "O'Reilly",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-secondary",
        "official_url": "https://www.nascar.com/standings/nascar-oreilly-auto-parts-series/",
    },
    {
        "key": "nascar-truck",
        "name": "NASCAR CRAFTSMAN Truck Series",
        "short_name": "Trucks",
        "group": "NASCAR",
        "provider": "espn",
        "league": "nascar-truck",
        "official_url": "https://www.nascar.com/standings/nascar-craftsman-truck-series/",
    },
    {
        "key": "f1",
        "name": "Formula 1",
        "short_name": "F1",
        "group": "Open Wheel",
        "provider": "jolpica",
        "official_url": "https://www.formula1.com/en/results/current/drivers",
    },
    {
        "key": "indycar",
        "name": "NTT INDYCAR SERIES",
        "short_name": "INDYCAR",
        "group": "Open Wheel",
        "provider": "espn",
        "league": "irl",
        "official_url": "https://www.indycar.com/standings",
    },
    {
        "key": "imsa-weathertech",
        "name": "IMSA WeatherTech SportsCar Championship",
        "short_name": "IMSA",
        "group": "Sports Cars",
        "provider": "imsa",
        "official_url": "https://www.imsa.com/weathertech/standings/",
    },
    {
        "key": "wec",
        "name": "FIA World Endurance Championship",
        "short_name": "WEC",
        "group": "Sports Cars",
        "provider": "wec",
        "official_url": "https://www.fiawec.com/en/page/drivers-classification/34",
    },
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RacingStandingSnapshot(Base):
    __tablename__ = "racing_standing_snapshots"
    __table_args__ = (
        UniqueConstraint("series_key", "season", "fingerprint", name="uq_racing_standing_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_key: Mapped[str] = mapped_column(String(64), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    source_name: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip().replace(",", "").replace("+", "")
    if not raw or raw in {"—", "-", "null", "None"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _clean_points(value: Any) -> int | float | str | None:
    number = _num(value)
    if number is None:
        text = str(value or "").strip()
        return text or None
    return int(number) if number.is_integer() else number


def _fingerprint(entries: list[dict[str, Any]]) -> str:
    stable = [
        {
            "position": item.get("position"),
            "name": item.get("name"),
            "points": item.get("points"),
            "wins": item.get("wins"),
        }
        for item in entries
    ]
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stats_map(entry: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for stat in entry.get("stats") or []:
        if not isinstance(stat, dict):
            continue
        names = [
            stat.get("name"),
            stat.get("abbreviation"),
            stat.get("displayName"),
            stat.get("shortDisplayName"),
        ]
        value = stat.get("displayValue")
        if value in (None, ""):
            value = stat.get("value")
        for name in names:
            if name:
                result[str(name).strip().lower()] = value
    return result


def _entity_name(value: Any) -> tuple[str, str | None]:
    if not isinstance(value, dict):
        return "", None
    name = (
        value.get("displayName")
        or value.get("fullName")
        or value.get("name")
        or value.get("shortName")
        or ""
    )
    team = None
    if isinstance(value.get("team"), dict):
        team = value["team"].get("displayName") or value["team"].get("name")
    return str(name).strip(), str(team).strip() if team else None


def _find_espn_entries(payload: Any) -> list[dict[str, Any]]:
    candidates: list[list[dict[str, Any]]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            standings = node.get("standings")
            if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
                candidates.append([x for x in standings["entries"] if isinstance(x, dict)])
            entries = node.get("entries")
            if isinstance(entries, list) and entries and all(isinstance(x, dict) for x in entries):
                if any(("athlete" in x or "team" in x) and "stats" in x for x in entries):
                    candidates.append(entries)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    if not candidates:
        return []
    return max(candidates, key=len)


def _fetch_espn(config: dict[str, str], season: int) -> dict[str, Any]:
    league = config["league"]
    urls = (
        f"https://site.web.api.espn.com/apis/v2/sports/racing/{league}/standings?season={season}&seasontype=1&type=0&level=3",
        f"https://site.api.espn.com/apis/v2/sports/racing/{league}/standings?season={season}",
    )
    last_error = ""
    with httpx.Client(timeout=14.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for url in urls:
            try:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                raw_entries = _find_espn_entries(payload)
                if not raw_entries:
                    last_error = "structured standings were empty"
                    continue
                normalized: list[dict[str, Any]] = []
                for index, row in enumerate(raw_entries, start=1):
                    athlete = row.get("athlete") or row.get("team") or row.get("competitor") or {}
                    name, team = _entity_name(athlete)
                    if not name and isinstance(row.get("name"), str):
                        name = row["name"].strip()
                    if not name:
                        continue
                    stats = _stats_map(row)
                    position = (
                        row.get("position")
                        or stats.get("rank")
                        or stats.get("position")
                        or stats.get("pos")
                        or index
                    )
                    try:
                        position = int(float(str(position)))
                    except (TypeError, ValueError):
                        position = index
                    points = (
                        stats.get("points")
                        or stats.get("pts")
                        or stats.get("championship points")
                        or stats.get("championshippoints")
                    )
                    wins = stats.get("wins") or stats.get("w")
                    behind = stats.get("behind") or stats.get("gb") or stats.get("points behind")
                    starts = stats.get("starts") or stats.get("races")
                    normalized.append(
                        {
                            "position": position,
                            "name": name,
                            "team": team,
                            "manufacturer": stats.get("manufacturer") or stats.get("make"),
                            "points": _clean_points(points),
                            "behind": _clean_points(behind),
                            "wins": _clean_points(wins),
                            "starts": _clean_points(starts),
                        }
                    )
                if normalized:
                    normalized.sort(key=lambda x: x["position"])
                    return {
                        "entries": normalized,
                        "source_name": "ESPN structured racing feed",
                        "provider_url": url,
                    }
                last_error = "standings entries could not be normalized"
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
    raise RuntimeError(last_error or "ESPN standings unavailable")


def _fetch_f1(config: dict[str, str], season: int) -> dict[str, Any]:
    url = f"https://api.jolpi.ca/ergast/f1/{season}/driverstandings.json"
    with httpx.Client(timeout=14.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    lists = (
        payload.get("MRData", {})
        .get("StandingsTable", {})
        .get("StandingsLists", [])
    )
    if not lists:
        raise RuntimeError("F1 standings response was empty")
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(lists[0].get("DriverStandings") or [], start=1):
        driver = row.get("Driver") or {}
        constructors = row.get("Constructors") or []
        team = constructors[0].get("name") if constructors and isinstance(constructors[0], dict) else None
        name = " ".join(
            part for part in [driver.get("givenName"), driver.get("familyName")] if part
        ).strip() or driver.get("code") or f"Driver {index}"
        normalized.append(
            {
                "position": int(row.get("position") or index),
                "name": name,
                "team": team,
                "manufacturer": team,
                "points": _clean_points(row.get("points")),
                "behind": None,
                "wins": _clean_points(row.get("wins")),
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("F1 standings had no drivers")
    return {"entries": normalized, "source_name": "Jolpica F1", "provider_url": url}


def _html_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    with httpx.Client(timeout=16.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tables: list[tuple[list[str], list[list[str]]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header: list[str] = []
        body: list[list[str]] = []
        for row_index, row in enumerate(rows):
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in row.find_all(["th", "td"])
            ]
            if not cells:
                continue
            if row_index == 0 or row.find("th"):
                if len(cells) >= len(header):
                    header = cells
                continue
            body.append(cells)
        if body:
            tables.append((header, body))
    return tables


def _fetch_imsa(config: dict[str, str], season: int) -> dict[str, Any]:
    tables = _html_table_rows(config["official_url"])
    chosen: tuple[list[str], list[list[str]]] | None = None
    for header, rows in tables:
        joined = " ".join(header).lower()
        if "driver" in joined and ("total" in joined or "points" in joined):
            chosen = (header, rows)
            break
    if not chosen:
        raise RuntimeError("IMSA standings table was not present in the page HTML")
    header, rows = chosen
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 3:
            continue
        try:
            position = int(str(row[0]).split()[0])
        except (ValueError, TypeError):
            continue
        name = row[1].strip()
        if not name:
            continue
        points = _clean_points(row[-1])
        normalized.append(
            {
                "position": position,
                "name": name,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("IMSA standings rows could not be parsed")
    return {
        "entries": normalized,
        "source_name": "IMSA official standings",
        "provider_url": config["official_url"],
    }


def _fetch_wec(config: dict[str, str], season: int) -> dict[str, Any]:
    tables = _html_table_rows(config["official_url"])
    chosen: tuple[list[str], list[list[str]]] | None = None
    for header, rows in tables:
        joined = " ".join(header).lower()
        if "driver" in joined and "total" in joined:
            chosen = (header, rows)
            break
    if not chosen:
        raise RuntimeError("WEC drivers standings table was not present in the page HTML")
    header, rows = chosen
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 4:
            continue
        try:
            position = int(str(row[0]).split()[0])
        except (ValueError, TypeError):
            continue
        name = row[3].strip() if len(row) >= 5 else row[1].strip()
        manufacturer = row[1].strip() if len(row) >= 5 else None
        number = row[2].strip() if len(row) >= 5 else None
        if not name:
            continue
        normalized.append(
            {
                "position": position,
                "name": name,
                "team": number,
                "manufacturer": manufacturer,
                "points": _clean_points(row[-1]),
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("WEC standings rows could not be parsed")
    return {
        "entries": normalized,
        "source_name": "FIA WEC official standings",
        "provider_url": config["official_url"],
    }


def _fetch_series(config: dict[str, str], season: int) -> dict[str, Any]:
    provider = config["provider"]
    if provider == "espn":
        return _fetch_espn(config, season)
    if provider == "jolpica":
        return _fetch_f1(config, season)
    if provider == "imsa":
        return _fetch_imsa(config, season)
    if provider == "wec":
        return _fetch_wec(config, season)
    raise RuntimeError(f"Unknown standings provider: {provider}")


def _decode_snapshot(row: RacingStandingSnapshot | None) -> dict[str, Any] | None:
    if not row:
        return None
    try:
        payload = json.loads(row.payload_json or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["snapshot_id"] = row.id
    payload["fetched_at"] = row.fetched_at.isoformat() if row.fetched_at else None
    return payload


def _latest_snapshot(series_key: str, season: int, *, excluding: str | None = None) -> RacingStandingSnapshot | None:
    with SessionLocal() as db:
        stmt = (
            select(RacingStandingSnapshot)
            .where(
                RacingStandingSnapshot.series_key == series_key,
                RacingStandingSnapshot.season == season,
            )
            .order_by(RacingStandingSnapshot.fetched_at.desc(), RacingStandingSnapshot.id.desc())
        )
        if excluding:
            stmt = stmt.where(RacingStandingSnapshot.fingerprint != excluding)
        return db.scalar(stmt.limit(1))


def _movement(entries: list[dict[str, Any]], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    old_positions = {
        str(item.get("name") or "").strip().lower(): int(item.get("position"))
        for item in (previous or {}).get("entries", [])
        if item.get("name") and item.get("position") is not None
    }
    out: list[dict[str, Any]] = []
    for item in entries:
        current = dict(item)
        key = str(current.get("name") or "").strip().lower()
        prior = old_positions.get(key)
        try:
            now_pos = int(current.get("position"))
        except (TypeError, ValueError):
            now_pos = None
        current["movement"] = (prior - now_pos) if prior is not None and now_pos is not None else None
        out.append(current)
    return out


def _persist(config: dict[str, str], season: int, fetched: dict[str, Any]) -> dict[str, Any]:
    entries = fetched["entries"]
    fingerprint = _fingerprint(entries)
    previous_row = _latest_snapshot(config["key"], season, excluding=fingerprint)
    previous = _decode_snapshot(previous_row)
    normalized = {
        "series_key": config["key"],
        "series_name": config["name"],
        "short_name": config["short_name"],
        "group": config["group"],
        "season": season,
        "official_url": config["official_url"],
        "source_name": fetched.get("source_name") or "Standings source",
        "provider_url": fetched.get("provider_url"),
        "entries": entries,
        "fingerprint": fingerprint,
    }
    with SessionLocal() as db:
        existing = db.scalar(
            select(RacingStandingSnapshot).where(
                RacingStandingSnapshot.series_key == config["key"],
                RacingStandingSnapshot.season == season,
                RacingStandingSnapshot.fingerprint == fingerprint,
            )
        )
        if not existing:
            row = RacingStandingSnapshot(
                series_key=config["key"],
                season=season,
                source_name=normalized["source_name"],
                source_url=config["official_url"],
                fingerprint=fingerprint,
                payload_json=json.dumps(normalized, ensure_ascii=False, default=str),
                fetched_at=utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            fetched_at = row.fetched_at
            snapshot_id = row.id
        else:
            fetched_at = existing.fetched_at
            snapshot_id = existing.id
    normalized["entries"] = _movement(entries, previous)
    normalized["fetched_at"] = fetched_at.isoformat() if fetched_at else utcnow().isoformat()
    normalized["snapshot_id"] = snapshot_id
    normalized["status"] = "live"
    normalized["stale"] = False
    normalized["error"] = None
    return normalized


def _fallback(config: dict[str, str], season: int, error: Exception) -> dict[str, Any]:
    latest = _latest_snapshot(config["key"], season)
    cached = _decode_snapshot(latest)
    if cached:
        cached.update(
            {
                "series_key": config["key"],
                "series_name": config["name"],
                "short_name": config["short_name"],
                "group": config["group"],
                "official_url": config["official_url"],
                "season": season,
                "status": "stale",
                "stale": True,
                "error": str(error),
            }
        )
        cached["entries"] = [dict(item, movement=None) for item in cached.get("entries") or []]
        return cached
    return {
        "series_key": config["key"],
        "series_name": config["name"],
        "short_name": config["short_name"],
        "group": config["group"],
        "official_url": config["official_url"],
        "season": season,
        "source_name": None,
        "provider_url": None,
        "entries": [],
        "fetched_at": None,
        "snapshot_id": None,
        "status": "unavailable",
        "stale": True,
        "error": str(error),
    }


def _load_one(config: dict[str, str], season: int) -> dict[str, Any]:
    try:
        fetched = _fetch_series(config, season)
        return _persist(config, season, fetched)
    except Exception as exc:
        log.warning("Standings fetch failed series=%s error=%s", config["key"], exc)
        return _fallback(config, season, exc)


def get_standings_hub(*, force: bool = False, season: int | None = None) -> dict[str, Any]:
    season = int(season or utcnow().year)
    now = utcnow()
    with _cache_lock:
        cached_at = _cache.get("at")
        cached_value = _cache.get("value")
        if (
            not force
            and cached_at
            and cached_value
            and cached_value.get("season") == season
            and (now - cached_at).total_seconds() < CACHE_SECONDS
        ):
            return copy.deepcopy(cached_value)

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(6, len(SERIES))) as pool:
        future_map = {pool.submit(_load_one, config, season): config for config in SERIES}
        for future in as_completed(future_map):
            config = future_map[future]
            try:
                results[config["key"]] = future.result()
            except Exception as exc:
                results[config["key"]] = _fallback(config, season, exc)

    ordered = [results[config["key"]] for config in SERIES]
    live = sum(1 for item in ordered if item.get("status") == "live")
    stale = sum(1 for item in ordered if item.get("status") == "stale")
    unavailable = sum(1 for item in ordered if item.get("status") == "unavailable")
    synced_times = [item.get("fetched_at") for item in ordered if item.get("fetched_at")]
    value = {
        "season": season,
        "generated_at": now.isoformat(),
        "series": ordered,
        "summary": {
            "series_total": len(ordered),
            "live": live,
            "stale": stale,
            "unavailable": unavailable,
            "last_snapshot_at": max(synced_times) if synced_times else None,
        },
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = copy.deepcopy(value)
    return value


def clear_standings_cache() -> None:
    with _cache_lock:
        _cache["at"] = None
        _cache["value"] = None
