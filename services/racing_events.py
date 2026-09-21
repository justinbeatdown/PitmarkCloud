from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Any

import httpx

USER_AGENT = "PitmarkRaceCenter/1.0 (+https://pitmarkracing.com)"
SEASON = 2026

# Schedule/watch discovery is intentionally separate from standings. This lets
# Pitmark cover support series that do not expose a usable public standings feed.
SERIES_EVENT_CONFIG: dict[str, dict[str, Any]] = {
    "nascar-cup": {"name":"NASCAR Cup Series","group":"NASCAR","espn_league":"nascar-premier","schedule_url":"https://www.nascar.com/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-oreilly": {"name":"NASCAR O'Reilly Auto Parts Series","group":"NASCAR","espn_league":"nascar-secondary","schedule_url":"https://www.nascar.com/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-truck": {"name":"NASCAR CRAFTSMAN Truck Series","group":"NASCAR","espn_league":"nascar-truck","schedule_url":"https://www.nascar.com/schedule/","watch_name":"NASCAR TV Guide","watch_url":"https://www.nascar.com/tv-schedule/"},
    "nascar-whelen-modified": {"name":"NASCAR Whelen Modified Tour","group":"NASCAR","schedule_url":"https://www.nascar.com/whelen-modified-tour/","watch_name":"NASCAR / FloRacing","watch_url":"https://www.nascar.com/tv-schedule/"},
    "arca-menards": {"name":"ARCA Menards Series","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/"},
    "arca-east": {"name":"ARCA Menards Series East","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/"},
    "arca-west": {"name":"ARCA Menards Series West","group":"NASCAR","schedule_url":"https://www.arcaracing.com/schedule/","watch_name":"ARCA Broadcast Info","watch_url":"https://www.arcaracing.com/"},

    "world-of-outlaws-sprint": {"name":"World of Outlaws Sprint Car Series","group":"Dirt","schedule_url":"https://worldofoutlaws.com/sprintcars/schedule/","watch_name":"DIRTVision","watch_url":"https://www.dirtvision.com/"},
    "world-of-outlaws-late-models": {"name":"World of Outlaws Late Model Series","group":"Dirt","schedule_url":"https://worldofoutlaws.com/latemodels/schedule/","watch_name":"DIRTVision","watch_url":"https://www.dirtvision.com/"},
    "lucas-oil-late-models": {"name":"Lucas Oil Late Model Dirt Series","group":"Dirt","schedule_url":"https://www.lucasdirt.com/schedule/","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "high-limit-sprint": {"name":"High Limit Racing","group":"Dirt","schedule_url":"https://www.highlimitracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "usac-national-sprint": {"name":"USAC AMSOIL National Sprint","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "usac-national-midget": {"name":"USAC NOS Energy Drink National Midget","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "usac-silver-crown": {"name":"USAC Silver Crown","group":"Dirt / Pavement","schedule_url":"https://www.usacracing.com/schedule","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},

    "cars-tour-lmsc": {"name":"zMAX CARS Tour — Late Model Stock","group":"Short Track","schedule_url":"https://www.carsracingtour.com/schedule/","watch_name":"FloRacing","watch_url":"https://www.floracing.com/"},
    "asa-stars": {"name":"ASA STARS National Tour","group":"Short Track","schedule_url":"https://starsnationaltour.com/schedule/","watch_name":"Official Broadcast Info","watch_url":"https://starsnationaltour.com/"},
    "smart-modified": {"name":"SMART Modified Tour","group":"Short Track","schedule_url":"https://smartmodifiedtour.com/schedule","watch_name":"Official Broadcast Info","watch_url":"https://smartmodifiedtour.com/"},

    "nhra-top-fuel": {"name":"NHRA Top Fuel","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-funny-car": {"name":"NHRA Funny Car","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-pro-stock": {"name":"NHRA Pro Stock","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},
    "nhra-pro-stock-motorcycle": {"name":"NHRA Pro Stock Motorcycle","group":"Drag Racing","schedule_url":"https://www.nhra.com/schedule/2026","watch_name":"NHRA TV Schedule","watch_url":"https://www.nhra.com/tv-schedule"},

    "f1": {"name":"Formula 1","group":"Open Wheel","provider":"f1","schedule_url":"https://www.formula1.com/en/racing/2026","watch_name":"F1 TV","watch_url":"https://f1tv.formula1.com/"},
    "indycar": {"name":"NTT INDYCAR SERIES","group":"Open Wheel","espn_league":"irl","schedule_url":"https://www.indycar.com/Schedule","watch_name":"INDYCAR Ways to Watch","watch_url":"https://www.indycar.com/ways-to-watch"},
    "formula-e": {"name":"ABB FIA Formula E World Championship","group":"Open Wheel","schedule_url":"https://www.fiaformulae.com/en/calendar","watch_name":"Formula E Ways to Watch","watch_url":"https://www.fiaformulae.com/en/ways-to-watch"},

    "imsa-weathertech": {"name":"IMSA WeatherTech SportsCar Championship","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"NBC / Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-michelin-pilot": {"name":"IMSA Michelin Pilot Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-vp-racing": {"name":"IMSA VP Racing SportsCar Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-porsche-carrera-cup": {"name":"Porsche Carrera Cup North America","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-mustang-challenge": {"name":"Mustang Challenge","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-lamborghini-super-trofeo": {"name":"Lamborghini Super Trofeo North America","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"Peacock / IMSA.TV","watch_url":"https://www.imsa.com/tv/"},
    "imsa-mx5-cup": {"name":"Mazda MX-5 Cup","group":"Sports Cars","schedule_url":"https://www.imsa.com/events/","watch_name":"IMSA.TV / YouTube","watch_url":"https://www.imsa.com/tv/"},
    "wec": {"name":"FIA World Endurance Championship","group":"Sports Cars","schedule_url":"https://www.fiawec.com/en/calendar/80","watch_name":"FIA WEC TV","watch_url":"https://fiawec.tv/"},
    "gtwc-america": {"name":"GT World Challenge America","group":"Sports Cars","schedule_url":"https://www.gt-world-challenge-america.com/calendar","watch_name":"GTWorld","watch_url":"https://www.youtube.com/@GTWorld"},
    "trans-am": {"name":"Trans Am Series","group":"Sports Cars","schedule_url":"https://gotransam.com/events/","watch_name":"Trans Am Official Broadcast Info","watch_url":"https://gotransam.com/"},
    "dtm": {"name":"DTM","group":"Touring Cars","schedule_url":"https://www.dtm.com/en/events","watch_name":"DTM Official TV Guide","watch_url":"https://www.dtm.com/en/tv"},
    "btcc": {"name":"British Touring Car Championship","group":"Touring Cars","schedule_url":"https://btcc.net/calendar/","watch_name":"BTCC Watch Live","watch_url":"https://btcc.net/watch-live/"},

    "supercars": {"name":"Repco Supercars Championship","group":"Touring Cars","schedule_url":"https://www.supercars.com/calendar","watch_name":"Supercars Ways to Watch","watch_url":"https://www.supercars.com/ways-to-watch"},

    "motogp": {"name":"MotoGP World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "moto2": {"name":"Moto2 World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "moto3": {"name":"Moto3 World Championship","group":"Motorcycles","schedule_url":"https://www.motogp.com/en/calendar","watch_name":"MotoGP VideoPass","watch_url":"https://www.motogp.com/en/videopass"},
    "worldsbk": {"name":"FIM Superbike World Championship","group":"Motorcycles","schedule_url":"https://www.worldsbk.com/en/calendar","watch_name":"WorldSBK VideoPass","watch_url":"https://www.worldsbk.com/en/videos"},
}

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}


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
        broadcasts: list[str] = []
        for raw in competition.get("broadcasts") or []:
            if isinstance(raw, dict):
                broadcasts.extend(str(x) for x in (raw.get("names") or []) if x)
        out.append({
            "name": event.get("name") or event.get("shortName") or config["name"],
            "start": _iso(event.get("date") or competition.get("date")),
            "state": str(status_type.get("state") or "pre").lower(),
            "completed": bool(status_type.get("completed")),
            "broadcast": " / ".join(dict.fromkeys(broadcasts)) or None,
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
        out.append({
            "name": race.get("raceName") or config["name"],
            "start": start,
            "state": state,
            "completed": completed,
            "broadcast": "F1 TV",
            "source_url": config.get("schedule_url"),
        })
    return out


def _reader_markdown(url: str) -> str:
    target = "https://r.jina.ai/http://" + url.split("://", 1)[-1]
    with httpx.Client(timeout=5.0, follow_redirects=True, headers={"User-Agent": USER_AGENT, "X-Return-Format": "markdown"}) as client:
        response = client.get(target)
        response.raise_for_status()
        return response.text


def _official_page_schedule(config: dict[str, Any]) -> list[dict[str, Any]]:
    url = str(config.get("schedule_url") or "").strip()
    if not url:
        return []
    try:
        text = _reader_markdown(url)
    except Exception:
        return []
    now = datetime.now(timezone.utc)
    month_map = {m.lower(): i for i, m in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"), 1)}
    short = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    found = []
    pattern = re.compile(r"(?P<m>January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(?P<d>\d{1,2})(?:\s*[-–]\s*\d{1,2})?(?:,?\s*(?P<y>20\d{2}))?", re.I)
    for i,line in enumerate(lines):
        for match in pattern.finditer(line):
            token=match.group("m").lower().rstrip(".")
            month=month_map.get(token) or short.get(token[:4]) or short.get(token[:3])
            if not month: continue
            try: dt=datetime(int(match.group("y") or now.year),month,int(match.group("d")),tzinfo=timezone.utc)
            except Exception: continue
            if dt < now-timedelta(days=1) or dt > now+timedelta(days=370): continue
            context=" · ".join(lines[max(0,i-1):min(len(lines),i+2)])[:220]
            live_text=bool(re.search(r"\b(live now|watch live|live)\b",context,re.I)) and dt.date()==now.date()
            found.append((dt,context,live_text))
    found.sort(key=lambda x:x[0])
    return [{"name":ctx or config.get("name"),"start":dt.isoformat(),"state":"in" if live else ("pre" if dt.date()>=now.date() else "post"),"completed":dt.date()<now.date(),"broadcast":None,"source_url":url} for dt,ctx,live in found[:20]]


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
        if event.get("state") == "pre" and dt >= now - timedelta(minutes=10):
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
        "schedule_url": config.get("schedule_url"),
        "watch_name": (chosen or {}).get("broadcast") or config.get("watch_name"),
        "watch_url": config.get("watch_url"),
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
        events = []

    summary = _event_summary(events, config)
    summary.update({"series_key": key, "series_name": config["name"], "group": config["group"]})
    return key, summary


def _build_one_static(key: str, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return key, {"state":"schedule","event":None,"schedule_url":config.get("schedule_url"),"watch_name":config.get("watch_name"),"watch_url":config.get("watch_url"),"series_key":key,"series_name":config["name"],"group":config["group"]}


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
    dynamic = [(key, cfg) for key, cfg in SERIES_EVENT_CONFIG.items() if cfg.get("espn_league") or cfg.get("provider")]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_build_one, key, cfg) for key, cfg in dynamic]
        for future in as_completed(futures):
            try:
                key, item = future.result()
                by_series[key] = item
            except Exception:
                pass

    for key, cfg in SERIES_EVENT_CONFIG.items():
        if key in by_series:
            continue
        _, item = _build_one(key, cfg)
        by_series[key] = item

    live = [item for item in by_series.values() if item.get("state") == "live"]
    next_items = [
        item for item in by_series.values()
        if item.get("state") == "next" and item.get("event", {}).get("start")
    ]
    next_items.sort(key=lambda item: item["event"]["start"])

    value = {
        "generated_at": now.isoformat(),
        "live": live,
        "next": next_items[:12],
        "series": by_series,
        "catalog": list(by_series.values()),
        "warming": False,
    }
    with _cache_lock:
        _cache["at"] = now
        _cache["value"] = value
    return value
