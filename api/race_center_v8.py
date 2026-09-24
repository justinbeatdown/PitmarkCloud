from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from services import race_center_accounts
from services.racing_culture import get_racing_culture_feed
from utils.config import settings

router = APIRouter()
_HERE = Path(__file__).resolve().parent


@router.get("/api/public/race-center/stories", include_in_schema=False)
def race_center_stories(limit: int = 12):
    return get_racing_culture_feed(limit=limit)


@router.get("/api/public/race-center/community-search", include_in_schema=False)
def race_center_community_search(request: Request, q: str = "", limit: int = 24):
    viewer = race_center_accounts.account_from_request(request)
    return {
        "query": q,
        "people": race_center_accounts.search_people(
            q,
            viewer_user_id=viewer.id if viewer else None,
            limit=limit,
        ),
    }


@router.get("/race-center/community", response_class=HTMLResponse, include_in_schema=False)
def race_center_community_page():
    html = (_HERE / "standings_public.html").read_text(encoding="utf-8")
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
    html = html.replace("{{RACE_CENTER_VIEW}}", "community")
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/race-center-v8.js", include_in_schema=False)
def race_center_v8_js():
    return Response(
        (_HERE / "race_center_v8.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/race-center-v8.css", include_in_schema=False)
def race_center_v8_css():
    return Response(
        (_HERE / "race_center_v8.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
