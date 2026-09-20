from __future__ import annotations

import copy
import io
import hashlib
import json
import logging
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal

log = logging.getLogger("pitmark.racing_standings")

USER_AGENT = "PitmarkRacingStandings/1.0 (+https://pitmarkracing.com)"
CACHE_SECONDS = 20 * 60

SERIES: tuple[dict[str, Any], ...] = (
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
        "key": "world-of-outlaws-sprint",
        "name": "World of Outlaws Sprint Car Series",
        "short_name": "WoO Sprint",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://worldofoutlaws.com/series-points/",
        "source_name": "World of Outlaws official points",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "world-of-outlaws-late-models",
        "name": "World of Outlaws Late Model Series",
        "short_name": "WoO Late Models",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://worldofoutlaws.com/latemodels/series-points/",
        "source_name": "World of Outlaws official points",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "lucas-oil-late-models",
        "name": "Lucas Oil Late Model Dirt Series",
        "short_name": "Lucas Oil LM",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://www.lucasdirt.com/standings/",
        "source_name": "Lucas Oil Late Model Dirt Series official standings",
        "name_headers": ("driver", "competitor"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts", "races"),
    },
    {
        "key": "high-limit-sprint",
        "name": "High Limit Racing",
        "short_name": "High Limit",
        "group": "Dirt",
        "provider": "official_table",
        "official_url": "https://www.highlimitracing.com/standings",
        "source_name": "High Limit Racing official standings",
        "name_headers": ("driver", "competitor"),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts", "races", "features"),
        "fallback_urls": ("https://www.tonystewartracing.com/schedule/",),
    },
    {
        "key": "usac-national-sprint",
        "name": "USAC AMSOIL National Sprint",
        "short_name": "USAC Sprint",
        "group": "Dirt",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/national-sprint",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "usac-national-midget",
        "name": "USAC NOS Energy Drink National Midget",
        "short_name": "USAC Midget",
        "group": "Dirt",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/national-midget",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "usac-silver-crown",
        "name": "USAC Silver Crown",
        "short_name": "Silver Crown",
        "group": "Dirt / Pavement",
        "provider": "column_sections",
        "column_title": "Driver Standings",
        "official_url": "https://www.usacracing.com/series-point-standings/silver-crown",
        "source_name": "USAC official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("pos", "position"),
        "wins_headers": ("wins",),
        "starts_headers": ("starts",),
    },
    {
        "key": "arca-menards",
        "name": "ARCA Menards Series",
        "short_name": "ARCA",
        "group": "Stock Cars",
        "provider": "official_table",
        "official_url": "https://www.arcaracing.com/standings/arca-menards-series/",
        "source_name": "ARCA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank", "column 1"),
        "behind_headers": ("diff", "behind"),
        "wins_headers": ("wins", "win"),
        "starts_headers": ("races", "starts"),
        "fallback_urls": ("https://theconwaybulletin.com/league/arca/standings/",),
    },
    {
        "key": "cars-tour-lmsc",
        "name": "zMAX CARS Tour — Late Model Stock",
        "short_name": "CARS LMSC",
        "group": "Short Track",
        "provider": "official_table",
        "official_url": "https://www.carsracingtour.com/standings",
        "source_name": "CARS Tour official standings",
        "name_headers": ("driver",),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position", "rank"),
        "behind_headers": ("gap", "behind"),
        "wins_headers": ("wins",),
    },
    {
        "key": "asa-stars",
        "name": "ASA STARS National Tour",
        "short_name": "ASA STARS",
        "group": "Short Track",
        "provider": "linked_pdf",
        "official_url": "https://starsnationaltour.com/stats/standings/",
        "source_name": "ASA STARS official standings",
        "pdf_link_text": "Driver Standings",
        "pdf_format": "asa_stars",
    },
    {
        "key": "smart-modified",
        "name": "SMART Modified Tour",
        "short_name": "SMART Mods",
        "group": "Short Track",
        "provider": "linked_pdf",
        "official_url": "https://smartmodifiedtour.com/standings",
        "source_name": "SMART Modified Tour official standings",
        "pdf_link_text": "Click to Download PDF",
        "pdf_format": "smart_modified",
    },
    {
        "key": "nhra-top-fuel",
        "name": "NHRA Top Fuel",
        "short_name": "NHRA Top Fuel",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=top-fuel",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
        "team_headers": ("vehicle",),
    },
    {
        "key": "nhra-funny-car",
        "name": "NHRA Funny Car",
        "short_name": "NHRA Funny Car",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=funny-car",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
        "team_headers": ("vehicle",),
    },
    {
        "key": "nhra-pro-stock",
        "name": "NHRA Pro Stock",
        "short_name": "NHRA Pro Stock",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=pro-stock",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
        "team_headers": ("vehicle",),
    },
    {
        "key": "nhra-pro-stock-motorcycle",
        "name": "NHRA Pro Stock Motorcycle",
        "short_name": "NHRA PSM",
        "group": "Drag Racing",
        "provider": "official_table",
        "official_url_template": "https://www.nhra.com/standings/{season}/nhra-mission-foods-drag-racing-series/nhra-mission-foods-drag-racing-series?tab=pro-stock-motorcycle",
        "source_name": "NHRA official standings",
        "name_headers": ("driver",),
        "points_headers": ("points",),
        "position_headers": ("position", "pos"),
        "behind_headers": ("points behind leader", "behind"),
        "team_headers": ("vehicle",),
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
        "key": "formula-e",
        "name": "ABB FIA Formula E World Championship",
        "short_name": "Formula E",
        "group": "Open Wheel",
        "provider": "official_table",
        "official_url_template": "https://www.fiaformulae.com/en/results-and-standings?season={fe_season}&tab=drivers",
        "source_name": "Formula E official standings",
        "name_headers": ("driver",),
        "points_headers": ("pts", "points"),
        "position_headers": ("pos", "position"),
        "team_headers": ("team",),
    },
    {
        "key": "imsa-weathertech",
        "name": "IMSA WeatherTech — GTP Drivers",
        "short_name": "IMSA GTP",
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
    {
        "key": "supercars",
        "name": "Repco Supercars Championship",
        "short_name": "Supercars",
        "group": "Touring Cars",
        "provider": "official_table",
        "official_url_template": "https://www.supercars.com/standings/{season}/supercars",
        "source_name": "Supercars official standings",
        "name_headers": ("driver",),
        "points_headers": ("pts", "points"),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "wins_headers": ("wins",),
    },
    {
        "key": "motogp",
        "name": "MotoGP World Championship",
        "short_name": "MotoGP",
        "group": "Motorcycles",
        "provider": "official_table",
        "official_url": "https://stats.motogp.com/en/world-standing",
        "source_name": "MotoGP official statistics",
        "name_headers": ("rider",),
        "points_headers": ("points", "pts"),
        "position_headers": ("pos", "position"),
        "behind_headers": ("gap",),
        "team_headers": ("team",),
        "manufacturer_headers": ("bike",),
        "fallback_url_templates": (
            "https://www.motogp.com/en/world-standing/{season}/motogp/team-standings",
        ),
    },
)
 
OFFICIAL_LOGO_TERMS: dict[str, tuple[str, ...]] = {
    "nascar-cup": ("nascar cup", "cup series"),
    "nascar-oreilly": ("o'reilly auto parts", "oreilly auto parts"),
    "nascar-truck": ("craftsman truck", "truck series"),
    "world-of-outlaws-sprint": ("world of outlaws", "outlaws sprint"),
    "world-of-outlaws-late-models": ("world of outlaws", "outlaws late model"),
    "lucas-oil-late-models": ("lucas oil late model", "late model dirt series"),
    "high-limit-sprint": ("high limit racing", "high limit"),
    "usac-national-sprint": ("usac",),
    "usac-national-midget": ("usac",),
    "usac-silver-crown": ("usac", "silver crown"),
    "arca-menards": ("arca menards", "arca"),
    "cars-tour-lmsc": ("cars tour", "zmax cars"),
    "asa-stars": ("asa stars", "stars national tour"),
    "smart-modified": ("smart modified", "smart tour"),
    "nhra-top-fuel": ("nhra",),
    "nhra-funny-car": ("nhra",),
    "nhra-pro-stock": ("nhra",),
    "nhra-pro-stock-motorcycle": ("nhra",),
    "f1": ("formula 1", "f1"),
    "indycar": ("indycar",),
    "formula-e": ("formula e",),
    "imsa-weathertech": ("imsa", "weathertech"),
    "wec": ("fia wec", "world endurance championship"),
    "supercars": ("supercars",),
    "motogp": ("motogp",),
}

NUMBER_HEADERS = (
    "#", "no", "no.", "number", "car", "car #", "car no", "car no.",
    "vehicle no", "vehicle #", "bike #", "rider #",
)
TEAM_HEADERS = ("team", "entrant", "organization")
MANUFACTURER_HEADERS = ("manufacturer", "make", "marque", "bike", "constructor")


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
                            "number": None,
                            "team": None,
                            "manufacturer": None,
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
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": _clean_points(row.get("points")),
                "behind": None,
                "wins": _clean_points(row.get("wins")),
                "starts": None,
            }
        )
    if not normalized:
        raise RuntimeError("F1 standings had no drivers")
    return {"entries": normalized, "source_name": "Jolpica F1", "provider_url": url}


def _parse_html_tables(html: str) -> list[tuple[list[str], list[list[str]]]]:
    soup = BeautifulSoup(html, "html.parser")
    tables: list[tuple[list[str], list[list[str]]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header: list[str] = []
        body: list[list[str]] = []
        for row_index, row in enumerate(rows):
            cell_nodes = row.find_all(["th", "td"], recursive=False)
            if not cell_nodes:
                cell_nodes = row.find_all(["th", "td"])
            cells = [
                " ".join(cell.get_text(" ", strip=True).split())
                for cell in cell_nodes
            ]
            if not cells:
                continue
            in_thead = row.find_parent("thead") is not None
            all_header_cells = bool(cell_nodes) and all(getattr(cell, "name", "") == "th" for cell in cell_nodes)
            # Accessible standings tables often use <th scope="row"> in EVERY
            # driver row. Treat only real <thead> rows (or an initial all-TH
            # row) as column headers; otherwise we'd throw away the standings.
            if in_thead or (not header and row_index == 0 and all_header_cells):
                if len(cells) >= len(header):
                    header = cells
                continue
            if not header and all_header_cells:
                header = cells
                continue
            body.append(cells)
        if body:
            tables.append((header, body))
    return tables


def _clean_markdown_cell(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace(chr(96), "")
    return " ".join(text.split()).strip()


def _parse_markdown_tables(markdown: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = [line.strip() for line in str(markdown or "").splitlines()]
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0

    def split_row(line: str) -> list[str]:
        raw = line.strip().strip("|")
        return [_clean_markdown_cell(cell) for cell in raw.split("|")]

    def separator(line: str) -> bool:
        if "|" not in line:
            return False
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    while index + 1 < len(lines):
        if "|" not in lines[index] or not separator(lines[index + 1]):
            index += 1
            continue
        header = split_row(lines[index])
        body: list[list[str]] = []
        index += 2
        while index < len(lines) and "|" in lines[index]:
            row = split_row(lines[index])
            if row and any(cell for cell in row):
                body.append(row)
            index += 1
        if header and body:
            tables.append((header, body))
    return tables


def _reader_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"https://r.jina.ai/http://{parts.netloc}{path}{query}"


def _reader_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    reader_url = _reader_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/plain,text/markdown;q=0.9,*/*;q=0.5",
        "X-Return-Format": "markdown",
    }
    with httpx.Client(timeout=24.0, follow_redirects=True, headers=headers) as client:
        response = client.get(reader_url)
        response.raise_for_status()
    tables = _parse_markdown_tables(response.text)
    if not tables:
        raise RuntimeError("rendered reader returned no standings tables")
    return tables


def _html_table_rows(url: str) -> list[tuple[list[str], list[list[str]]]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    direct_error: Exception | None = None
    try:
        with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        tables = _parse_html_tables(response.text)
        if tables:
            return tables
        direct_error = RuntimeError("official page returned no static standings tables")
    except Exception as exc:
        direct_error = exc

    # Several racing sites block Render/datacenter IPs or render standings
    # entirely client-side. Use a read-only rendered-page fallback while
    # keeping the official page as the canonical source shown in Pitmark.
    try:
        return _reader_table_rows(url)
    except Exception as reader_error:
        raise RuntimeError(
            f"official source unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error



def _linked_pdf_url(config: dict[str, Any], season: int) -> str:
    landing_url = _series_url(config, season)
    wanted = str(config.get("pdf_link_text") or "").strip().lower()
    fallback: str | None = None
    direct_error: Exception | None = None

    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
            response = client.get(landing_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href:
                continue
            text = " ".join(anchor.get_text(" ", strip=True).split()).lower()
            absolute = urljoin(landing_url, href)
            looks_pdf = ".pdf" in absolute.lower() or "pdf" in text
            if not looks_pdf:
                continue
            if fallback is None:
                fallback = absolute
            if wanted and wanted in text:
                return absolute
        if fallback:
            return fallback
    except Exception as exc:
        direct_error = exc

    try:
        reader_url = _reader_url(landing_url)
        with httpx.Client(
            timeout=24.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
        ) as client:
            response = client.get(reader_url)
            response.raise_for_status()
        markdown = response.text
        for label, href in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", markdown):
            text = " ".join(label.split()).lower()
            absolute = urljoin(landing_url, href.strip())
            looks_pdf = ".pdf" in absolute.lower() or "pdf" in text
            if not looks_pdf:
                continue
            if fallback is None:
                fallback = absolute
            if wanted and wanted in text:
                return absolute
        if fallback:
            return fallback
    except Exception as reader_error:
        raise RuntimeError(
            f"standings PDF link unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error

    raise RuntimeError("standings PDF link was not found on the official page")


def _pdf_text(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf,*/*;q=0.5",
    }
    with httpx.Client(timeout=24.0, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise RuntimeError("standings PDF contained no extractable text")
    return text


def _parse_asa_stars_pdf(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        parts = line.split()
        if len(parts) < 8 or not parts[0].isdigit():
            continue
        # Position, car number, driver..., bonus, stage, race, total, difference.
        tail = parts[-5:]
        if not all(_num(value) is not None for value in tail[:4]):
            continue
        name = " ".join(parts[2:-5]).strip()
        if not name:
            continue
        points = _clean_points(tail[-2])
        if points is None:
            continue
        rows.append(
            {
                "position": int(parts[0]),
                "name": name.rstrip("*").strip(),
                "number": parts[1].strip() or None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": _clean_points(tail[-1]) if _num(tail[-1]) is not None else None,
                "wins": None,
                "starts": None,
            }
        )
    return rows


def _parse_smart_modified_pdf(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        parts = line.split()
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        position = int(parts[0])
        if position < 1 or position > 200:
            continue
        point_index: int | None = None
        for index in range(2, len(parts)):
            if _num(parts[index]) is not None:
                point_index = index
                break
        if point_index is None or point_index <= 2:
            continue
        name = " ".join(parts[2:point_index]).strip()
        points = _clean_points(parts[point_index])
        if not name or points is None:
            continue
        behind = None
        if point_index + 1 < len(parts):
            candidate = parts[point_index + 1].replace("−", "-")
            if candidate.startswith("-") and _num(candidate) is not None:
                behind = _clean_points(candidate)
        rows.append(
            {
                "position": position,
                "name": name,
                "number": parts[1].strip() or None,
                "team": None,
                "manufacturer": None,
                "points": points,
                "behind": behind,
                "wins": None,
                "starts": None,
            }
        )
    return rows


def _fetch_linked_pdf(config: dict[str, Any], season: int) -> dict[str, Any]:
    pdf_url = _linked_pdf_url(config, season)
    text = _pdf_text(pdf_url)
    fmt = str(config.get("pdf_format") or "").strip().lower()
    if fmt == "asa_stars":
        entries = _parse_asa_stars_pdf(text)
    elif fmt == "smart_modified":
        entries = _parse_smart_modified_pdf(text)
    else:
        raise RuntimeError(f"Unknown standings PDF format: {fmt}")
    if len(entries) < 3:
        raise RuntimeError(f"standings PDF rows could not be parsed ({len(entries)} rows)")
    entries.sort(key=lambda item: item["position"])
    return {
        "entries": entries,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": pdf_url,
    }


def _page_tokens(url: str) -> list[str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    direct_error: Exception | None = None
    try:
        with httpx.Client(timeout=16.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        tokens = [" ".join(text.split()) for text in soup.stripped_strings if " ".join(text.split())]
        if tokens:
            return tokens
        direct_error = RuntimeError("official page returned no readable text")
    except Exception as exc:
        direct_error = exc

    try:
        reader_url = _reader_url(url)
        with httpx.Client(
            timeout=24.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
        ) as client:
            response = client.get(reader_url)
            response.raise_for_status()
        tokens: list[str] = []
        for raw in response.text.splitlines():
            value = _clean_markdown_cell(raw.lstrip("#>*- ").strip())
            if value:
                tokens.append(value)
        if tokens:
            return tokens
        raise RuntimeError("rendered reader returned no readable text")
    except Exception as reader_error:
        raise RuntimeError(
            f"official text unavailable ({direct_error}); rendered fallback failed ({reader_error})"
        ) from reader_error


def _token_index(tokens: list[str], needle: str, start: int = 0) -> int | None:
    target = _norm_header(needle)
    for index in range(max(0, start), len(tokens)):
        if _norm_header(tokens[index]) == target:
            return index
    return None



def _split_collapsed_driver_names(value: str, expected_count: int) -> list[str]:
    words = [
        word for word in str(value or "").replace("\u00a0", " ").split()
        if word and word not in {"(R)", "(r)"}
    ]
    if not words or expected_count <= 0:
        return []
    suffixes = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v"}
    names: list[str] = []
    index = 0
    while index < len(words) and len(names) < expected_count:
        remaining_names = expected_count - len(names)
        remaining_words = len(words) - index
        if remaining_words < remaining_names * 2:
            break
        take = 2
        if index + 2 < len(words) and words[index + 2].lower() in suffixes:
            take = 3
        name = " ".join(words[index:index + take]).strip()
        if name:
            names.append(name)
        index += take
    return names


def _fetch_column_sections(config: dict[str, Any], season: int) -> dict[str, Any]:
    url = _series_url(config, season)
    tokens = _page_tokens(url)
    title = str(config.get("column_title") or "Driver Standings")
    title_index = _token_index(tokens, title, 0) or 0
    pos_index = _token_index(tokens, "Pos.", title_index)
    if pos_index is None:
        pos_index = _token_index(tokens, "Pos", title_index)
    name_index = _token_index(tokens, "Driver", (pos_index or title_index) + 1)
    points_index = _token_index(tokens, "Points", (name_index or title_index) + 1)
    if pos_index is None or name_index is None or points_index is None:
        raise RuntimeError("standings columns were not found in official page text")

    stop_labels = (
        "Home town",
        "Hometown",
        "Starts",
        "Wins",
        "Top 5s",
        "Top 10s",
        "FQs",
        "Scroll Over >",
        "Entrant Standings",
    )
    stop_index = len(tokens)
    for label in stop_labels:
        found = _token_index(tokens, label, points_index + 1)
        if found is not None:
            stop_index = min(stop_index, found)

    positions: list[int] = []
    for token in tokens[pos_index + 1:name_index]:
        for piece in str(token or "").split():
            value = _parse_position(piece)
            if value is not None:
                positions.append(value)

    point_values: list[int | float | str | None] = []
    for token in tokens[points_index + 1:stop_index]:
        for piece in str(token or "").replace(",", "").split():
            if _num(piece) is not None:
                point_values.append(_clean_points(piece))

    raw_names = [
        name for name in tokens[name_index + 1:points_index]
        if name
        and _norm_header(name) not in {
            "image", "driver standings", "entrant standings", "home town",
            "hometown", "starts", "wins", "top 5s", "top 10s", "fqs",
        }
    ]
    if len(raw_names) == 1 and point_values:
        names = _split_collapsed_driver_names(raw_names[0], len(point_values))
    else:
        names = [
            " ".join(str(name).replace("(R)", "").split()).strip()
            for name in raw_names
            if _num(name) is None
        ]

    count = min(len(names), len(point_values))
    if positions:
        count = min(count, len(positions))
    if count < 3:
        raise RuntimeError(
            f"standings columns were incomplete (positions={len(positions)} names={len(names)} points={len(point_values)})"
        )

    normalized: list[dict[str, Any]] = []
    for index in range(count):
        normalized.append(
            {
                "position": positions[index] if positions else index + 1,
                "name": names[index],
                "number": None,
                "team": None,
                "manufacturer": None,
                "points": point_values[index],
                "behind": None,
                "wins": None,
                "starts": None,
            }
        )
    return {
        "entries": normalized,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": url,
    }


def _series_url(config: dict[str, Any], season: int) -> str:
    template = str(config.get("official_url_template") or "").strip()
    if template:
        fe_season = max(1, season - 2014)
        return template.format(season=season, fe_season=fe_season)
    return str(config.get("official_url") or "").strip()


def _norm_header(value: str) -> str:
    return " ".join(
        "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower()).split()
    )


def _header_index(header: list[str], aliases: tuple[str, ...] | list[str] | None) -> int | None:
    normalized = [_norm_header(item) for item in header]
    for alias in aliases or ():
        needle = _norm_header(alias)
        for index, value in enumerate(normalized):
            if value == needle or needle in value:
                return index
    return None


def _parse_position(value: Any) -> int | None:
    digits = ""
    for ch in str(value or "").strip():
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    try:
        return int(digits) if digits else None
    except ValueError:
        return None


def _fetch_official_table(config: dict[str, Any], season: int) -> dict[str, Any]:
    urls = [_series_url(config, season)]
    for fallback in config.get("fallback_urls") or ():
        value = str(fallback or "").strip()
        if value:
            urls.append(value.format(season=season, fe_season=max(1, season - 2014)))
    for template in config.get("fallback_url_templates") or ():
        value = str(template or "").strip()
        if value:
            urls.append(value.format(season=season, fe_season=max(1, season - 2014)))

    errors: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            return _fetch_official_table_url(config, url)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError(" ; ".join(errors) or "official standings unavailable")


def _fetch_official_table_url(config: dict[str, Any], url: str) -> dict[str, Any]:
    try:
        tables = _html_table_rows(url)
        return _normalize_official_tables(config, url, tables)
    except Exception as direct_error:
        try:
            tables = _reader_table_rows(url)
            return _normalize_official_tables(config, url, tables)
        except Exception as reader_error:
            raise RuntimeError(
                f"direct table parse failed ({direct_error}); rendered table parse failed ({reader_error})"
            ) from reader_error


def _normalize_official_tables(
    config: dict[str, Any],
    url: str,
    tables: list[tuple[list[str], list[list[str]]]],
) -> dict[str, Any]:
    best: tuple[list[str], list[list[str]], dict[str, int | None]] | None = None
    best_score = -1
    for header, rows in tables:
        indexes = {
            "position": _header_index(header, config.get("position_headers") or ("pos", "position")),
            "name": _header_index(header, config.get("name_headers") or ("driver", "rider")),
            "points": _header_index(header, config.get("points_headers") or ("points", "pts", "total")),
            "behind": _header_index(header, config.get("behind_headers") or ("gap", "behind")),
            "wins": _header_index(header, config.get("wins_headers") or ("wins",)),
            "starts": _header_index(header, config.get("starts_headers") or ("starts",)),
            "number": _header_index(header, config.get("number_headers") or NUMBER_HEADERS),
            "team": _header_index(header, config.get("team_headers") or TEAM_HEADERS),
            "manufacturer": _header_index(header, config.get("manufacturer_headers") or MANUFACTURER_HEADERS),
        }
        if indexes["name"] is None or indexes["points"] is None:
            continue
        score = sum(1 for value in indexes.values() if value is not None) + min(len(rows), 40) / 100
        if score > best_score:
            best = (header, rows, indexes)
            best_score = score
    if not best:
        raise RuntimeError("official standings table was not present in page HTML")
    _, rows, indexes = best
    normalized: list[dict[str, Any]] = []
    for fallback_position, row in enumerate(rows, start=1):
        name_index = indexes["name"]
        points_index = indexes["points"]
        if name_index is None or points_index is None:
            continue

        offset = 0
        if name_index < len(row):
            candidate_name = str(row[name_index] or "").strip()
            if candidate_name.startswith("[](") and candidate_name.endswith(")"):
                offset = 1

        def shifted(index: int | None) -> int | None:
            return None if index is None else index + offset

        actual_name_index = shifted(name_index)
        actual_points_index = shifted(points_index)
        if (
            actual_name_index is None
            or actual_points_index is None
            or actual_name_index >= len(row)
            or actual_points_index >= len(row)
        ):
            continue

        name = str(row[actual_name_index] or "").strip()
        points = _clean_points(row[actual_points_index])
        if not name or points is None:
            continue

        # MyRacePass inserts the unlabeled profile cell AFTER the rank/car columns,
        # so Driver/Points need the offset but championship position does not.
        position_index = indexes["position"]
        position = (
            _parse_position(row[position_index])
            if position_index is not None and position_index < len(row)
            else fallback_position
        ) or fallback_position

        def field(index_name: str) -> Any:
            index = shifted(indexes.get(index_name))
            return row[index] if index is not None and index < len(row) else None

        normalized.append(
            {
                "position": position,
                "name": name,
                "number": str(field("number") or "").strip() or None,
                "team": str(field("team") or "").strip() or None,
                "manufacturer": str(field("manufacturer") or "").strip() or None,
                "points": points,
                "behind": _clean_points(field("behind")),
                "wins": _clean_points(field("wins")),
                "starts": _clean_points(field("starts")),
            }
        )
    if not normalized:
        raise RuntimeError("official standings rows could not be parsed")
    normalized.sort(key=lambda item: item["position"])
    return {
        "entries": normalized,
        "source_name": str(config.get("source_name") or "Official standings"),
        "provider_url": url,
    }


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
                "number": None,
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
                "number": number,
                "team": None,
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



def _identity_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _official_metadata_from_tables(
    config: dict[str, Any],
    season: int,
) -> tuple[dict[str, dict[str, str | None]], str | None]:
    """Read optional identity columns from the series' own official page only."""
    url = str(config.get("metadata_url") or _series_url(config, season))
    try:
        tables = _html_table_rows(url)
    except Exception:
        return {}, None

    best: tuple[list[str], list[list[str]], dict[str, int | None]] | None = None
    best_score = -1
    for header, rows in tables:
        indexes = {
            "name": _header_index(header, config.get("name_headers") or ("driver", "rider")),
            "number": _header_index(header, config.get("number_headers") or NUMBER_HEADERS),
            "team": _header_index(header, config.get("team_headers") or TEAM_HEADERS),
            "manufacturer": _header_index(header, config.get("manufacturer_headers") or MANUFACTURER_HEADERS),
        }
        if indexes["name"] is None:
            continue
        identity_columns = sum(
            1 for key in ("number", "team", "manufacturer") if indexes[key] is not None
        )
        if identity_columns == 0:
            continue
        score = identity_columns * 10 + min(len(rows), 50) / 100
        if score > best_score:
            best = (header, rows, indexes)
            best_score = score
    if not best:
        return {}, None

    _, rows, indexes = best
    out: dict[str, dict[str, str | None]] = {}
    for row in rows:
        name_index = indexes["name"]
        if name_index is None or name_index >= len(row):
            continue
        name = str(row[name_index] or "").strip()
        key = _identity_key(name)
        if not key:
            continue

        def cell(field: str) -> str | None:
            index = indexes.get(field)
            if index is None or index >= len(row):
                return None
            value = str(row[index] or "").strip()
            return value or None

        out[key] = {
            "number": cell("number"),
            "team": cell("team"),
            "manufacturer": cell("manufacturer"),
        }
    return out, url if out else None



def _same_host(left: str, right: str) -> bool:
    try:
        left_host = (urlsplit(left).hostname or "").lower().removeprefix("www.")
        right_host = (urlsplit(right).hostname or "").lower().removeprefix("www.")
        return bool(left_host and right_host and left_host == right_host)
    except Exception:
        return False


def _http_image_url(value: str) -> bool:
    try:
        return urlsplit(str(value or "")).scheme.lower() in {"http", "https"}
    except Exception:
        return False


def _provider_identity_provenance(
    config: dict[str, Any],
    season: int,
    fetched: dict[str, Any],
) -> tuple[bool, str | None]:
    """Approve identity only when its source chain originates with the series itself."""
    provider = str(config.get("provider") or "")
    official_url = _series_url(config, season)
    provider_url = str(fetched.get("provider_url") or "").strip()

    # Linked PDFs are discovered by following a link on the configured official
    # standings page. The PDF may live on a CDN, but the official landing page
    # is the provenance anchor.
    if provider == "linked_pdf" and provider_url:
        return True, official_url

    # These adapters consume the configured official series URL directly.
    if provider in {"column_sections", "imsa", "wec"} and provider_url:
        if provider_url == official_url or _same_host(provider_url, official_url):
            return True, official_url

    # official_table may use third-party fallbacks (for example High Limit).
    # Only identity parsed from the configured official host is accepted.
    if provider == "official_table" and provider_url:
        if provider_url == official_url or _same_host(provider_url, official_url):
            return True, official_url

    return False, None


def _enrich_official_identity(
    config: dict[str, Any],
    season: int,
    fetched: dict[str, Any],
) -> dict[str, Any]:
    entries = [dict(item) for item in fetched.get("entries") or []]
    if not entries:
        result = dict(fetched)
        result["metadata_source_url"] = None
        result["metadata_verified"] = False
        return result

    provider_verified, provider_source = _provider_identity_provenance(
        config, season, fetched
    )

    # Identity parsed from an unverified fallback must never leak into the hub.
    if not provider_verified:
        for item in entries:
            item["number"] = None
            item["team"] = None
            item["manufacturer"] = None

    metadata_source_url = provider_source
    metadata_verified = provider_verified and any(
        item.get("number") or item.get("team") or item.get("manufacturer")
        for item in entries
    )

    # Independently inspect the configured official series page for identity
    # columns. This can fill missing fields even when the standings provider is
    # a structured third-party feed used only for positions/points.
    metadata, table_url = _official_metadata_from_tables(config, season)
    if metadata:
        matched = False
        for item in entries:
            values = metadata.get(_identity_key(item.get("name")))
            if not values:
                continue
            for field in ("number", "team", "manufacturer"):
                if not item.get(field) and values.get(field):
                    item[field] = values[field]
                    matched = True
        if matched:
            metadata_source_url = table_url or _series_url(config, season)
            metadata_verified = True

    for item in entries:
        item.setdefault("number", None)
        item.setdefault("team", None)
        item.setdefault("manufacturer", None)

    result = dict(fetched)
    result["entries"] = entries
    result["metadata_source_url"] = metadata_source_url if metadata_verified else None
    result["metadata_verified"] = bool(metadata_verified)
    return result


def _logo_score(text: str, url: str, terms: tuple[str, ...]) -> int:
    hay = f"{text} {url}".lower()
    score = 0
    if "logo" in hay:
        score += 4
    for term in terms:
        term = term.lower().strip()
        if term and term in hay:
            score += 7
    if any(bad in hay for bad in ("sponsor", "partner", "advert", "ticket", "driver", "car-photo", "hero-")):
        score -= 6
    return score


def _discover_official_logo(
    config: dict[str, Any],
    season: int,
) -> tuple[str | None, str | None]:
    """Return only imagery referenced by the configured official series page."""
    source_url = _series_url(config, season)
    terms = OFFICIAL_LOGO_TERMS.get(str(config.get("key") or ""), ())
    if not terms:
        return None, None

    candidates: list[tuple[int, str]] = []
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(timeout=14.0, follow_redirects=True, headers=headers) as client:
            response = client.get(source_url)
            response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for image in soup.find_all("img"):
            raw_url = (
                image.get("src")
                or image.get("data-src")
                or image.get("data-lazy-src")
                or ""
            )
            raw_url = str(raw_url).strip()
            if not raw_url:
                continue
            absolute = urljoin(source_url, raw_url)
            if not _http_image_url(absolute):
                continue
            label = " ".join(
                str(value or "")
                for value in (
                    image.get("alt"), image.get("title"), image.get("id"),
                    " ".join(image.get("class") or []),
                )
            )
            score = _logo_score(label, absolute, terms)
            if score >= 7:
                candidates.append((score, absolute))
    except Exception:
        pass

    if not candidates:
        try:
            reader_url = _reader_url(source_url)
            with httpx.Client(
                timeout=20.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"},
            ) as client:
                response = client.get(reader_url)
                response.raise_for_status()
            for alt, raw_url in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", response.text):
                absolute = urljoin(source_url, raw_url.strip())
                if not _http_image_url(absolute):
                    continue
                score = _logo_score(alt, absolute, terms)
                if score >= 7:
                    candidates.append((score, absolute))
        except Exception:
            pass

    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], source_url



def _fetch_series(config: dict[str, Any], season: int) -> dict[str, Any]:
    provider = config["provider"]
    if provider == "espn":
        return _fetch_espn(config, season)
    if provider == "jolpica":
        return _fetch_f1(config, season)
    if provider == "imsa":
        return _fetch_imsa(config, season)
    if provider == "wec":
        return _fetch_wec(config, season)
    if provider == "official_table":
        return _fetch_official_table(config, season)
    if provider == "linked_pdf":
        return _fetch_linked_pdf(config, season)
    if provider == "column_sections":
        return _fetch_column_sections(config, season)
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


def _persist(config: dict[str, Any], season: int, fetched: dict[str, Any]) -> dict[str, Any]:
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
        "official_url": _series_url(config, season),
        "source_name": fetched.get("source_name") or "Standings source",
        "provider_url": fetched.get("provider_url"),
        "metadata_source_url": fetched.get("metadata_source_url"),
        "metadata_verified": bool(fetched.get("metadata_verified")),
        "series_logo_url": fetched.get("series_logo_url"),
        "series_logo_source_url": fetched.get("series_logo_source_url"),
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
                source_url=_series_url(config, season),
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
            # Metadata/logo provenance can improve without the points changing.
            existing.source_name = normalized["source_name"]
            existing.source_url = _series_url(config, season)
            existing.payload_json = json.dumps(normalized, ensure_ascii=False, default=str)
            db.commit()
            fetched_at = existing.fetched_at
            snapshot_id = existing.id
    normalized["entries"] = _movement(entries, previous)
    normalized["fetched_at"] = fetched_at.isoformat() if fetched_at else utcnow().isoformat()
    normalized["snapshot_id"] = snapshot_id
    normalized["status"] = "live"
    normalized["stale"] = False
    normalized["error"] = None
    return normalized


def _fallback(config: dict[str, Any], season: int, error: Exception) -> dict[str, Any]:
    latest = _latest_snapshot(config["key"], season)
    cached = _decode_snapshot(latest)
    if cached:
        cached.update(
            {
                "series_key": config["key"],
                "series_name": config["name"],
                "short_name": config["short_name"],
                "group": config["group"],
                "official_url": _series_url(config, season),
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
        "official_url": _series_url(config, season),
        "season": season,
        "source_name": None,
        "provider_url": None,
        "metadata_source_url": None,
        "metadata_verified": False,
        "entries": [],
        "fetched_at": None,
        "snapshot_id": None,
        "status": "unavailable",
        "stale": True,
        "error": str(error),
    }



def _sanitize_identity_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Fail closed: identity fields are visible only with verified official provenance."""
    result = copy.deepcopy(item)
    verified = bool(result.get("metadata_verified"))
    result["metadata_verified"] = verified
    if not verified:
        result["metadata_source_url"] = None
        for entry in result.get("entries") or []:
            entry["number"] = None
            entry["team"] = None
            entry["manufacturer"] = None
    return result


def _load_one(config: dict[str, Any], season: int) -> dict[str, Any]:
    try:
        fetched = _fetch_series(config, season)
        fetched = _enrich_official_identity(config, season, fetched)
        logo_url, logo_source_url = _discover_official_logo(config, season)
        fetched["series_logo_url"] = logo_url
        fetched["series_logo_source_url"] = logo_source_url
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
    with ThreadPoolExecutor(max_workers=min(8, len(SERIES))) as pool:
        future_map = {pool.submit(_load_one, config, season): config for config in SERIES}
        for future in as_completed(future_map):
            config = future_map[future]
            try:
                results[config["key"]] = future.result()
            except Exception as exc:
                results[config["key"]] = _fallback(config, season, exc)

    ordered = [_sanitize_identity_payload(results[config["key"]]) for config in SERIES]
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


def get_standings_snapshot_hub(*, season: int | None = None) -> dict[str, Any]:
    """Return the latest saved standings immediately without touching remote sources."""
    season = int(season or utcnow().year)
    now = utcnow()
    ordered: list[dict[str, Any]] = []
    for config in SERIES:
        latest_row = _latest_snapshot(config["key"], season)
        snapshot = _decode_snapshot(latest_row)
        if snapshot:
            entries = snapshot.get("entries") or []
            previous_row = _latest_snapshot(
                config["key"],
                season,
                excluding=snapshot.get("fingerprint"),
            )
            previous = _decode_snapshot(previous_row)
            fetched_at = latest_row.fetched_at if latest_row else None
            age_seconds = (now - fetched_at).total_seconds() if fetched_at else None
            fresh = age_seconds is not None and age_seconds <= 6 * 3600
            snapshot.update(
                {
                    "series_key": config["key"],
                    "series_name": config["name"],
                    "short_name": config["short_name"],
                    "group": config["group"],
                    "season": season,
                    "official_url": _series_url(config, season),
                    "source_name": snapshot.get("source_name") or latest_row.source_name,
                    "metadata_verified": bool(snapshot.get("metadata_verified")),
                    "entries": _movement(entries, previous),
                    "status": "live" if fresh else "stale",
                    "stale": not fresh,
                    "error": None,
                }
            )
            ordered.append(_sanitize_identity_payload(snapshot))
            continue
        ordered.append(
            {
                "series_key": config["key"],
                "series_name": config["name"],
                "short_name": config["short_name"],
                "group": config["group"],
                "official_url": _series_url(config, season),
                "season": season,
                "source_name": None,
                "provider_url": None,
                "metadata_source_url": None,
                "metadata_verified": False,
                "entries": [],
                "fetched_at": None,
                "snapshot_id": None,
                "status": "unavailable",
                "stale": True,
                "error": "No saved Pitmark snapshot yet.",
            }
        )

    live = sum(1 for item in ordered if item.get("status") == "live")
    stale = sum(1 for item in ordered if item.get("status") == "stale")
    unavailable = sum(1 for item in ordered if item.get("status") == "unavailable")
    synced_times = [item.get("fetched_at") for item in ordered if item.get("fetched_at")]
    return {
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



def get_series_logo_info(series_key: str, *, season: int | None = None) -> dict[str, str] | None:
    season = int(season or utcnow().year)
    config = next((item for item in SERIES if item["key"] == series_key), None)
    if not config:
        return None
    snapshot = _decode_snapshot(_latest_snapshot(series_key, season))
    if not snapshot:
        return None
    logo_url = str(snapshot.get("series_logo_url") or "").strip()
    source_url = str(snapshot.get("series_logo_source_url") or "").strip()
    if not logo_url or not source_url or not _http_image_url(logo_url):
        return None
    # Source provenance must be the configured official series page.
    if source_url != _series_url(config, season):
        return None
    return {"url": logo_url, "source_url": source_url}



def clear_standings_cache() -> None:
    with _cache_lock:
        _cache["at"] = None
        _cache["value"] = None
