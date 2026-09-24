from __future__ import annotations

from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from services import race_center_accounts
from services import race_center_owner_hub
from services import race_center_entities
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



class OwnerHubScheduleChange(BaseModel):
    title: str = Field(default="", max_length=220)
    start_at: str = Field(default="", max_length=80)
    venue: str = Field(default="", max_length=220)
    location: str = Field(default="", max_length=220)
    class_name: str = Field(default="", max_length=160)
    event_url: str = Field(default="", max_length=4000)
    status: str = Field(default="scheduled", max_length=30)
    notes: str = Field(default="", max_length=4000)
    flyer_media_id: int | None = None


class OwnerHubUpdateCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1200)
    media_id: int | None = None


class OwnerHubSponsor(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    website_url: str = Field(default="", max_length=4000)
    logo_url: str = Field(default="", max_length=4000)
    description: str = Field(default="", max_length=1000)
    sort_order: int = 0


class OwnerHubSponsorList(BaseModel):
    sponsors: list[OwnerHubSponsor] = Field(default_factory=list, max_length=30)


def _account_or_401(request: Request):
    account = race_center_accounts.account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Race Center account required.")
    return account


@router.get("/api/public/race-center/entity-hub/{entity_type}/{entity_key}", include_in_schema=False)
def race_center_entity_hub(request: Request, entity_type: str, entity_key: str):
    viewer = race_center_accounts.account_from_request(request)
    try:
        return race_center_owner_hub.public_hub(
            entity_type,
            entity_key,
            viewer_user_id=viewer.id if viewer else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/schedule", include_in_schema=False)
def race_center_entity_schedule_create(request: Request, entity_type: str, entity_key: str, body: OwnerHubScheduleChange):
    account = _account_or_401(request)
    try:
        return {"item": race_center_owner_hub.upsert_schedule(account.id, entity_type, entity_key, body.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/schedule/{item_id}", include_in_schema=False)
def race_center_entity_schedule_update(request: Request, entity_type: str, entity_key: str, item_id: int, body: OwnerHubScheduleChange):
    account = _account_or_401(request)
    try:
        return {"item": race_center_owner_hub.upsert_schedule(account.id, entity_type, entity_key, body.model_dump(), item_id=item_id)}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/schedule/{item_id}", include_in_schema=False)
def race_center_entity_schedule_delete(request: Request, entity_type: str, entity_key: str, item_id: int):
    account = _account_or_401(request)
    try:
        return race_center_owner_hub.delete_schedule(account.id, entity_type, entity_key, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/updates", include_in_schema=False)
def race_center_entity_update_create(request: Request, entity_type: str, entity_key: str, body: OwnerHubUpdateCreate):
    account = _account_or_401(request)
    try:
        return race_center_owner_hub.add_update(
            account.id,
            entity_type,
            entity_key,
            body=body.body,
            media_id=body.media_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/sponsors", include_in_schema=False)
def race_center_entity_sponsors_replace(request: Request, entity_type: str, entity_key: str, body: OwnerHubSponsorList):
    account = _account_or_401(request)
    try:
        return {
            "sponsors": race_center_owner_hub.replace_sponsors(
                account.id,
                entity_type,
                entity_key,
                [item.model_dump() for item in body.sponsors],
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/api/public/race-center/entity-hub/{entity_type}/{entity_key}/media", include_in_schema=False)
async def race_center_entity_media_upload(
    request: Request,
    entity_type: str,
    entity_key: str,
    image: UploadFile = File(...),
    media_kind: str = Form(default="photo"),
    title: str = Form(default=""),
    credit: str = Form(default=""),
    alt_text: str = Form(default=""),
):
    account = _account_or_401(request)
    raw = await image.read(3 * 1024 * 1024 + 1)
    if len(raw) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Images must be 3 MB or smaller.")
    try:
        opened = Image.open(BytesIO(raw))
        opened = ImageOps.exif_transpose(opened).convert("RGB")
        if max(opened.size) > 1800:
            opened.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        output = BytesIO()
        opened.save(output, format="WEBP", quality=88, method=6)
        prepared = output.getvalue()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Upload a valid JPG, PNG, or WebP image.") from exc
    try:
        return {
            "media": race_center_owner_hub.add_media(
                account.id,
                entity_type,
                entity_key,
                image_data=prepared,
                content_type="image/webp",
                media_kind=media_kind,
                title=title,
                credit=credit,
                alt_text=alt_text,
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/api/public/race-center/entity-media/{media_id}", include_in_schema=False)
def race_center_entity_media(media_id: int):
    result = race_center_owner_hub.get_media(media_id)
    if not result:
        raise HTTPException(status_code=404, detail="Race Center media not found.")
    body, content_type = result
    return Response(body, media_type=content_type, headers={"Cache-Control": "public, max-age=300"})



@router.get("/api/public/race-center/entity-hub-driver/{series_key}/{driver_name:path}", include_in_schema=False)
def race_center_driver_owner_hub(request: Request, series_key: str, driver_name: str):
    viewer = race_center_accounts.account_from_request(request)
    try:
        return race_center_owner_hub.public_hub(
            "driver",
            race_center_entities.identity_key(driver_name),
            viewer_user_id=viewer.id if viewer else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/public/race-center/entity-hub-driver/{series_key}/{driver_name:path}/schedule", include_in_schema=False)
def race_center_driver_schedule_create(request: Request, series_key: str, driver_name: str, body: OwnerHubScheduleChange):
    account = _account_or_401(request)
    try:
        return {"item": race_center_owner_hub.upsert_schedule(
            account.id, "driver", race_center_entities.identity_key(driver_name), body.model_dump()
        )}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/api/public/race-center/entity-hub-driver/{series_key}/{driver_name:path}/updates", include_in_schema=False)
def race_center_driver_update_create(request: Request, series_key: str, driver_name: str, body: OwnerHubUpdateCreate):
    account = _account_or_401(request)
    try:
        return race_center_owner_hub.add_update(
            account.id,
            "driver",
            race_center_entities.identity_key(driver_name),
            body=body.body,
            media_id=body.media_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/api/public/race-center/entity-hub-driver/{series_key}/{driver_name:path}/sponsors", include_in_schema=False)
def race_center_driver_sponsors_replace(request: Request, series_key: str, driver_name: str, body: OwnerHubSponsorList):
    account = _account_or_401(request)
    try:
        return {"sponsors": race_center_owner_hub.replace_sponsors(
            account.id,
            "driver",
            race_center_entities.identity_key(driver_name),
            [item.model_dump() for item in body.sponsors],
        )}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/api/public/race-center/entity-hub-driver/{series_key}/{driver_name:path}/media", include_in_schema=False)
async def race_center_driver_media_upload(
    request: Request,
    series_key: str,
    driver_name: str,
    image: UploadFile = File(...),
    media_kind: str = Form(default="photo"),
    title: str = Form(default=""),
    credit: str = Form(default=""),
    alt_text: str = Form(default=""),
):
    account = _account_or_401(request)
    raw = await image.read(3 * 1024 * 1024 + 1)
    if len(raw) > 3 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Images must be 3 MB or smaller.")
    try:
        opened = Image.open(BytesIO(raw))
        opened = ImageOps.exif_transpose(opened).convert("RGB")
        if max(opened.size) > 1800:
            opened.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
        output = BytesIO()
        opened.save(output, format="WEBP", quality=88, method=6)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Upload a valid JPG, PNG, or WebP image.") from exc
    try:
        return {"media": race_center_owner_hub.add_media(
            account.id,
            "driver",
            race_center_entities.identity_key(driver_name),
            image_data=output.getvalue(),
            content_type="image/webp",
            media_kind=media_kind,
            title=title,
            credit=credit,
            alt_text=alt_text,
        )}
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/race-center-owner-hub.js", include_in_schema=False)
def race_center_owner_hub_js():
    return Response(
        (_HERE / "race_center_owner_hub.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
