from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import httpx

USER_AGENT = "PitmarkRaceCenter/1.0 (+https://pitmarkracing.com)"
CACHE_SECONDS = 5 * 60
_lock = threading.Lock()
_cache: dict[str, Any] = {"at": None, "value": None}

SERIES_SCHEDULES = (
    {"key":"nascar-cup","name":"NASCAR Cup Series","group":"NASCAR","espn":"nascar-premier","schedule":"https://www.nascar.com/nascar-cup-series/2026/schedule/","watch":"https://www.nascar.com/watch/","watch_label":"NASCAR broadcast guide"},
    {"key":"nascar-oreilly","name":"NASCAR O'Reilly Auto Parts Series","group":"NASCAR","espn":"nascar-secondary","schedule":"https://www.nascar.com/nascar-oreilly-auto-parts-series/2026/schedule/","watch":"https://www.nascar.com/watch/","watch_label":"NASCAR broadcast guide"},
    {"key":"nascar-truck","name":"NASCAR CRAFTSMAN Truck Series","group":"NASCAR","espn":"nascar-truck","schedule":"https://www.nascar.com/nascar-craftsman-truck-series/2026/schedule/","watch":"https://www.nascar.com/watch/","watch_label":"NASCAR broadcast guide"},
    {"key":"nascar-whelen-modified","name":"NASCAR Whelen Modified Tour","group":"Stock Cars","schedule":"https://www.nascar.com/whelen-modified-tour/2026/schedule/","watch":"https://www.floracing.com/","watch_label":"FloRacing / official event guide"},
    {"key":"arca-menards","name":"ARCA Menards Series","group":"Stock Cars","schedule":"https://www.arcaracing.com/schedule/","watch":"https://www.arcaracing.com/","watch_label":"ARCA official broadcast information"},
    {"key":"world-of-outlaws-sprint","name":"World of Outlaws Sprint Car Series","group":"Dirt","schedule":"https://worldofoutlaws.com/sprintcars/schedule/","watch":"https://www.dirtvision.com/","watch_label":"DIRTVision"},
    {"key":"world-of-outlaws-late-models","name":"World of Outlaws Late Model Series","group":"Dirt","schedule":"https://worldofoutlaws.com/latemodels/schedule/","watch":"https://www.dirtvision.com/","watch_label":"DIRTVision"},
    {"key":"lucas-oil-late-models","name":"Lucas Oil Late Model Dirt Series","group":"Dirt","schedule":"https://www.lucasdirt.com/schedule/","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"high-limit-sprint","name":"High Limit Racing","group":"Dirt","schedule":"https://www.highlimitracing.com/schedule","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"usac-national-sprint","name":"USAC National Sprint","group":"Dirt","schedule":"https://www.usacracing.com/schedule-and-results","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"usac-national-midget","name":"USAC National Midget","group":"Dirt","schedule":"https://www.usacracing.com/schedule-and-results","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"usac-silver-crown","name":"USAC Silver Crown","group":"Dirt / Pavement","schedule":"https://www.usacracing.com/schedule-and-results","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"cars-tour-lmsc","name":"zMAX CARS Tour","group":"Short Track","schedule":"https://www.carsracingtour.com/schedule","watch":"https://www.floracing.com/","watch_label":"FloRacing"},
    {"key":"asa-stars","name":"ASA STARS National Tour","group":"Short Track","schedule":"https://starsnationaltour.com/schedule/","watch":"https://starsnationaltour.com/","watch_label":"ASA STARS official broadcast guide"},
    {"key":"smart-modified","name":"SMART Modified Tour","group":"Short Track","schedule":"https://smartmodifiedtour.com/schedule","watch":"https://www.floracing.com/","watch_label":"FloRacing / official event guide"},
    {"key":"nhra","name":"NHRA Mission Foods Drag Racing Series","group":"Drag Racing","schedule":"https://www.nhra.com/schedule/2026","watch":"https://www.nhra.com/tv-schedule","watch_label":"NHRA TV schedule"},
    {"key":"f1","name":"Formula 1","group":"Open Wheel","espn":"f1","schedule":"https://www.formula1.com/en/racing/2026.html","watch":"https://www.formula1.com/en/toolbar-content/f1-tv.html","watch_label":"F1 TV / local broadcaster"},
    {"key":"indycar","name":"NTT INDYCAR SERIES","group":"Open Wheel","espn":"irl","schedule":"https://www.indycar.com/Schedule","watch":"https://www.indycar.com/ways-to-watch","watch_label":"INDYCAR official watch guide"},
    {"key":"formula-e","name":"ABB FIA Formula E World Championship","group":"Open Wheel","schedule":"https://www.fiaformulae.com/en/calendar","watch":"https://www.fiaformulae.com/en/ways-to-watch","watch_label":"Formula E official watch guide"},
    {"key":"imsa-weathertech","name":"IMSA WeatherTech SportsCar Championship","group":"Sports Cars","schedule":"https://www.imsa.com/weathertech/weathertech-2026-schedule/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA TV / NBC-family coverage"},
    {"key":"imsa-michelin-pilot","name":"IMSA Michelin Pilot Challenge","group":"Sports Cars","schedule":"https://www.imsa.com/michelinpilotchallenge/2026-schedule/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA TV / official coverage"},
    {"key":"imsa-vp-racing","name":"IMSA VP Racing SportsCar Challenge","group":"Sports Cars","schedule":"https://www.imsa.com/vpracingsportscarchallenge/2026-schedule/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA TV / official coverage"},
    {"key":"imsa-porsche-carrera-cup","name":"Porsche Carrera Cup North America","group":"Sports Cars","schedule":"https://www.imsa.com/porsche-carrera-cup-north-america/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA / Porsche official coverage"},
    {"key":"imsa-lamborghini-super-trofeo","name":"Lamborghini Super Trofeo North America","group":"Sports Cars","schedule":"https://www.imsa.com/lamborghini-super-trofeo-north-america/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA / Lamborghini official coverage"},
    {"key":"imsa-mx5-cup","name":"Mazda MX-5 Cup","group":"Sports Cars","schedule":"https://www.imsa.com/mazda-mx-5-cup/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA TV / official coverage"},
    {"key":"imsa-mustang-challenge","name":"Mustang Challenge","group":"Sports Cars","schedule":"https://www.imsa.com/mustang-challenge/","watch":"https://www.imsa.com/tvlive/","watch_label":"IMSA TV / official coverage"},
    {"key":"wec","name":"FIA World Endurance Championship","group":"Sports Cars","schedule":"https://www.fiawec.com/en/calendar/80","watch":"https://fiawec.tv/","watch_label":"FIA WEC TV"},
    {"key":"gtwc-america","name":"GT World Challenge America","group":"Sports Cars","schedule":"https://www.gt-world-challenge-america.com/calendar","watch":"https://www.youtube.com/@GTWorld","watch_label":"GTWorld / official broadcast"},
    {"key":"trans-am","name":"Trans Am Series","group":"Sports Cars","schedule":"https://gotransam.com/events/","watch":"https://gotransam.com/","watch_label":"Trans Am official broadcast guide"},
    {"key":"supercars","name":"Repco Supercars Championship","group":"Touring Cars","schedule":"https://www.supercars.com/calendar","watch":"https://www.supercars.com/superview","watch_label":"SuperView / local broadcaster"},
    {"key":"dtm","name":"DTM","group":"Touring Cars","schedule":"https://www.dtm.com/en/events","watch":"https://www.dtm.com/en/tv","watch_label":"DTM official watch guide"},
    {"key":"btcc","name":"British Touring Car Championship","group":"Touring Cars","schedule":"https://btcc.net/calendar/","watch":"https://btcc.net/watch-live/","watch_label":"BTCC official watch guide"},
    {"key":"motogp","name":"MotoGP","group":"Motorcycles","schedule":"https://www.motogp.com/en/calendar","watch":"https://www.motogp.com/en/videopass","watch_label":"MotoGP VideoPass / local broadcaster"},
    {"key":"moto2","name":"Moto2","group":"Motorcycles","schedule":"https://www.motogp.com/en/calendar","watch":"https://www.motogp.com/en/videopass","watch_label":"MotoGP VideoPass / local broadcaster"},
    {"key":"moto3","name":"Moto3","group":"Motorcycles","schedule":"https://www.motogp.com/en/calendar","watch":"https://www.motogp.com/en/videopass","watch_label":"MotoGP VideoPass / local broadcaster"},
)

_MONTHS = {name.lower(): i for i,name in enumerate(("January","February","March","April","May","June","July","August","September","October","November","December"),1)}

def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None

def _espn_event(league: str) -> dict[str, Any] | None:
    url=f"https://site.api.espn.com/apis/site/v2/sports/racing/{league}/scoreboard"
    try:
        with httpx.Client(timeout=8.0,follow_redirects=True,headers={"User-Agent":USER_AGENT}) as client:
            r=client.get(url); r.raise_for_status(); payload=r.json()
    except Exception:
        return None
    now=datetime.now(timezone.utc)
    candidates=[]
    for event in payload.get("events") or []:
        try: start=datetime.fromisoformat(str(event.get("date")).replace("Z","+00:00"))
        except Exception: continue
        comp=(event.get("competitions") or [{}])[0]
        status=(comp.get("status") or event.get("status") or {}).get("type") or {}
        state=str(status.get("state") or "").lower()
        detail=status.get("shortDetail") or status.get("detail") or ""
        end=start+timedelta(hours=6)
        live=state=="in"
        if start-timedelta(hours=12) <= now <= end+timedelta(hours=3) or start>=now-timedelta(hours=2):
            candidates.append((abs((start-now).total_seconds()),{
                "name":event.get("name") or event.get("shortName") or "Race event",
                "start":_iso(start),"live":live,"state":state or ("pre" if start>now else "post"),
                "status_text":detail,"source_url":url,
            }))
    if not candidates:return None
    candidates.sort(key=lambda x:x[0])
    return candidates[0][1]

def _reader_markdown(url: str) -> str:
    parts=url.split("://",1)[-1]
    reader="https://r.jina.ai/http://"+parts
    with httpx.Client(timeout=12.0,follow_redirects=True,headers={"User-Agent":USER_AGENT,"X-Return-Format":"markdown"}) as client:
        r=client.get(reader); r.raise_for_status(); return r.text

def _official_next_event(url: str) -> dict[str, Any] | None:
    try: text=_reader_markdown(url)
    except Exception: return None
    now=datetime.now(timezone.utc)
    year=now.year
    found=[]
    patterns=[
        r"(?P<m>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<d>\d{1,2})(?:\s*[-–]\s*\d{1,2})?(?:,?\s*(?P<y>20\d{2}))?",
        r"(?P<m>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?P<d>\d{1,2})(?:,?\s*(?P<y>20\d{2}))?",
    ]
    lines=[re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]
    for i,line in enumerate(lines):
        for pat in patterns:
            for m in re.finditer(pat,line,re.I):
                mon=m.group("m").lower().rstrip(".")
                mon_map={"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
                month=_MONTHS.get(mon) or mon_map.get(mon[:4]) or mon_map.get(mon[:3])
                if not month: continue
                yy=int(m.group("y") or year); dd=int(m.group("d"))
                try: dt=datetime(yy,month,dd,tzinfo=timezone.utc)
                except Exception: continue
                if dt < now-timedelta(days=1) or dt > now+timedelta(days=370): continue
                context=" · ".join(lines[max(0,i-1):min(len(lines),i+2)])
                if len(context)>240: context=context[:237]+"..."
                found.append((dt,context))
    if not found:return None
    found.sort(key=lambda x:x[0])
    dt,context=found[0]
    return {"name":context or "Official schedule event","start":_iso(dt),"live":False,"state":"today" if dt.date()==now.date() else "pre","status_text":"Today" if dt.date()==now.date() else "Upcoming","source_url":url}

def get_race_schedule() -> dict[str, Any]:
    now=datetime.now(timezone.utc)
    with _lock:
        if _cache["at"] and _cache["value"] and (now-_cache["at"]).total_seconds()<CACHE_SECONDS:
            return _cache["value"]
    items=[]
    def load(cfg):
        event=_espn_event(cfg["espn"]) if cfg.get("espn") else None
        if not event:event=_official_next_event(cfg["schedule"])
        return {**cfg,"event":event}
    from concurrent.futures import ThreadPoolExecutor,as_completed
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(load,cfg) for cfg in SERIES_SCHEDULES]
        for f in as_completed(futures):
            try:items.append(f.result())
            except Exception:pass
    order={cfg["key"]:i for i,cfg in enumerate(SERIES_SCHEDULES)}
    items.sort(key=lambda x:order.get(x["key"],999))
    live=[x for x in items if (x.get("event") or {}).get("live")]
    upcoming=sorted([x for x in items if x.get("event") and not x["event"].get("live")],key=lambda x:x["event"].get("start") or "9999")[:12]
    value={"generated_at":_iso(now),"live":live,"upcoming":upcoming,"series":items,"summary":{"series_total":len(items),"live_now":len(live)}}
    with _lock:_cache["at"]=now;_cache["value"]=value
    return value
