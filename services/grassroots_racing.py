from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import copy
import re
import threading
import unicodedata
from typing import Any
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "PitmarkRaceCenterGrassroots/1.0 (+https://pitmarkracing.com)"
CACHE_SECONDS = 6 * 3600

SPRINTCAR_TRACKS_URL = "https://www.sprintcarratings.com/TrackList.aspx?OrderBy=Track&RaceType=0"
SPRINTCAR_DRIVER_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "key": "scr-wing-410",
        "name": "SprintCarRatings Wing 410",
        "discipline": "Wing 410 Sprint Cars",
        "url": "https://www.sprintcarratings.com/RatingsDriver.aspx?RaceType=1",
    },
    {
        "key": "scr-wingless-410",
        "name": "SprintCarRatings Wingless 410",
        "discipline": "Wingless 410 Sprint Cars",
        "url": "https://www.sprintcarratings.com/RatingsDriver.aspx?RaceType=2",
    },
    {
        "key": "scr-wing-360",
        "name": "SprintCarRatings Wing 360",
        "discipline": "Wing 360 Sprint Cars",
        "url": "https://www.sprintcarratings.com/RatingsDriver.aspx?RaceType=4",
    },
)

SOURCE_REGISTRY: tuple[dict[str, str], ...] = (
    {
        "key": "sprintcarratings",
        "name": "SprintCarRatings",
        "kind": "ratings-results-tracks",
        "status": "active",
        "url": "https://www.sprintcarratings.com/",
    },
    {
        "key": "dirtcar",
        "name": "DIRTcar Racing",
        "kind": "standings-tracks-drivers",
        "status": "active",
        "url": "https://dirtcar.com/points/",
    },
    {
        "key": "nascar-local",
        "name": "NASCAR Local Racing Series / MyRacePass",
        "kind": "grassroots-standings-drivers-tracks",
        "status": "discovery",
        "url": "https://www.nascar.com/local-racing-series/",
    },
    {
        "key": "myracepass",
        "name": "MyRacePass",
        "kind": "track-series-driver-points",
        "status": "discovery",
        "url": "https://www.myracepass.com/",
    },
    {
        "key": "race-monitor",
        "name": "Race Monitor",
        "kind": "live-timing-results",
        "status": "discovery",
        "url": "https://www.race-monitor.com/",
    },
    {
        "key": "mylaps-speedhive",
        "name": "MYLAPS Speedhive",
        "kind": "timing-results",
        "status": "discovery",
        "url": "https://speedhive.mylaps.com/",
    },
)

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def identity_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:180] or "unknown"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _number(value: Any) -> int | float | None:
    raw = _clean(value).replace(",", "").replace("$", "").replace("+", "")
    if not raw or raw in {"-", "—"}:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _reader_url(url: str) -> str:
    parts = urlsplit(url)
    query = f"?{parts.query}" if parts.query else ""
    return f"https://r.jina.ai/http://{parts.netloc}{parts.path or '/'}{query}"


def _html_tables(html: str) -> list[tuple[list[str], list[list[str]]]]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[list[str], list[list[str]]]] = []
    for table in soup.find_all("table"):
        headers: list[str] = []
        rows: list[list[str]] = []
        for row_index, tr in enumerate(table.find_all("tr")):
            cells = tr.find_all(["th", "td"])
            values = [_clean(cell.get_text(" ", strip=True)) for cell in cells]
            if not values:
                continue
            if tr.find_parent("thead") is not None or (
                not headers and row_index == 0 and all(getattr(cell, "name", "") == "th" for cell in cells)
            ):
                headers = values
                continue
            rows.append(values)
        if rows:
            out.append((headers, rows))
    return out


def _markdown_tables(markdown: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = [line.strip() for line in str(markdown or "").splitlines()]
    out: list[tuple[list[str], list[list[str]]]] = []

    def split_row(line: str) -> list[str]:
        return [_clean(re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cell)) for cell in line.strip().strip("|").split("|")]

    def is_separator(line: str) -> bool:
        if "|" not in line:
            return False
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or not is_separator(lines[index + 1]):
            index += 1
            continue
        header = split_row(lines[index])
        rows: list[list[str]] = []
        index += 2
        while index < len(lines) and "|" in lines[index]:
            row = split_row(lines[index])
            if any(row):
                rows.append(row)
            index += 1
        if header and rows:
            out.append((header, rows))
    return out


def _tables(url: str) -> list[tuple[list[str], list[list[str]]]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    direct_error: Exception | None = None
    try:
        with httpx.Client(timeout=18.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        parsed = _html_tables(response.text)
        if parsed:
            return parsed
    except Exception as exc:
        direct_error = exc

    try:
        with httpx.Client(
            timeout=24.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
        ) as client:
            response = client.get(_reader_url(url))
            response.raise_for_status()
        parsed = _markdown_tables(response.text)
        if parsed:
            return parsed
    except Exception as reader_error:
        raise RuntimeError(f"grassroots source unavailable ({direct_error}); rendered fallback failed ({reader_error})") from reader_error

    raise RuntimeError("grassroots source returned no usable tables")


def _header_index(headers: list[str], names: tuple[str, ...]) -> int | None:
    normalized = [re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip() for value in headers]
    wanted = {re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip() for value in names}
    for index, value in enumerate(normalized):
        if value in wanted:
            return index
    for index, value in enumerate(normalized):
        if any(token and token in value for token in wanted):
            return index
    return None


def _fetch_sprintcar_tracks() -> list[dict[str, Any]]:
    tables = _tables(SPRINTCAR_TRACKS_URL)
    chosen: tuple[list[str], list[list[str]]] | None = None
    for headers, rows in tables:
        joined = " ".join(headers).casefold()
        if "track" in joined and ("state" in joined or "location" in joined):
            chosen = (headers, rows)
            break
    if not chosen:
        raise RuntimeError("SprintCarRatings track table not found")

    headers, rows = chosen
    track_index = _header_index(headers, ("track",))
    state_index = _header_index(headers, ("state", "location"))
    if track_index is None:
        track_index = 0
    if state_index is None:
        state_index = 1 if len(headers) > 1 else None

    tracks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if track_index >= len(row):
            continue
        name = _clean(row[track_index])
        location = _clean(row[state_index]) if state_index is not None and state_index < len(row) else ""
        if not name or name.casefold() == "track":
            continue
        token = slugify(f"{name}-{location}")
        if token in seen:
            continue
        seen.add(token)
        tracks.append(
            {
                "key": token,
                "name": name,
                "location": location or None,
                "grassroots": True,
                "source_key": "sprintcarratings",
                "source_name": "SprintCarRatings track database",
                "source_url": SPRINTCAR_TRACKS_URL,
            }
        )
    return tracks


def _fetch_sprintcar_drivers(source: dict[str, Any]) -> list[dict[str, Any]]:
    url = str(source["url"])
    tables = _tables(url)
    chosen: tuple[list[str], list[list[str]]] | None = None
    for headers, rows in tables:
        joined = " ".join(headers).casefold()
        if "driver" in joined and "rating" in joined and len(rows) >= 3:
            chosen = (headers, rows)
            break
    if not chosen:
        raise RuntimeError(f"{source['name']} rating table not found")

    headers, rows = chosen
    name_index = _header_index(headers, ("driver",))
    rating_index = _header_index(headers, ("rating",))
    races_index = _header_index(headers, ("races", "race"))
    wins_index = _header_index(headers, ("wins", "win"))
    money_index = _header_index(headers, ("money", "2026 money"))
    if name_index is None or rating_index is None:
        raise RuntimeError(f"{source['name']} required columns missing")

    drivers: list[dict[str, Any]] = []
    for fallback_position, row in enumerate(rows, start=1):
        # SprintCarRatings tables render an unlabeled ranking column before Driver.
        offset = 1 if len(row) > len(headers) and row and re.fullmatch(r"\d+", _clean(row[0])) else 0

        def cell(index: int | None) -> str:
            actual = None if index is None else index + offset
            return _clean(row[actual]) if actual is not None and actual < len(row) else ""

        name = cell(name_index)
        rating = _number(cell(rating_index))
        if not name or rating is None:
            continue
        rank = fallback_position
        if offset and row:
            parsed_rank = _number(row[0])
            if isinstance(parsed_rank, int) and parsed_rank > 0:
                rank = parsed_rank
        drivers.append(
            {
                "key": identity_key(name),
                "name": name,
                "grassroots": True,
                "source_key": str(source["key"]),
                "source_name": str(source["name"]),
                "source_url": url,
                "discipline": str(source["discipline"]),
                "rank": rank,
                "rating": rating,
                "races": _number(cell(races_index)),
                "wins": _number(cell(wins_index)),
                "money": _number(cell(money_index)),
            }
        )
    return drivers


def _merge_drivers(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in groups:
        for raw in rows:
            key = str(raw.get("key") or "")
            if not key:
                continue
            row = merged.setdefault(
                key,
                {
                    "key": key,
                    "name": raw.get("name"),
                    "grassroots": True,
                    "grassroots_rankings": [],
                    "source_urls": [],
                },
            )
            ranking = {
                "source_key": raw.get("source_key"),
                "source_name": raw.get("source_name"),
                "source_url": raw.get("source_url"),
                "discipline": raw.get("discipline"),
                "rank": raw.get("rank"),
                "rating": raw.get("rating"),
                "races": raw.get("races"),
                "wins": raw.get("wins"),
                "money": raw.get("money"),
            }
            row["grassroots_rankings"].append(ranking)
            if raw.get("source_url") and raw["source_url"] not in row["source_urls"]:
                row["source_urls"].append(raw["source_url"])
    return sorted(merged.values(), key=lambda item: str(item.get("name") or ""))


def _empty_value(*, warming: bool) -> dict[str, Any]:
    return {
        "generated_at": utcnow().isoformat(),
        "warming": warming,
        "tracks": [],
        "drivers": [],
        "sources": [dict(item) for item in SOURCE_REGISTRY],
        "summary": {
            "tracks": 0,
            "drivers": 0,
            "active_sources": sum(1 for item in SOURCE_REGISTRY if item.get("status") == "active"),
            "discovery_sources": sum(1 for item in SOURCE_REGISTRY if item.get("status") == "discovery"),
            "errors": [],
        },
    }


def get_grassroots_catalog(force: bool = False) -> dict[str, Any]:
    now = utcnow()
    with _cache_lock:
        cached_at = _cache.get("at")
        cached = _cache.get("value")
        if (
            cached_at
            and cached
            and not force
            and (now - cached_at).total_seconds() < CACHE_SECONDS
        ):
            return copy.deepcopy(cached)
        if cached and not force:
            return copy.deepcopy(cached)
        if not force:
            return _empty_value(warming=True)

    tracks: list[dict[str, Any]] = []
    driver_groups: list[list[dict[str, Any]]] = []
    errors: list[dict[str, str]] = []

    jobs: list[tuple[str, Any]] = [("tracks", SPRINTCAR_TRACKS_URL)]
    jobs.extend((str(source["key"]), source) for source in SPRINTCAR_DRIVER_SOURCES)

    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {}
        for key, payload in jobs:
            if key == "tracks":
                future_map[pool.submit(_fetch_sprintcar_tracks)] = (key, payload)
            else:
                future_map[pool.submit(_fetch_sprintcar_drivers, payload)] = (key, payload)
        for future in as_completed(future_map):
            key, payload = future_map[future]
            try:
                result = future.result()
                if key == "tracks":
                    tracks = result
                else:
                    driver_groups.append(result)
            except Exception as exc:
                errors.append(
                    {
                        "source": key,
                        "url": str(payload if isinstance(payload, str) else payload.get("url") or ""),
                        "error": str(exc),
                    }
                )

    drivers = _merge_drivers(driver_groups)
    value = {
        "generated_at": now.isoformat(),
        "warming": False,
        "tracks": tracks,
        "drivers": drivers,
        "sources": [dict(item) for item in SOURCE_REGISTRY],
        "summary": {
            "tracks": len(tracks),
            "drivers": len(drivers),
            "active_sources": sum(1 for item in SOURCE_REGISTRY if item.get("status") == "active"),
            "discovery_sources": sum(1 for item in SOURCE_REGISTRY if item.get("status") == "discovery"),
            "errors": errors,
        },
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = copy.deepcopy(value)
    return value
