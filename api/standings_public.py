from __future__ import annotations

from pathlib import Path
from io import BytesIO
from datetime import datetime, timedelta, timezone
import base64
import threading
import time

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from services.racing_standings import SERIES as STANDINGS_SERIES, get_driver_identity, get_series_logo_info, get_series_roster, get_standings_snapshot_hub
from services.racing_events import get_racing_event_hub
from services.grassroots_racing import get_grassroots_catalog
from services import race_center_accounts
from services import race_center_entities
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


def _ics_escape(value: object) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _ics_datetime(value: object) -> tuple[str, bool]:
    raw = str(value or "").strip()
    if not raw:
        return "", False
    if len(raw) == 10 and raw[4:5] == "-" and raw[7:8] == "-":
        return raw.replace("-", ""), True
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        return parsed.strftime("%Y%m%dT%H%M%SZ"), False
    except ValueError:
        return "", False


def _race_center_calendar(events: list[dict], *, name: str) -> Response:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Pitmark Racing Co.//Race Center//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape(name)}",
    ]
    seen: set[str] = set()
    for event in events:
        key = str(event.get("key") or "").strip()
        if not key or key in seen:
            continue
        start, all_day = _ics_datetime(event.get("start"))
        if not start:
            continue
        seen.add(key)
        uid = f"{key}@racecenter.pitmarkracing.com"
        title = event.get("name") or event.get("series_name") or "Race Center event"
        location = " · ".join(
            str(value).strip()
            for value in (event.get("venue"), event.get("location"))
            if str(value or "").strip()
        )
        description_parts = [
            str(event.get("series_name") or "").strip(),
            str(event.get("broadcast") or "").strip(),
        ]
        description = " · ".join(value for value in description_parts if value)
        lines.extend(["BEGIN:VEVENT", f"UID:{_ics_escape(uid)}"])
        if all_day:
            lines.append(f"DTSTART;VALUE=DATE:{start}")
        else:
            lines.append(f"DTSTART:{start}")
            try:
                parsed = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
                lines.append(f"DTEND:{(parsed + timedelta(hours=4)).strftime('%Y%m%dT%H%M%SZ')}")
            except ValueError:
                pass
        lines.append(f"SUMMARY:{_ics_escape(title)}")
        if location:
            lines.append(f"LOCATION:{_ics_escape(location)}")
        if description:
            lines.append(f"DESCRIPTION:{_ics_escape(description)}")
        url = event.get("event_url") or event.get("watch_url") or event.get("schedule_url")
        if url:
            lines.append(f"URL:{_ics_escape(url)}")
        lines.extend(["END:VEVENT"])
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines) + "\r\n"
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name.lower()).strip("-") or "race-center"
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Content-Disposition": f'attachment; filename="{safe_name}.ics"',
        },
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


class RaceProfileChange(BaseModel):
    handle: str = Field(min_length=3, max_length=40)
    bio: str = Field(default="", max_length=280)
    favorite_track: str = Field(default="", max_length=120)
    account_type: str = Field(default="fan", min_length=3, max_length=30)


class RacePostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=600)
    series_key: str = Field(default="", max_length=120)
    driver_key: str = Field(default="", max_length=220)


class RaceReactionChange(BaseModel):
    reaction: str = Field(min_length=2, max_length=20)


class RaceCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=280)


class RaceUserFollowChange(BaseModel):
    user_id: int = Field(gt=0)


class RaceDriverClaimCreate(BaseModel):
    driver_key: str = Field(min_length=3, max_length=220)
    driver_name: str = Field(min_length=1, max_length=160)
    series_key: str = Field(default="", max_length=120)
    evidence_url: str = Field(default="", max_length=1200)
    note: str = Field(default="", max_length=1200)


class RaceEntityClaimCreate(BaseModel):
    entity_type: str = Field(min_length=3, max_length=24)
    entity_key: str = Field(min_length=1, max_length=220)
    entity_name: str = Field(default="", max_length=180)
    evidence_url: str = Field(default="", max_length=1200)
    note: str = Field(default="", max_length=1200)


class RaceNotificationPreferences(BaseModel):
    race_day: bool | None = None
    live_now: bool | None = None
    results_posted: bool | None = None
    standings_move: bool | None = None
    schedule_change: bool | None = None
    editorial: bool | None = None


class RaceEntityOwnerProfileChange(BaseModel):
    bio: str = Field(default="", max_length=5000)
    website_url: str = Field(default="", max_length=4000)
    shop_url: str = Field(default="", max_length=4000)
    contact_url: str = Field(default="", max_length=4000)
    hero_url: str = Field(default="", max_length=4000)
    sponsors: list[str] = Field(default_factory=list, max_length=30)


class RaceEntityClaimReview(BaseModel):
    status: str = Field(min_length=6, max_length=20)
    note: str = Field(default="", max_length=4000)


class RaceEditorialLinkCreate(BaseModel):
    entity_type: str = Field(min_length=3, max_length=24)
    entity_key: str = Field(min_length=1, max_length=220)
    title: str = Field(min_length=2, max_length=240)
    url: str = Field(min_length=5, max_length=4000)
    summary: str = Field(default="", max_length=4000)


def _race_account_or_401(request: Request) -> race_center_accounts.RaceCenterAccount:
    account = race_center_accounts.account_from_request(request)
    if not account:
        raise HTTPException(status_code=401, detail="Race Center account required.")
    return account


def _race_staff_or_403(request: Request) -> race_center_accounts.RaceCenterAccount:
    account = _race_account_or_401(request)
    profile = race_center_accounts.ensure_profile(account.id) or {}
    if not (profile.get("staff") or {}).get("label"):
        raise HTTPException(status_code=403, detail="Pitmark staff access required.")
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
    payload["profile"] = race_center_accounts.ensure_profile(account.id) if account else None
    payload["connections"] = race_center_accounts.connection_counts(account.id) if account else {"followers": 0, "following": 0}
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
            "profile": race_center_accounts.ensure_profile(account.id),
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
            "profile": race_center_accounts.ensure_profile(account.id),
        },
        account,
    )


@router.post("/api/public/race-center/account/logout", include_in_schema=False)
def race_center_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(race_center_accounts.SESSION_COOKIE, path="/")
    return response


@router.put("/api/public/race-center/profile/photo", include_in_schema=False)
async def race_center_profile_photo_upload(request: Request, photo: UploadFile = File(...)):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-profile-photo", 10, 300)
    raw = await photo.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Prepared profile photos must be 2 MB or smaller.")
    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image = ImageOps.fit(image, (640, 640), method=Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=88, method=6)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Upload a valid JPG, PNG, or WebP image.") from exc
    race_center_accounts.set_profile_photo(account.id, output.getvalue(), "image/webp")
    profile = race_center_accounts.ensure_profile(account.id)
    return {"ok": True, "photo_url": f"/api/public/race-center/profile-photo/{profile['handle']}?v={int(time.time())}"}


@router.get("/api/public/race-center/profile-photo/{handle}", include_in_schema=False)
def race_center_profile_photo(handle: str):
    result = race_center_accounts.profile_photo_by_handle(handle)
    if not result:
        raise HTTPException(status_code=404, detail="Profile photo not found.")
    image_data, content_type = result
    return Response(image_data, media_type=content_type, headers={"Cache-Control": "public, max-age=300"})


@router.get("/api/public/race-center/profile-wall/{handle}", include_in_schema=False)
def race_center_profile_wall(request: Request, handle: str, limit: int = 40):
    viewer = race_center_accounts.account_from_request(request)
    profile = race_center_accounts.public_profile_by_handle(
        handle,
        viewer_user_id=viewer.id if viewer else None,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Race Center profile not found.")
    return {
        "posts": race_center_accounts.list_posts(
            viewer_user_id=viewer.id if viewer else None,
            author_user_id=int(profile["id"]),
            limit=limit,
        )
    }


@router.post("/api/public/race-center/driver-claims", include_in_schema=False)
def race_center_driver_claim_submit(request: Request, body: RaceDriverClaimCreate):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-driver-claim", 8, 3600)
    try:
        return race_center_accounts.submit_driver_claim(
            account.id,
            driver_key=body.driver_key,
            driver_name=body.driver_name,
            series_key=body.series_key,
            evidence_url=body.evidence_url,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/public/race-center/driver-claims/me", include_in_schema=False)
def race_center_driver_claims_me(request: Request):
    account = _race_account_or_401(request)
    return {"claims": race_center_accounts.driver_claims_for_user(account.id)}


@router.get("/api/public/race-center/graph", include_in_schema=False)
def race_center_entity_graph():
    return race_center_entities.build_entity_graph()


@router.get("/api/public/race-center/search", include_in_schema=False)
def race_center_entity_search(q: str = "", limit: int = 24):
    return {"query": q, "results": race_center_entities.graph_search(q, limit=limit)}


@router.get("/api/public/race-center/compare", include_in_schema=False)
def race_center_driver_compare(a: str = "", b: str = ""):
    graph = race_center_entities.build_entity_graph()
    drivers = {str(item.get("key") or ""): item for item in graph.get("drivers") or []}
    left = drivers.get(str(a or "").strip())
    right = drivers.get(str(b or "").strip())
    if not left or not right:
        return {
            "a": left,
            "b": right,
            "drivers": [
                {
                    "key": item.get("key"),
                    "name": item.get("name"),
                    "number": item.get("number"),
                    "team": item.get("team"),
                    "manufacturer": item.get("manufacturer"),
                }
                for item in graph.get("drivers") or []
            ],
        }

    left_series = {str(item.get("series_key") or ""): item for item in left.get("series") or []}
    right_series = {str(item.get("series_key") or ""): item for item in right.get("series") or []}
    shared_keys = sorted(set(left_series) & set(right_series))
    shared = [
        {
            "series_key": key,
            "series_name": left_series[key].get("series_name") or right_series[key].get("series_name"),
            "a": left_series[key],
            "b": right_series[key],
        }
        for key in shared_keys
    ]
    return {
        "a": left,
        "b": right,
        "shared_series": shared,
        "drivers": [
            {
                "key": item.get("key"),
                "name": item.get("name"),
                "number": item.get("number"),
                "team": item.get("team"),
                "manufacturer": item.get("manufacturer"),
            }
            for item in graph.get("drivers") or []
        ],
    }


@router.get("/api/public/race-center/entity/{entity_type}/{entity_key}", include_in_schema=False)
def race_center_entity_detail(entity_type: str, entity_key: str):
    result = race_center_entities.entity_detail(entity_type, entity_key)
    if not result:
        raise HTTPException(status_code=404, detail="Race Center entity not found.")
    return result


@router.get("/api/public/race-center/relationships/{entity_type}/{entity_key}", include_in_schema=False)
def race_center_entity_relationships(entity_type: str, entity_key: str):
    result = race_center_entities.entity_detail(entity_type, entity_key)
    if not result:
        raise HTTPException(status_code=404, detail="Race Center entity not found.")
    return {
        "entity": {
            "type": result.get("type"),
            "key": result.get("key"),
            "name": result.get("name") or result.get("series_name"),
        },
        "relationships": result.get("relationships") or {},
    }


@router.get("/api/public/race-center/my-racing", include_in_schema=False)
def race_center_my_racing(request: Request):
    account = race_center_accounts.account_from_request(request)
    follows = race_center_accounts.list_follows(account.id) if account else []
    return race_center_entities.my_racing_brief(follows)


@router.get("/api/public/race-center/race-day", include_in_schema=False)
def race_center_race_day(request: Request):
    account = race_center_accounts.account_from_request(request)
    follows = race_center_accounts.list_follows(account.id) if account else []
    return race_center_entities.race_day_brief(follows)


@router.get("/api/public/race-center/data-health", include_in_schema=False)
def race_center_data_health():
    return race_center_entities.data_health()


@router.get("/api/public/race-center/calendar/event/{entity_key}.ics", include_in_schema=False)
def race_center_event_calendar(entity_key: str):
    event = race_center_entities.entity_detail("event", entity_key)
    if not event:
        raise HTTPException(status_code=404, detail="Race Center event not found.")
    return _race_center_calendar([event], name=str(event.get("name") or "Race Center event"))


@router.get("/api/public/race-center/calendar/series/{series_key}.ics", include_in_schema=False)
def race_center_series_calendar(series_key: str):
    graph = race_center_entities.build_entity_graph()
    events = [item for item in graph.get("events") or [] if item.get("series_key") == series_key]
    series = next((item for item in graph.get("series") or [] if item.get("key") == series_key), None)
    if not series:
        raise HTTPException(status_code=404, detail="Race Center series not found.")
    return _race_center_calendar(events, name=f"{series.get('name') or series_key} — Race Center")


@router.get("/api/public/race-center/calendar/track/{track_key}.ics", include_in_schema=False)
def race_center_track_calendar(track_key: str):
    graph = race_center_entities.build_entity_graph()
    events = [item for item in graph.get("events") or [] if item.get("track_key") == track_key]
    track = next((item for item in graph.get("tracks") or [] if item.get("key") == track_key), None)
    if not track:
        raise HTTPException(status_code=404, detail="Race Center track not found.")
    return _race_center_calendar(events, name=f"{track.get('name') or track_key} — Race Center")


@router.get("/api/public/race-center/calendar/my-racing.ics", include_in_schema=False)
def race_center_my_racing_calendar(request: Request):
    account = _race_account_or_401(request)
    follows = race_center_accounts.list_follows(account.id)
    brief = race_center_entities.my_racing_brief(follows)
    events = [*(brief.get("live") or []), *(brief.get("upcoming") or [])]
    return _race_center_calendar(events, name="My Racing — Pitmark Race Center")


@router.get("/api/public/race-center/archive/{series_key}", include_in_schema=False)
def race_center_series_archive(series_key: str, season: int | None = None, limit: int = 24):
    return race_center_entities.series_archive(series_key, season=season, limit=limit)


@router.get("/api/public/race-center/alerts", include_in_schema=False)
def race_center_alerts(request: Request):
    account = race_center_accounts.account_from_request(request)
    follows = race_center_accounts.list_follows(account.id) if account else []
    return {"alerts": race_center_entities.alerts_for_user(follows)}


@router.get("/api/public/race-center/notifications", include_in_schema=False)
def race_center_notification_preferences(request: Request):
    account = _race_account_or_401(request)
    return {"preferences": race_center_entities.notification_preferences(account.id)}


@router.put("/api/public/race-center/notifications", include_in_schema=False)
def race_center_notification_preferences_update(request: Request, body: RaceNotificationPreferences):
    account = _race_account_or_401(request)
    values = {key: value for key, value in body.model_dump().items() if value is not None}
    return {"preferences": race_center_entities.update_notification_preferences(account.id, values)}


@router.post("/api/public/race-center/entity-claims", include_in_schema=False)
def race_center_entity_claim_submit(request: Request, body: RaceEntityClaimCreate):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-entity-claim", 12, 3600)
    try:
        return race_center_entities.submit_entity_claim(
            account.id,
            entity_type=body.entity_type,
            entity_key=body.entity_key,
            entity_name=body.entity_name,
            evidence_url=body.evidence_url,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/public/race-center/entity-claims/me", include_in_schema=False)
def race_center_entity_claims_me(request: Request):
    account = _race_account_or_401(request)
    return {"claims": race_center_entities.entity_claims_for_user(account.id)}


@router.put("/api/public/race-center/entity-profile/{entity_type}/{entity_key}", include_in_schema=False)
def race_center_entity_profile_update(
    request: Request,
    entity_type: str,
    entity_key: str,
    body: RaceEntityOwnerProfileChange,
):
    account = _race_account_or_401(request)
    try:
        profile = race_center_entities.update_entity_owner_content(
            account.id,
            entity_type=entity_type,
            entity_key=entity_key,
            bio=body.bio,
            website_url=body.website_url,
            shop_url=body.shop_url,
            contact_url=body.contact_url,
            hero_url=body.hero_url,
            sponsors=body.sponsors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"ok": True, "profile": profile}


@router.get("/api/public/race-center/entity-claims/review", include_in_schema=False)
def race_center_entity_claim_review_queue(request: Request, status: str = "", limit: int = 100):
    _race_staff_or_403(request)
    return {"claims": race_center_entities.entity_claims_for_review(status=status, limit=limit)}


@router.put("/api/public/race-center/entity-claims/{claim_id}/review", include_in_schema=False)
def race_center_entity_claim_review(request: Request, claim_id: int, body: RaceEntityClaimReview):
    staff = _race_staff_or_403(request)
    try:
        return race_center_entities.review_entity_claim(
            claim_id,
            status=body.status,
            reviewer_user_id=staff.id,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/public/race-center/editorial-links", include_in_schema=False)
def race_center_editorial_link_create(request: Request, body: RaceEditorialLinkCreate):
    _race_staff_or_403(request)
    return race_center_entities.attach_editorial(
        entity_type=body.entity_type,
        entity_key=body.entity_key,
        title=body.title,
        url=body.url,
        summary=body.summary,
    )


@router.get("/api/public/race-center/driver-identity/{series_key}/{driver_name:path}", include_in_schema=False)
def race_center_driver_identity(request: Request, series_key: str, driver_name: str):
    enforce_rate_limit(request, "race-center-driver-identity", 240, 300)
    if not any(item.get("key") == series_key for item in STANDINGS_SERIES):
        raise HTTPException(status_code=404, detail="Race Center series not found.")
    return get_driver_identity(series_key, driver_name)


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




@router.put("/api/public/race-center/profile", include_in_schema=False)
def race_center_profile_update(request: Request, body: RaceProfileChange):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-profile", 20, 300)
    try:
        profile = race_center_accounts.update_profile(
            account.id,
            handle=body.handle,
            bio=body.bio,
            favorite_track=body.favorite_track,
            account_type=body.account_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "profile": profile}


@router.get("/api/public/race-center/feed", include_in_schema=False)
def race_center_feed(request: Request, limit: int = 40):
    account = race_center_accounts.account_from_request(request)
    series_keys: list[str] = []
    if account:
        series_keys = [
            str(item.get("key") or "")
            for item in race_center_accounts.list_follows(account.id)
            if item.get("kind") == "series" and item.get("key")
        ]
    return {
        "posts": race_center_accounts.list_posts(
            viewer_user_id=account.id if account else None,
            limit=limit,
            series_keys=series_keys or None,
        )
    }


@router.post("/api/public/race-center/feed", include_in_schema=False)
def race_center_post_create(request: Request, body: RacePostCreate):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-post", 12, 300)
    try:
        result = race_center_accounts.create_post(
            account.id,
            body=body.body,
            series_key=body.series_key,
            driver_key=body.driver_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        **result,
        "posts": race_center_accounts.list_posts(viewer_user_id=account.id, limit=40),
    }


@router.delete("/api/public/race-center/feed/{post_id}", include_in_schema=False)
def race_center_post_delete(request: Request, post_id: int):
    account = _race_account_or_401(request)
    try:
        race_center_accounts.delete_post(account.id, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"ok": True}


@router.post("/api/public/race-center/feed/{post_id}/reaction", include_in_schema=False)
def race_center_react(request: Request, post_id: int, body: RaceReactionChange):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-reaction", 60, 300)
    try:
        result = race_center_accounts.toggle_reaction(account.id, post_id, body.reaction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.post("/api/public/race-center/feed/{post_id}/comments", include_in_schema=False)
def race_center_comment(request: Request, post_id: int, body: RaceCommentCreate):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-comment", 30, 300)
    try:
        result = race_center_accounts.add_comment(account.id, post_id, body.body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result




@router.get("/api/public/race-center/people/discover", include_in_schema=False)
def race_center_people_discover(request: Request, limit: int = 12):
    account = _race_account_or_401(request)
    return {"people": race_center_accounts.discover_people(account.id, limit=limit)}


@router.get("/api/public/race-center/people/{handle}", include_in_schema=False)
def race_center_public_profile(request: Request, handle: str):
    account = race_center_accounts.account_from_request(request)
    profile = race_center_accounts.public_profile_by_handle(
        handle,
        viewer_user_id=account.id if account else None,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Race Center profile not found.")
    return profile


@router.put("/api/public/race-center/people/follow", include_in_schema=False)
def race_center_people_follow(request: Request, body: RaceUserFollowChange):
    account = _race_account_or_401(request)
    enforce_rate_limit(request, "race-center-people-follow", 60, 300)
    try:
        race_center_accounts.follow_user(account.id, body.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "connections": race_center_accounts.connection_counts(account.id),
        "people": race_center_accounts.discover_people(account.id, limit=12),
    }


@router.delete("/api/public/race-center/people/follow", include_in_schema=False)
def race_center_people_unfollow(request: Request, body: RaceUserFollowChange):
    account = _race_account_or_401(request)
    race_center_accounts.unfollow_user(account.id, body.user_id)
    return {
        "ok": True,
        "connections": race_center_accounts.connection_counts(account.id),
    }


@router.get("/race-center", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/compare", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/tracks", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/track/{entity_key}", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/teams", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/team/{entity_key}", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/events", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/event/{entity_key}", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/my-racing", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/health", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/series", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/series/{series_key}", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/drivers", response_class=HTMLResponse, include_in_schema=False)
@router.get("/race-center/driver/{series_key}/{driver_name:path}", response_class=HTMLResponse, include_in_schema=False)
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
        else "driver" if "/race-center/driver/" in path
        else "drivers" if path.endswith("/drivers")
        else "seriesprofile" if "/race-center/series/" in path
        else "series" if path.endswith("/series")
        else "trackprofile" if "/race-center/track/" in path
        else "tracks" if path.endswith("/tracks")
        else "teamprofile" if "/race-center/team/" in path
        else "teams" if path.endswith("/teams")
        else "eventprofile" if "/race-center/event/" in path
        else "events" if path.endswith("/events")
        else "myracing" if path.endswith("/my-racing")
        else "compare" if path.endswith("/compare")
        else "health" if path.endswith("/health")
        else "hub"
    )
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
    html = html.replace("{{RACE_CENTER_VIEW}}", view)
    return HTMLResponse(
        html,
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get("/race-center/u/{handle}", response_class=HTMLResponse, include_in_schema=False)
def public_race_center_user_profile(handle: str):
    html = (ASSET_DIR / "race_center_profile.html").read_text(encoding="utf-8")
    html = html.replace("{{PITMARK_VERSION}}", settings.app_version)
    html = html.replace("{{PROFILE_HANDLE}}", handle)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store"})


@router.get("/race-center-profile.js", include_in_schema=False)
def public_race_center_profile_js():
    return _asset("race_center_profile.js", "application/javascript")


@router.get("/standings.css", include_in_schema=False)
def public_standings_css():
    return _asset("standings_public.css", "text/css")


@router.get("/standings.js", include_in_schema=False)
def public_standings_js():
    return _asset("standings_public.js", "application/javascript")


@router.get("/race-center-v5.js", include_in_schema=False)
def public_race_center_v5_js():
    return _asset("race_center_v5.js", "application/javascript")


@router.get("/race-center-v6.js", include_in_schema=False)
def public_race_center_v6_js():
    return _asset("race_center_v6.js", "application/javascript")


@router.get("/race-center-v7.js", include_in_schema=False)
def public_race_center_v7_js():
    return _asset("race_center_v7.js", "application/javascript")


@router.get("/race-center.webmanifest", include_in_schema=False)
def public_race_center_manifest():
    return _asset("race-center.webmanifest", "application/manifest+json")


def _race_center_icon(size: int) -> Response:
    if size not in {192, 512}:
        raise HTTPException(status_code=404, detail="Race Center icon size not found.")
    source = Image.open(ASSET_DIR / "pitmark_favicon.png").convert("RGBA")
    inset = max(18, int(size * 0.14))
    mark = ImageOps.contain(source, (size - inset * 2, size - inset * 2), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (9, 11, 14, 255))
    canvas.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return Response(out.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/race-center-icon-192.png", include_in_schema=False)
def public_race_center_icon_192():
    return _race_center_icon(192)


@router.get("/race-center-icon-512.png", include_in_schema=False)
def public_race_center_icon_512():
    return _race_center_icon(512)


@router.get("/race-center-sw.js", include_in_schema=False)
def public_race_center_service_worker():
    response = _asset("race_center_sw.js", "application/javascript")
    response.headers["Service-Worker-Allowed"] = "/race-center/"
    return response


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
    grassroots = get_grassroots_catalog()
    event_series = event_hub.get("series") or {}
    safe_series = []
    for series in payload.get("series") or []:
        identity_verified = bool(series.get("metadata_verified"))
        # Saved standings are already hydrated server-side with source-backed
        # identity from official series data, persistent verified enrichment,
        # and explicit verified fallbacks. Do not erase that trusted per-driver
        # identity merely because the original series-wide metadata scrape was
        # incomplete.
        safe_entries = [dict(raw_entry) for raw_entry in (series.get("entries") or [])]
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
                "grassroots": {
                    "generated_at": grassroots.get("generated_at"),
                    "warming": bool(grassroots.get("warming")),
                    "summary": grassroots.get("summary") or {},
                    "sources": grassroots.get("sources") or [],
                    "drivers": grassroots.get("drivers") or [],
                },
                "series": safe_series,
            },
            ensure_ascii=False,
            default=str,
        ),
        media_type="application/json",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
