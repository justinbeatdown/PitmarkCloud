from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from services import race_center_accounts
from services.racing_culture import get_racing_culture_feed, get_racing_culture_story
from utils.config import settings

router = APIRouter()
_HERE = Path(__file__).resolve().parent


@router.get("/api/public/race-center/stories", include_in_schema=False)
def race_center_stories(limit: int = 12):
    payload = get_racing_culture_feed(limit=limit)
    return {
        **payload,
        "stories": [
            {key: value for key, value in story.items() if key != "content_html"}
            for story in payload.get("stories") or []
        ],
    }


@router.get("/api/public/race-center/story/{story_key}", include_in_schema=False)
def race_center_story(story_key: str):
    story = get_racing_culture_story(story_key)
    if not story:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Race Center story not found.")
    return story


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


def _race_center_shell(view: str) -> str:
    html = (_HERE / "standings_public.html").read_text(encoding="utf-8")
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
    return html.replace("{{RACE_CENTER_VIEW}}", view)


@router.get("/race-center/community", response_class=HTMLResponse, include_in_schema=False)
def race_center_community_page():
    return HTMLResponse(
        _race_center_shell("community"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/race-center/story/{story_key}", response_class=HTMLResponse, include_in_schema=False)
def race_center_story_page(story_key: str):
    return HTMLResponse(
        _race_center_shell("story"),
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


@router.get("/race-center-v8-social.js", include_in_schema=False)
def race_center_v8_social_js():
    return Response(
        (_HERE / "race_center_v8_social.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
