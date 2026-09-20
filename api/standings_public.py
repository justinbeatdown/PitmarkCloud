from __future__ import annotations

from pathlib import Path
import threading
import time

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

from services.racing_standings import get_series_logo_info, get_standings_snapshot_hub
from utils.config import settings

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
LOGO_MAX_BYTES = 2 * 1024 * 1024
_logo_cache_lock = threading.Lock()
_logo_cache: dict[str, tuple[float, bytes, str]] = {}


def _public_payload() -> dict:
    """Serve durable saved snapshots immediately; background sync updates them."""
    return get_standings_snapshot_hub()


def _asset(name: str, media_type: str) -> Response:
    return Response(
        (ASSET_DIR / name).read_text(encoding="utf-8"),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/standings", response_class=HTMLResponse, include_in_schema=False)
def public_standings_home():
    html = (ASSET_DIR / "standings_public.html").read_text(encoding="utf-8")
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
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


@router.get("/standings-logo/{series_key}", include_in_schema=False)
def public_standings_logo(series_key: str):
    info = get_series_logo_info(series_key)
    if not info:
        raise HTTPException(status_code=404, detail="Official series logo is not available.")

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
    try:
        with httpx.Client(timeout=14.0, follow_redirects=True, headers=headers) as client:
            response = client.get(remote_url)
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Official series logo could not be retrieved.") from exc

    content = response.content
    media_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    allowed = {
        "image/png", "image/jpeg", "image/webp", "image/gif",
        "image/svg+xml", "image/avif",
    }
    if media_type not in allowed or not content or len(content) > LOGO_MAX_BYTES:
        raise HTTPException(status_code=502, detail="Official series logo response was invalid.")

    with _logo_cache_lock:
        _logo_cache[remote_url] = (now, content, media_type)
        if len(_logo_cache) > 64:
            oldest = min(_logo_cache.items(), key=lambda item: item[1][0])[0]
            _logo_cache.pop(oldest, None)
    return Response(content, media_type=media_type)


@router.get("/api/public/standings", include_in_schema=False)
def public_standings_data():
    payload = get_standings_snapshot_hub()
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
        logo_url = str(series.get("series_logo_url") or "").strip()
        logo_is_http = logo_url.startswith(("https://", "http://"))
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
                "series_logo": (
                    f"/standings-logo/{series.get('series_key')}"
                    if logo_is_http and series.get("series_logo_source_url")
                    else None
                ),
                "series_logo_source_url": series.get("series_logo_source_url"),
                "fetched_at": series.get("fetched_at"),
                "status": series.get("status"),
                "stale": bool(series.get("stale")),
                "entries": safe_entries,
            }
        )
    return Response(
        __import__("json").dumps(
            {
                "season": payload.get("season"),
                "generated_at": payload.get("generated_at"),
                "summary": payload.get("summary") or {},
                "series": safe_series,
            },
            ensure_ascii=False,
            default=str,
        ),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=600"},
    )
