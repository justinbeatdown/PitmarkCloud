from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "PitmarkRaceCenter/1.0 (+https://pitmarkracing.com)"
SEASON = 2026

# Schedule/watch discovery is intentionally separate from standings. This lets
# Pitmark cover support series that do not expose a usable public standings feed.
SERIES_EVENT_CONFIG: dict[str, dict[str, Any]] = {
    "nascar-cup": {"name":"NASCAR Cup Series","group":"NASCAR","espn_league":"nascar-premier","schedule_url":"https://www.nascar.com/nascar-cup-series/2026/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-oreilly": {"name":"NASCAR O'Reilly Auto Parts Series","group":"NASCAR","espn_league":"nascar-secondary","schedule_url":"https://www.nascar.com/nascar-oreilly-auto-parts-series/2026/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-truck": {"name":"NASCAR CRAFTSMAN Truck Series","group":"NASCAR","espn_league":"nascar-truck","schedule_url":"https://www.nascar.com/nascar-craftsman-truck-series/2026/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-whelen-modified": {"name":"NASCAR Whelen Modified Tour","group":"NASCAR","schedule_url":"https://www.nascar.com/whelen-modified-tour/","logo_source_url":"https://www.nascar.com/whelen-modified-tour/","logo_url":"https://www.nascar.com/wp-content/uploads/sites/7/2024/01/05/NWMT_Logo.svg","watch_name":"NASCAR / FloRacing","watch_url":"https://www.nascar.com/tv-schedule/"},
    "arca-menards": {"name":"ARCA Menards Series","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/","logo_source_url":"https://www.arcaracing.com/competitor-site/","logo_url":"https://www.arcaracing.com/wp-content/uploads/sites/36/2022/11/10/Menards_ANASCARTouringDivision_Primary_4C_BLK.png"},
    "arca-east": {"name":"ARCA Menards Series East","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/","logo_source_url":"https://www.arcaracing.com/competitor-site/","logo_url":"https://www.arcaracing.com/wp-content/uploads/sites/36/2021/02/02/ArcaMenardsSeries_East_ANASCARTouringDivision_Primary_4C_BLK.png"},
    "arca-west": {"name":"ARCA Menards Series West","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/","logo_source_url":"https://www.arcaracing.com/competitor-site/","logo_url":"https://www.arcaracing.com/wp-content/uploads/sites/36/2021/02/02/ArcaMenardsSeries_West_ANASCARTouringDivision_Primary_4C_BLK.png"},

    "ascs-national": {"name":"American Sprint Car Series National Tour","group":"Grassroots / Dirt","schedule_url":"https://ascsracing.com/print-schedule.php?series=ASCS","watch_name":"DIRTVision","watch_url":"https://www.dirtvision.com/","logo_source_url":"https://ascsracing.com/"},

    "world-of-outlaws-sprint": {"name":"World of Outlaws Sprint Car Series","group":"Dirt","schedule_url":"https://worldofoutlaws.com/sprintcars/schedule/","watch_name":"DIRTVision","watch_url":"https://www.dirtvision.com/"},
    "world-of-outlaws-late-models": {"name":"World of Outlaws Late Model Series","group":"Dirt","schedule_url":"https://worldofoutlaws.com/latemodels/schedule/","watch_name":"DIRTVision","watch_url":"https://www.dirtvision.com/"},
    "lucas-oil-late-models": {"name":"Lucas Oil Late Model Dirt Series","group":"Dirt","schedule_url":"https://www.lucasdirt.com/schedule/","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "high-limit-sprint": {"name":"High Limit Racing","group":"Dirt","schedule_url":"https://www.highlimitracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/","logo_source_url":"https://www.highlimitracing.com/","logo_url":"https://cdn.myracepass.com/v1/siteresources/44498/v1/img/logo.png"},
    "usac-national-sprint": {"name":"USAC AMSOIL National Sprint","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/","logo_source_url":"https://www.usacracing.com/","logo_url":"https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif"},
    "usac-national-midget": {"name":"USAC NOS Energy Drink National Midget","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/","logo_source_url":"https://www.usacracing.com/","logo_url":"https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif"},
    "usac-silver-crown": {"name":"USAC Silver Crown","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/","logo_source_url":"https://www.usacracing.com/","logo_url":"https://cdn.prod.website-files.com/65a055cdd264f6a7981147fe/65edc3afc8c77c845c80e17b_USAC_Racing_Logo_White.avif"},

    "cars-tour-lmsc": {"name":"zMAX CARS Tour — Late Model Stock","group":"Short Track","schedule_url":"https://www.carsracingtour.com/schedule/","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "asa-stars": {"name":"ASA STARS National Tour","group":"Short Track","schedule_url":"https://starsnationaltour.com/schedule/","watch_name":"Official Broadcast Info","watch_url":"https://starsnationaltour.com/"},
    "smart-modified": {"name":"SMART Modified Tour","group":"Short Track","schedule_url":"https://smartmodifiedtour.com/schedule","watch_name":"Official Broadcast Info","watch_url":"https://smartmodifiedtour.com/"},

    "nhra-top-fuel": {"name":"NHRA Top Fuel","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","logo_source_url":"https://www.nhra.com/media-center/logos","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-funny-car": {"name":"NHRA Funny Car","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","logo_source_url":"https://www.nhra.com/media-center/logos","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-pro-stock": {"name":"NHRA Pro Stock","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","logo_source_url":"https://www.nhra.com/media-center/logos","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-pro-stock-motorcycle": {"name":"NHRA Pro Stock Motorcycle","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","logo_source_url":"https://www.nhra.com/media-center/logos","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},

    "f1": {"name":"Formula 1","group":"Open Wheel","provider":"f1","schedule_url":"https://www.formula1.com/en/racing/2026","logo_source_url":"https://www.formula1.com/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/3/33/F1.svg","watch_name":"F1 TV","watch_url":"https://f1tv.formula1.com/"},
    "indycar": {"name":"NTT INDYCAR SERIES","group":"Open Wheel","espn_league":"irl","schedule_url":"https://www.indycar.com/Schedule","watch_name":"INDYCAR Ways to Watch","watch_url":"https://www.indycar.com/ways-to-watch","logo_source_url":"https://www.indycar.com/Support","logo_url":"https://www.indycar.com/-/media/IndyCar/Content/Footer/indycar-horizontal.png"},
    "formula-e": {"name":"ABB FIA Formula E World Championship","group":"Open Wheel","schedule_url":"https://www.fiaformulae.com/en/calendar","logo_source_url":"https://www.fiaformulae.com/","logo_url":"https://www.fiaformulae.com/images/formula-e-footer.svg","watch_name":"Formula E Ways to Watch","watch_url":"https://www.fiaformulae.com/en/ways-to-watch"},

    "imsa-weathertech": {"name":"IMSA WeatherTech SportsCar Championship","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_IWSC_Logo_MediaCenter.png","watch_name":"NBC / Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-michelin-pilot": {"name":"IMSA Michelin Pilot Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_IMPC_Logo_MediaCenter.png","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-vp-racing": {"name":"IMSA VP Racing SportsCar Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_VPRC_Logo_MediaCenter.png","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-porsche-carrera-cup": {"name":"Porsche Carrera Cup North America","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_PCCNA_Logo_MediaCenter.png","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-mustang-challenge": {"name":"Mustang Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_MC_Logo_MediaCenter.png","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-lamborghini-super-trofeo": {"name":"Lamborghini Super Trofeo North America","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.imsa.com/wp-content/uploads/sites/32/2025/12/08/2025_LST_Logo_MediaCenter.png","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-mx5-cup": {"name":"Mazda MX-5 Cup","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","logo_source_url":"https://www.imsa.com/media-center/","logo_url":"https://www.mx-5cup.com/images/default-source/logos/series-logos/mx5logo2024-2.png?sfvrsn=43c07ae5_2","watch_name":"IMSA.TV / YouTube","watch_url":"https://www.imsa.com/tv/"},
    "wec": {"name":"FIA World Endurance Championship","group":"Sports Cars","schedule_url":"https://www.fiawec.com/en/calendar/80","watch_name":"FIA WEC TV","watch_url":"https://fiawec.tv/"},
    "gtwc-america": {"name":"GT World Challenge America","group":"Sports Cars","schedule_url":"https://www.gt-world-challenge-america.com/calendar","logo_source_url":"https://www.gt-world-challenge-america.com/","watch_name":"GTWorld","watch_url":"https://www.youtube.com/@GTWorld"},
    "trans-am": {"name":"Trans Am Series","group":"Sports Cars","schedule_url":"https://gotransam.com/events/","logo_source_url":"https://gotransam.com/","watch_name":"Trans Am Official Broadcast Info","watch_url":"https://gotransam.com/"},
    "dtm": {"name":"DTM","group":"Touring Cars","schedule_url":"https://www.dtm.com/en/events","logo_source_url":"https://www.dtm.com/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/5/55/Deutsche_Tourenwagen_Masters_-_Logo_2025.png","watch_name":"DTM Official TV Guide","watch_url":"https://www.dtm.com/en/tv"},
    "btcc": {"name":"British Touring Car Championship","group":"Touring Cars","schedule_url":"https://btcc.net/calendar/","logo_source_url":"https://btcc.net/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/f/fd/BTCC_logo.svg","watch_name":"BTCC Watch Live","watch_url":"https://btcc.net/watch-live/"},

    "supercars": {"name":"Repco Supercars Championship","group":"Touring Cars","schedule_url":"https://www.supercars.com/calendar","watch_name":"Supercars Ways to Watch","watch_url":"https://www.supercars.com/ways-to-watch"},

    "motogp": {"name":"MotoGP World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","logo_source_url":"https://www.motogp.com/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/f/f9/MotoGP_logo_%282024%29.svg","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "moto2": {"name":"Moto2 World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","logo_source_url":"https://www.motogp.com/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/4/46/Moto2_logo_%282024%29.svg","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "moto3": {"name":"Moto3 World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","logo_source_url":"https://www.motogp.com/","logo_url":"https://upload.wikimedia.org/wikipedia/commons/d/d7/Moto3_logo_%282024%29.svg","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "worldsbk": {"name":"FIM Superbike World Championship","group":"Motorcycles","schedule_url":"https://www.worldsbk.com/en/calendar","logo_source_url":"https://www.worldsbk.com/","logo_url":"https://www.worldsbk.com/themes/responsive/static/img/common/logo_sbk.svg","watch_name":"WorldSBK VideoPass","watch_url":"https://www.worldsbk.com/en/videos"},
}

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}
_logo_lock = threading.Lock()
_logo_cache: dict[str, tuple[datetime, str | None, str | None]] = {}
_LOGO_RESTRICTED: set[str] = set()


def _logo_tokens(config: dict[str, Any]) -> tuple[str, ...]:
    name = str(config.get("name") or "").casefold()
    drop = {
        "series","championship","world","racing","national","tour","challenge",
        "north","america","presented","by","the","fia","fim","sports","car"
    }
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", name)
        if len(token) >= 3 and token not in drop
    ]
    return tuple(dict.fromkeys(tokens[:6]))


def _image_url(value: str) -> bool:
    raw = str(value or "").strip().lower()
    if not raw.startswith(("http://","https://","/")):
        return False
    path = urlsplit(raw if raw.startswith("http") else "https://example.com"+raw).path.lower()
    return any(path.endswith(ext) for ext in (".png",".jpg",".jpeg",".webp",".gif",".svg",".avif"))


def _logo_candidate_score(label: str, url: str, config: dict[str, Any]) -> int:
    hay = f"{label} {url}".casefold()
    tokens = _logo_tokens(config)
    score = 0
    if "logo" in hay:
        score += 6
    for token in tokens:
        if token in hay:
            score += 3
    if any(bad in hay for bad in ("sponsor","ticket","flag","icon-","favicon","social","app-store","google-play")):
        score -= 5
    return score


def _discover_official_event_logo(key: str, config: dict[str, Any]) -> tuple[str | None, str | None]:
    if key in _LOGO_RESTRICTED:
        return None, None
    explicit = str(config.get("logo_url") or "").strip()
    source_url = str(config.get("logo_source_url") or config.get("schedule_url") or "").strip()
    if explicit:
        return explicit, source_url or str(config.get("schedule_url") or "")

    now = datetime.now(timezone.utc)
    with _logo_lock:
        cached = _logo_cache.get(key)
        if cached and (now - cached[0]).total_seconds() < 24 * 3600:
            return cached[1], cached[2]

    candidates: list[tuple[int, str]] = []
    if source_url:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            with httpx.Client(timeout=6.0, follow_redirects=True, headers=headers) as client:
                response = client.get(source_url)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for meta in soup.find_all("meta"):
                prop = str(meta.get("property") or meta.get("name") or "").casefold()
                if prop in {"og:image","twitter:image","twitter:image:src"}:
                    raw = str(meta.get("content") or "").strip()
                    if raw:
                        absolute = urljoin(source_url, raw)
                        score = _logo_candidate_score(prop, absolute, config)
                        if score >= 6:
                            candidates.append((score, absolute))

            for image in soup.find_all(["img","source"]):
                raw = image.get("src") or image.get("data-src") or image.get("data-lazy-src") or image.get("srcset") or image.get("data-srcset") or ""
                raw = str(raw).strip()
                if "," in raw:
                    raw = raw.split(",",1)[0].strip().split(" ",1)[0]
                if not raw:
                    continue
                absolute = urljoin(source_url, raw)
                if not _image_url(absolute):
                    continue
                label = " ".join(str(v or "") for v in (
                    image.get("alt"), image.get("title"), image.get("id"),
                    " ".join(image.get("class") or []),
                ))
                score = _logo_candidate_score(label, absolute, config)
                if score >= 6:
                    candidates.append((score, absolute))
        except Exception:
            pass

        if not candidates:
            try:
                markdown = _reader_markdown(source_url)
                for alt, raw in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", markdown):
                    absolute = urljoin(source_url, raw.strip())
                    if not _image_url(absolute):
                        continue
                    score = _logo_candidate_score(alt, absolute, config)
                    if score >= 6:
                        candidates.append((score, absolute))
            except Exception:
                pass

    logo = max(candidates, key=lambda item:item[0])[1] if candidates else None
    with _logo_lock:
        _logo_cache[key] = (now, logo, source_url or None)
    return logo, source_url or None


def _iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _espn_schedule(config: dict[str, Any]) -> list[dict[str, Any]]:
    league = config["espn_league"]
    url = f"https://site.api.espn.com/apis/site/v2/sports/racing/{league}/scoreboard?dates={SEASON}"
    with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()

    out: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        competition = (event.get("competitions") or [{}])[0] or {}
        status = event.get("status") or competition.get("status") or {}
        status_type = status.get("type") or {}
        venue_data = competition.get("venue") or {}
        address = venue_data.get("address") or {}
        broadcasts: list[str] = []
        for raw in competition.get("broadcasts") or []:
            if isinstance(raw, dict):
                broadcasts.extend(str(x) for x in (raw.get("names") or []) if x)
        location = ", ".join(
            str(value).strip()
            for value in (address.get("city"), address.get("state"), address.get("country"))
            if str(value or "").strip()
        ) or None
        links = event.get("links") or competition.get("links") or []
        event_url = next(
            (
                str(item.get("href") or "").strip()
                for item in links
                if isinstance(item, dict) and str(item.get("href") or "").startswith("http")
            ),
            None,
        )
        out.append({
            "event_id": str(event.get("id") or competition.get("id") or "").strip() or None,
            "name": event.get("name") or event.get("shortName") or config["name"],
            "start": _iso(event.get("date") or competition.get("date")),
            "state": str(status_type.get("state") or "pre").lower(),
            "completed": bool(status_type.get("completed")),
            "broadcast": " / ".join(dict.fromkeys(broadcasts)) or None,
            "venue": venue_data.get("fullName") or venue_data.get("name"),
            "location": location,
            "event_url": event_url,
            "source_url": config.get("schedule_url"),
        })
    return out


def _f1_schedule(config: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"https://api.jolpi.ca/ergast/f1/{SEASON}.json"
    with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    out: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for race in races:
        date = race.get("date")
        time_value = race.get("time") or "00:00:00Z"
        start = _iso(f"{date}T{time_value}") if date else None
        state = "pre"
        completed = False
        if start:
            dt = datetime.fromisoformat(start)
            if now >= dt + timedelta(hours=4):
                state, completed = "post", True
            elif dt <= now < dt + timedelta(hours=4):
                state = "in"
        circuit = race.get("Circuit") or {}
        location_data = circuit.get("Location") or {}
        location = ", ".join(
            str(value).strip()
            for value in (location_data.get("locality"), location_data.get("country"))
            if str(value or "").strip()
        ) or None
        out.append({
            "event_id": str(race.get("round") or "").strip() or None,
            "name": race.get("raceName") or config["name"],
            "start": start,
            "state": state,
            "completed": completed,
            "broadcast": "F1 TV",
            "venue": circuit.get("circuitName"),
            "location": location,
            "event_url": race.get("url"),
            "source_url": config.get("schedule_url"),
        })
    return out


def _reader_markdown(url: str) -> str:
    target = "https://r.jina.ai/http://" + url.split("://", 1)[-1]
    with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"}) as client:
        response = client.get(target)
        response.raise_for_status()
        return response.text


def _clean_schedule_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\s*\]", " ", text)
    text = text.replace("[", " ").replace("]", " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[#*_\x60]+", " ", text)
    text = re.sub(
        r"\b(?:buy now|tickets?|ticket info|event guide|event lodging|tv schedule|watch live|watch now|learn more|read more)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bImage\s*:?\s*[^·|]+(?:flag|logo)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" ·|-")
    return text


def _event_title(lines: list[str], index: int, match: re.Match[str], config: dict[str, Any]) -> str:
    candidates: list[str] = []
    month_date = re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s*20\d{2})?\b",
        re.IGNORECASE,
    )
    weekday = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b,?", re.IGNORECASE)

    for pos in (index, index - 1, index + 1):
        if pos < 0 or pos >= len(lines):
            continue
        value = _clean_schedule_text(lines[pos])
        value = month_date.sub(" ", value)
        value = weekday.sub(" ", value)
        value = re.sub(r"^\s*\d{1,2}\s*[·|:-]\s*", "", value)
        value = re.sub(r"\s*[·|]\s*", " · ", value)
        value = re.sub(r"\s+", " ", value).strip(" ·|-")
        if not value:
            continue

        # Keep the useful segment and drop CTA/nav fragments.
        segments = [seg.strip() for seg in value.split(" · ") if seg.strip()]
        for seg in segments or [value]:
            low = seg.casefold()
            if len(seg) < 3 or len(seg) > 110:
                continue
            if any(token in low for token in (
                "schedule", "tickets", "event guide", "event lodging", "tv schedule",
                "privacy", "cookie", "sign up", "newsletter", "image:", "utm_",
            )):
                continue
            if re.fullmatch(r"\d+", seg):
                continue
            candidates.append(seg)

    if candidates:
        def score(value: str) -> tuple[int, int]:
            low = value.casefold()
            points = 0
            if any(word in low for word in ("grand prix", "nationals", "classic", "championship", "shootout", "arch", "race", "showdown")):
                points += 6
            if str(config.get("name") or "").casefold() not in low:
                points += 2
            if value.isupper():
                points += 1
            return points, -len(value)
        candidates.sort(key=score, reverse=True)
        return candidates[0]

    return "See official schedule"


_VENUE_HINTS = (
    "speedway",
    "raceway",
    "race course",
    "racecourse",
    "motor speedway",
    "motorsports park",
    "motorsport park",
    "motorplex",
    "dragway",
    "circuit",
    "autodrome",
    "autódromo",
    "fairgrounds",
    "road course",
    "race track",
    "racetrack",
)

_VENUE_EXACTISH = (
    "road america",
    "road atlanta",
    "watkins glen",
    "lime rock",
    "sebring",
    "laguna seca",
    "mid-ohio",
)


def _venue_candidate(value: str, *, title: str = "", series_name: str = "") -> str | None:
    candidate = _clean_schedule_text(value).strip(" ·|-")
    if not candidate or len(candidate) < 4 or len(candidate) > 82:
        return None

    low = candidate.casefold()
    if any(token in low for token in (
        "ticket", "watch", "broadcast", "results", "standings", "newsletter",
        "privacy", "cookie", "schedule", "presented by", "feature", "heat ",
        "qualifying", "practice", "main event", "championship points",
    )):
        return None
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
                 r"|january|february|march|april|june|july|august|september|october|november|december)"
                 r"\.?\s+\d{1,2}\b", low):
        return None
    if re.search(r"\b20\d{2}\b", low):
        return None
    if re.search(r"\b(?:\$\d|\d{1,3},\d{3}\s*to win|laps?\b)", low):
        return None
    if series_name and series_name.casefold() in low:
        return None

    looks_like_venue = (
        any(hint in low for hint in _VENUE_HINTS)
        or any(name in low for name in _VENUE_EXACTISH)
    )
    if not looks_like_venue:
        return None

    title_low = str(title or "").casefold().strip()
    # If the "venue" is literally the whole event title, accept only clean
    # venue-shaped names. Event phrases like "Series at X Speedway" are rejected.
    if title_low and low == title_low:
        if any(token in low for token in (" at ", " vs ", " showdown", " nationals", " classic", " weekend", " night ")):
            return None

    # Strip common event-copy prefixes while preserving the actual venue name.
    candidate = re.sub(
        r"^(?:at|from|visit|race at|racing at|returns? to|heads? to)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip(" ·|-")
    if len(candidate) > 82:
        return None
    return candidate or None


def _schedule_venue(lines: list[str], index: int, title: str, config: dict[str, Any]) -> str | None:
    candidates: list[tuple[int, str]] = []
    series_name = str(config.get("name") or "")

    # Prefer nearby standalone lines over the line containing the date/event.
    positions = [index - 2, index - 1, index + 1, index + 2, index]
    for pos in positions:
        if pos < 0 or pos >= len(lines):
            continue
        raw = _clean_schedule_text(lines[pos])
        if not raw:
            continue
        pieces = [seg.strip(" ·|-") for seg in re.split(r"\s*[·|]\s*", raw) if seg.strip(" ·|-")]
        for piece in pieces or [raw]:
            venue = _venue_candidate(piece, title=title, series_name=series_name)
            if not venue:
                continue
            low = venue.casefold()
            score = 20 if pos != index else 8
            if any(low.endswith(hint) for hint in _VENUE_HINTS):
                score += 4
            if any(name == low for name in _VENUE_EXACTISH):
                score += 4
            candidates.append((score, venue))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1].casefold()))
    return candidates[0][1]


def _official_page_schedule(config: dict[str, Any]) -> list[dict[str, Any]]:
    url = str(config.get("schedule_url") or "").strip()
    if not url:
        return []
    try:
        text = _reader_markdown(url)
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    month_map = {m.lower(): i for i, m in enumerate(
        ("January","February","March","April","May","June","July","August","September","October","November","December"), 1
    )}
    short = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"(?P<m>January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s*(?P<y>20\d{2}))?",
        re.IGNORECASE,
    )

    for i, line in enumerate(lines):
        for match in pattern.finditer(line):
            token = match.group("m").lower().rstrip(".")
            month = month_map.get(token) or short.get(token[:4]) or short.get(token[:3])
            if not month:
                continue
            try:
                # Noon UTC is deliberate: generic official pages usually give a DATE,
                # not a start time. Midnight UTC shifted US dates to the previous day.
                dt = datetime(int(match.group("y") or now.year), month, int(match.group("d")), 12, 0, tzinfo=timezone.utc)
            except Exception:
                continue
            # Keep the entire configured season so Race Center can build a real
            # season-wide track/event graph instead of only today's remaining venues.
            if dt.year != SEASON:
                continue
            title = _event_title(lines, i, match, config)
            venue = _schedule_venue(lines, i, title, config)
            key = (dt.date().isoformat(), title.casefold())
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "name": title,
                "start": dt.isoformat(),
                "date_only": True,
                # Generic page text is not reliable enough to claim LIVE NOW.
                "state": "pre" if dt.date() >= now.date() else "post",
                "completed": dt.date() < now.date(),
                "broadcast": None,
                "venue": venue,
                "location": None,
                "source_url": url,
            })

    found.sort(key=lambda item: item.get("start") or "")
    # Preserve the full season. Truncating to the first 20 events hid late-season
    # races from Live + Next for high-event-count series.
    return found


def _floracing_broadcast_events() -> list[dict[str, Any]]:
    """Supplement Race Center with FloRacing's public race-night schedule."""
    now = datetime.now(timezone.utc)
    collected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_event(*, day, title: str, event_url: str, location: str | None, hour: int, minute: int):
        title = " ".join(str(title or "").split()).strip()
        if not title or title.casefold() in {"floracing 24/7", "pbr ridepass"}:
            return
        start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=timezone.utc)
        delta = now - start
        state = "pre" if delta < timedelta(0) else ("in" if delta <= timedelta(hours=6) else "post")
        if start < now - timedelta(hours=8) or start > now + timedelta(hours=30):
            return
        key = (start.isoformat(), title.casefold())
        if key in seen:
            return
        seen.add(key)
        collected.append({
            "name": title,
            "start": start.isoformat(),
            "date_only": False,
            "state": state,
            "completed": state == "post",
            "broadcast": "FloRacing",
            "venue": location,
            "location": location,
            "source_url": event_url,
            "event_url": event_url,
        })

    # Current UTC day plus the previous UTC day catches US evening events that
    # are still running after midnight UTC.
    for day_offset in (-1, 0):
        day = (now + timedelta(days=day_offset)).date()
        schedule_url = f"https://www.floracing.com/events?date={day.isoformat()}"
        parsed_direct = False

        try:
            with httpx.Client(timeout=7.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (compatible; PitmarkRaceCenter/1.0; +https://pitmarkracing.com)",
                "Accept-Language": "en-US,en;q=0.9",
            }) as client:
                response = client.get(schedule_url)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = str(anchor.get("href") or "")
                if "/events/" not in href and "/live/" not in href:
                    continue
                label = " ".join(anchor.get_text(" ", strip=True).split())
                if not label or "UTC" in label.upper():
                    continue
                # Flo also links the venue/location in each schedule row. Keep the
                # event-title link and ignore obvious location-only anchors.
                if " · " in label and re.search(r",\s*[A-Z]{2}(?:\b|$)", label):
                    continue

                container = anchor
                container_text = label
                for _ in range(6):
                    parent = getattr(container, "parent", None)
                    if parent is None:
                        break
                    container = parent
                    container_text = " ".join(container.get_text(" ", strip=True).split())
                    if re.search(r"\b\d{1,2}:\d{2}\s*[AP]M\s+UTC\b", container_text, re.IGNORECASE):
                        break

                time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*([AP]M)\s+UTC\b", container_text, re.IGNORECASE)
                if not time_match:
                    continue
                hour = int(time_match.group(1)) % 12
                if time_match.group(3).upper() == "PM":
                    hour += 12
                minute = int(time_match.group(2))

                if len(label) < 4:
                    continue
                event_url = urljoin(schedule_url, href)
                add_event(day=day, title=label, event_url=event_url, location=None, hour=hour, minute=minute)
                parsed_direct = True
        except Exception:
            parsed_direct = False

        if parsed_direct:
            continue

        # Reader fallback: useful when Flo changes HTML, but not required for the
        # live board to function because it can be rate-limited independently.
        try:
            text = _reader_markdown(schedule_url)
        except Exception:
            continue

        for raw_line in text.splitlines():
            if "UTC" not in raw_line or "|" not in raw_line:
                continue
            time_match = re.search(r"\b(\d{1,2}):(\d{2})\s*([AP]M)\s+UTC\b", raw_line, re.IGNORECASE)
            if not time_match:
                continue
            links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", raw_line)
            candidates = [
                (label.strip(), url.strip())
                for label, url in links
                if "UTC" not in label.upper() and label.strip()
            ]
            if not candidates:
                continue
            title, event_url = candidates[0]
            location = candidates[1][0] if len(candidates) > 1 else None
            hour = int(time_match.group(1)) % 12
            if time_match.group(3).upper() == "PM":
                hour += 12
            add_event(
                day=day,
                title=title,
                event_url=event_url or schedule_url,
                location=location,
                hour=hour,
                minute=int(time_match.group(2)),
            )

    collected.sort(key=lambda item: item.get("start") or "")
    return collected

def _floracing_broadcast_summaries() -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for event in _floracing_broadcast_events():
        state = "live" if event.get("state") == "in" else ("next" if event.get("state") == "pre" else "recent")
        safe_key = re.sub(r"[^a-z0-9]+", "-", str(event.get("name") or "").casefold()).strip("-")[:80] or "event"
        summaries.append({
            "state": state,
            "event": event,
            "events": [event],
            "schedule_url": "https://www.floracing.com/events",
            "watch_name": "FloRacing",
            "watch_url": event.get("event_url") or "https://www.floracing.com/events",
            "logo_url": None,
            "logo_source_url": "https://www.floracing.com/events",
            "series_key": f"floracing-{safe_key}",
            "series_name": "FloRacing",
            "group": "Live Broadcast",
            "source_kind": "broadcast_schedule",
        })
    return summaries


def _event_summary(events: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    live = next((e for e in events if e.get("state") == "in"), None)
    upcoming: list[tuple[datetime, dict[str, Any]]] = []
    recent: list[tuple[datetime, dict[str, Any]]] = []
    for event in events:
        start = event.get("start")
        if not start:
            continue
        try:
            dt = datetime.fromisoformat(start)
        except Exception:
            continue
        if event.get("state") == "pre" and (
            (event.get("date_only") and dt.date() >= now.date())
            or (not event.get("date_only") and dt >= now - timedelta(minutes=10))
        ):
            upcoming.append((dt, event))
        elif event.get("state") == "post":
            recent.append((dt, event))
    upcoming.sort(key=lambda item: item[0])
    recent.sort(key=lambda item: item[0], reverse=True)

    chosen = live or (upcoming[0][1] if upcoming else (recent[0][1] if recent else None))
    state = "live" if live else ("next" if upcoming else ("recent" if recent else "schedule"))
    return {
        "state": state,
        "event": chosen,
        "events": events,
        "schedule_url": config.get("schedule_url"),
        "watch_name": (chosen or {}).get("broadcast") or config.get("watch_name"),
        "watch_url": config.get("watch_url"),
        "logo_url": config.get("logo_url"),
        "logo_source_url": config.get("logo_source_url"),
    }


def _build_one(key: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        if config.get("espn_league"):
            events = _espn_schedule(config)
        elif config.get("provider") == "f1":
            events = _f1_schedule(config)
        else:
            events = _official_page_schedule(config)
    except Exception:
        # Structured feeds can block datacenter traffic. Fall back to the
        # official schedule page for date/upcoming info, but never invent LIVE.
        events = _official_page_schedule(config)

    summary = _event_summary(events, config)
    if not summary.get("logo_url"):
        logo_url, logo_source_url = _discover_official_event_logo(key, config)
        summary["logo_url"] = logo_url
        summary["logo_source_url"] = logo_source_url
    summary.update({"series_key": key, "series_name": config["name"], "group": config["group"]})
    return key, summary


def _build_one_static(key: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return key, {"state":"schedule","event":None,"events":[],"schedule_url":config.get("schedule_url"),"watch_name":config.get("watch_name"),"watch_url":config.get("watch_url"),"logo_url":config.get("logo_url"),"logo_source_url":config.get("logo_source_url"),"series_key":key,"series_name":config["name"],"group":config["group"]}


def get_racing_event_hub(force: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with _cache_lock:
        cached = _cache.get("value")
        if not force and cached:
            return cached
    if not force:
        by_series = {}
        for key, cfg in SERIES_EVENT_CONFIG.items():
            _, item = _build_one_static(key, cfg)
            by_series[key] = item
        value = {"generated_at":now.isoformat(),"live":[],"next":[],"series":by_series,"catalog":list(by_series.values()),"warming":True}
        with _cache_lock:
            _cache["at"]=now
            _cache["value"]=value
        return value

    by_series: dict[str, Any] = {}
    configs = list(SERIES_EVENT_CONFIG.items())
    workers = max(2, min(8, len(configs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(_build_one, key, cfg): (key, cfg)
            for key, cfg in configs
        }
        for future in as_completed(future_map):
            key, cfg = future_map[future]
            try:
                resolved_key, item = future.result()
                by_series[resolved_key] = item
            except Exception:
                # A single blocked schedule source must never hold the entire
                # race-weekend board hostage.
                _, item = _build_one_static(key, cfg)
                by_series[key] = item

    broadcast_summaries = _floracing_broadcast_summaries()
    live = [item for item in by_series.values() if item.get("state") == "live"]
    live.extend(item for item in broadcast_summaries if item.get("state") == "live")

    next_items = [
        item for item in by_series.values()
        if item.get("state") == "next" and item.get("event", {}).get("start")
    ]
    next_items.extend(
        item for item in broadcast_summaries
        if item.get("state") == "next" and item.get("event", {}).get("start")
    )
    next_items.sort(key=lambda item: item["event"]["start"])

    value = {
        "generated_at": now.isoformat(),
        "live": live,
        "next": next_items[:48],
        "series": by_series,
        "catalog": list(by_series.values()),
        "warming": False,
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = value
    return value
