from __future__ import annotations

from pathlib import Path
import base64
import threading
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from services.racing_standings import SERIES as STANDINGS_SERIES, get_series_logo_info, get_series_roster, get_standings_snapshot_hub
from services.racing_events import get_racing_event_hub
from services import race_center_accounts
from utils.config import settings
from utils.security import enforce_rate_limit

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
LOGO_MAX_BYTES = 2 * 1024 * 1024
_logo_cache_lock = threading.Lock()
_logo_cache: dict[str, tuple[float, bytes, str]] = {}

ARCA_LOGO_WEBP_B64 = "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"


def _fallback_series_logo(series_key: str) -> Response:
    config = next((item for item in STANDINGS_SERIES if item.get("key") == series_key), None)
    label = str((config or {}).get("short_name") or (config or {}).get("name") or series_key.replace("-", " ")).strip()
    safe = (
        label.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
    # Last-resort brand tile so a broken upstream image can never leave a
    # blank hole in the public hub. Official/discovered logos are always tried first.
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="120" viewBox="0 0 360 120">
<rect width="360" height="120" rx="18" fill="#111315"/>
<rect x="4" y="4" width="352" height="112" rx="15" fill="none" stroke="#34383d" stroke-width="2"/>
<text x="180" y="68" fill="#f4f1eb" font-family="Arial,Helvetica,sans-serif" font-size="28" font-weight="800" text-anchor="middle">{safe}</text>
</svg>"""
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


def _public_payload() -> dict:
    """Serve durable saved snapshots immediately; background sync updates them."""
    return get_standings_snapshot_hub()


def _asset(name: str, media_type: str) -> Response:
    return Response(
        (ASSET_DIR / name).read_text(encoding="utf-8"),
        media_type=media_type,
        headers={"Cache-Control": "no-store, max-age=0"},
    )


class RaceAccountCredentials(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(default="", max_length=80)


class RaceFollowChange(BaseModel):
    kind: str = Field(min_length=3, max_length=20)
    key: str = Field(min_length=1, max_length=220)
    label: str = Field(default="", max_length=160)
    series_key: str = Field(default="", max_length=120)


def _race_account_or_401(request: Request) -> race_center_accounts.RaceCenterAccount:
    account = race_center_accounts.account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Race Center account required.")
    return account


def _race_session_response(payload: dict, account: race_center_accounts.RaceCenterAccount) -> JSONResponse:
    response = JSONResponse(payload)
    response.set_cookie(
        race_center_accounts.SESSION_COOKIE,
        race_center_accounts.issue_session(account),
        max_age=race_center_accounts.SESSION_TTL_SECONDS,
        httponly=True,
        secure=str(settings.environment or "").lower() not in {"dev", "development", "local"},
        samesite="lax",
        path="/",
    )
    return response


@router.get("/api/public/race-center/account", include_in_schema=False)
def race_center_account(request: Request):
    account = race_center_accounts.account_from_request(request)
    payload = race_center_accounts.serialize_account(account)
    payload["follows"] = race_center_accounts.list_follows(account.id) if account else []
    return payload


@router.post("/api/public/race-center/account/signup", include_in_schema=False)
def race_center_signup(request: Request, body: RaceAccountCredentials):
    enforce_rate_limit(request, "race-center-signup", 8, 300)
    try:
        account = race_center_accounts.create_account(body.email, body.password, body.display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _race_session_response(
        {
            **race_center_accounts.serialize_account(account),
            "follows": [],
            "message": "Welcome to My Race Center.",
        },
        account,
    )


@router.post("/api/public/race-center/account/login", include_in_schema=False)
def race_center_login(request: Request, body: RaceAccountCredentials):
    enforce_rate_limit(request, "race-center-login", 15, 300)
    account = race_center_accounts.authenticate(body.email, body.password)
    if not account:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return _race_session_response(
        {
            **race_center_accounts.serialize_account(account),
            "follows": race_center_accounts.list_follows(account.id),
        },
        account,
    )


@router.post("/api/public/race-center/account/logout", include_in_schema=False)
def race_center_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(race_center_accounts.SESSION_COOKIE, path="/")
    return response


@router.put("/api/public/race-center/follows", include_in_schema=False)
def race_center_follow(request: Request, body: RaceFollowChange):
    account = _race_account_or_401(request)
    try:
        race_center_accounts.set_follow(
            account.id,
            kind=body.kind,
            key=body.key,
            label=body.label,
            series_key=body.series_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "follows": race_center_accounts.list_follows(account.id)}


@router.delete("/api/public/race-center/follows", include_in_schema=False)
def race_center_unfollow(request: Request, body: RaceFollowChange):
    account = _race_account_or_401(request)
    race_center_accounts.remove_follow(account.id, kind=body.kind, key=body.key)
    return {"ok": True, "follows": race_center_accounts.list_follows(account.id)}


@router.get("/race-center", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/standings", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/schedules", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/live", response_class=HTMLResponse, include_in_schema=False)
@router.get("/standings", response_class=HTMLResponse, include_in_schema=False)
def public_standings_home(request: Request):
    html = (ASSET_DIR / "standings_public.html").read_text(encoding="utf-8")
    path = request.url.path.rstrip("/").lower()
    view = (
        "standings" if path == "/standings" or path.endswith("/standings")
        else "schedules" if path.endswith("/schedules")
        else "live" if path.endswith("/live")
        else "hub"
    )
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
    html = html.replace("{{RACE_CENTER_VIEW}}", view)
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get("/standings.css", include_in_schema=False)
def public_standings_css():
    return _asset("standings_public.css", "text/css")


@router.get("/standings.js", include_in_schema=False)
def public_standings_js():
    return _asset("standings_public.js", "application/javascript")


@router.get("/race-center-assets/arca.webp", include_in_schema=False)
def public_arca_logo():
    return Response(
        base64.b64decode(ARCA_LOGO_WEBP_B64),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/standings-logo/{series_key}", include_in_schema=False)
def public_standings_logo(series_key: str):
    info = get_series_logo_info(series_key)
    if not info:
        return _fallback_series_logo(series_key)

    remote_url = info["url"]
    now = time.monotonic()
    with _logo_cache_lock:
        cached = _logo_cache.get(remote_url)
        if cached and now - cached[0] <= 24 * 3600:
            return Response(cached[1], media_type=cached[2])

    headers = {
        "User-Agent": "PitmarkRacingStandings/1.0 (+https://pitmarkracing.com)",
        "Accept": "image/avif,image/webp,image/png,image/svg+xml,image/jpeg,*/*;q=0.5",
        "Referer": info["source_url"],
    }
    response = None
    attempts = (
        headers,
        {
            "User-Agent": headers["User-Agent"],
            "Accept": headers["Accept"],
        },
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/144 Safari/537.36",
            "Accept": headers["Accept"],
        },
    )
    for attempt_headers in attempts:
        try:
            with httpx.Client(timeout=14.0, follow_redirects=True, headers=attempt_headers) as client:
                candidate = client.get(remote_url)
                candidate.raise_for_status()
                response = candidate
                break
        except Exception:
            continue
    if response is None:
        return _fallback_series_logo(series_key)

    content = response.content
    media_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/png", "image/jpeg", "image/webp", "image/gif",
        "image/svg+xml", "image/avif",
    }
    if media_type not in allowed or not content or len(content) > LOGO_MAX_BYTES:
        return _fallback_series_logo(series_key)

    with _logo_cache_lock:
        _logo_cache[remote_url] = (now, content, media_type)
        if len(_logo_cache) > 64:
            oldest = min(_logo_cache.items(), key=lambda item: item[1][0])[0]
            _logo_cache.pop(oldest, None)
    return Response(content, media_type=media_type)


@router.get("/api/public/standings", include_in_schema=False)
def public_standings_data():
    payload = get_standings_snapshot_hub()
    event_hub = get_racing_event_hub()
    event_series = event_hub.get("series") or {}
    safe_series = []
    for series in payload.get("series") or []:
        identity_verified = bool(series.get("metadata_verified"))
        safe_entries = []
        for raw_entry in series.get("entries") or []:
            entry = dict(raw_entry)
            if not identity_verified:
                entry["number"] = None
                entry["team"] = None
                entry["manufacturer"] = None
            safe_entries.append(entry)
        series_key = str(series.get("series_key") or "")
        logo_info = get_series_logo_info(series_key)
        event_info = event_series.get(series_key) or {}
        safe_series.append(
            {
                "series_key": series.get("series_key"),
                "series_name": series.get("series_name"),
                "short_name": series.get("short_name"),
                "group": series.get("group"),
                "season": series.get("season"),
                "official_url": series.get("official_url"),
                "source_name": series.get("source_name"),
                "metadata_source_url": series.get("metadata_source_url") if identity_verified else None,
                "metadata_verified": identity_verified,
                "series_logo": f"/standings-logo/{series_key}",
                "series_logo_direct": "/race-center-assets/arca.webp" if series_key == "arca-menards" else (logo_info.get("url") if logo_info else None),
                "series_logo_source_url": logo_info.get("source_url") if logo_info else None,
                "fetched_at": series.get("fetched_at"),
                "status": series.get("status"),
                "stale": bool(series.get("stale")),
                "event_state": event_info.get("state"),
                "current_event": event_info.get("event"),
                "schedule_url": event_info.get("schedule_url"),
                "watch_name": event_info.get("watch_name"),
                "watch_url": event_info.get("watch_url"),
                "entries": safe_entries,
                "roster": get_series_roster(
                    series_key,
                    safe_entries,
                    season=int(series.get("season") or payload.get("season") or 2026),
                ),
            }
        )
    return Response(
        __import__("json").dumps(
            {
                "season": payload.get("season"),
                "generated_at": payload.get("generated_at"),
                "summary": {
                    **(payload.get("summary") or {}),
                    "events_live": len(event_hub.get("live") or []),
                    "schedule_series_total": len(event_hub.get("catalog") or []),
                },
                "events": {
                    "generated_at": event_hub.get("generated_at"),
                    "live": event_hub.get("live") or [],
                    "next": event_hub.get("next") or [],
                    "catalog": event_hub.get("catalog") or [],
                },
                "series": safe_series,
            },
            ensure_ascii=False,
            default=str,
        ),
        media_type="application/json",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
