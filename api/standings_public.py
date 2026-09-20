from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from services.racing_standings import get_standings_hub
from utils.config import settings

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent


def _asset(name: str, media_type: str) -> Response:
    return Response(
        (ASSET_DIR / name).read_text(encoding="utf-8"),
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/standings", response_class=HTMLResponse, include_in_schema=False)
def public_standings_home():
    html = (ASSET_DIR / "standings_public.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("{{PITMARK_VERSION}}", settings.app_version),
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/standings.css", include_in_schema=False)
def public_standings_css():
    return _asset("standings_public.css", "text/css")


@router.get("/standings.js", include_in_schema=False)
def public_standings_js():
    return _asset("standings_public.js", "application/javascript")


@router.get("/api/public/standings", include_in_schema=False)
def public_standings_data():
    payload = get_standings_hub(force=False)
    safe_series = []
    for series in payload.get("series") or []:
        safe_series.append(
            {
                "series_key": series.get("series_key"),
                "series_name": series.get("series_name"),
                "short_name": series.get("short_name"),
                "group": series.get("group"),
                "season": series.get("season"),
                "official_url": series.get("official_url"),
                "source_name": series.get("source_name"),
                "fetched_at": series.get("fetched_at"),
                "status": series.get("status"),
                "stale": bool(series.get("stale")),
                "entries": series.get("entries") or [],
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
