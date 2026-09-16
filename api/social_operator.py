from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from services.control_auth import require_control_user
from services.control_center import SocialPost
from services.database import SessionLocal
from services.meta_publish_service import _page_token, reply_facebook_comment, reply_instagram_comment
from services.social_daily_campaign import campaign_status, ensure_daily_campaign
from services.social_daily_package import generate_daily_package
from services.social_operator import (
    SocialEngagementEvent,
    operator_status,
    run_operator_once,
)
from services.social_operator_logic import counts_toward_daily_coverage
from utils.config import settings

router = APIRouter()
log = logging.getLogger(__name__)
_operator_paused = False
_meta_diag_cache: tuple[datetime, dict] | None = None


class EngagementReplyRequest(BaseModel):
    message: str


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


def _probe_token_permissions(token: str) -> dict:
    try:
        response = httpx.get(
            f"https://graph.facebook.com/{settings.meta_graph_version.strip('/')}/me/permissions",
            params={"access_token": token},
            timeout=12.0,
        )
        payload = response.json()
        if response.is_error:
            detail = (payload.get("error") or {}).get("message") if isinstance(payload, dict) else response.text
            return {"ok": False, "error": str(detail or f"HTTP {response.status_code}")[:300]}
        granted = sorted(
            str(item.get("permission"))
            for item in (payload.get("data") or [])
            if isinstance(item, dict) and item.get("status") == "granted" and item.get("permission")
        )
        return {"ok": True, "granted": granted}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def _probe_comment_read(token: str) -> dict:
    try:
        response = httpx.get(
            f"https://graph.facebook.com/{settings.meta_graph_version.strip('/')}/{settings.meta_page_id.strip()}/published_posts",
            params={
                "fields": "id,comments.limit(1){id}",
                "limit": 1,
                "access_token": token,
            },
            timeout=12.0,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.is_error:
            err = payload.get("error") if isinstance(payload, dict) else None
            return {
                "ok": False,
                "http_status": response.status_code,
                "code": (err or {}).get("code") if isinstance(err, dict) else None,
                "error": str((err or {}).get("message") if isinstance(err, dict) else response.text)[:300],
            }
        return {"ok": True, "http_status": response.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def _meta_permission_diagnostics() -> dict:
    """Inspect safe metadata about every configured Facebook token candidate.

    This intentionally never returns or logs token values. It verifies the exact
    capability Social Operator needs instead of inferring health from publishing.
    """
    global _meta_diag_cache
    now = datetime.now(timezone.utc)
    if _meta_diag_cache and now - _meta_diag_cache[0] < timedelta(minutes=10):
        return _meta_diag_cache[1]

    current = _page_token()
    legacy = settings.meta_page_access_token.strip()
    system = settings.meta_system_user_access_token.strip()
    candidates: list[tuple[str, str]] = []
    if current:
        candidates.append(("resolved_page", current))
    if legacy and all(token != legacy for _, token in candidates):
        candidates.append(("legacy_page", legacy))

    result = {
        "ok": False,
        "configured": {
            "app_id": bool(settings.meta_app_id.strip()),
            "app_secret": bool(settings.meta_app_secret.strip()),
            "page_id": bool(settings.meta_page_id.strip()),
            "page_access_token": bool(legacy),
            "system_user_token": bool(system),
        },
        "candidates": [],
    }

    for label, token in candidates:
        permissions = _probe_token_permissions(token)
        read_probe = _probe_comment_read(token)
        result["candidates"].append(
            {
                "source": label,
                "permissions": permissions,
                "comment_read": read_probe,
            }
        )

    working = [item for item in result["candidates"] if item["comment_read"].get("ok")]
    result["ok"] = bool(working)
    result["working_source"] = working[0]["source"] if working else None
    if not candidates:
        result["error"] = "No Facebook Page token is configured."
    elif not working:
        result["error"] = "No configured Page token can read Facebook comments."

    _meta_diag_cache = (now, result)
    log.info(
        "Meta permission diagnostic: configured=%s candidates=%s working_source=%s",
        result["configured"],
        result["candidates"],
        result["working_source"],
    )
    return result


try:
    print(f"META_PERMISSION_STARTUP_DIAGNOSTIC {_meta_permission_diagnostics()}", flush=True)
except Exception as exc:
    print(f"META_PERMISSION_STARTUP_DIAGNOSTIC_FAILED {type(exc).__name__}: {exc}", flush=True)


def _build_daily_campaign_once() -> dict:
    if not settings.social_daily_campaign_enabled:
        return {"ok": False, "enabled": False, "error": "Daily Campaign is disabled."}
    campaign = ensure_daily_campaign()
    result = generate_daily_package(campaign["id"])
    current = campaign_status() or result.get("campaign") or campaign
    return {
        "ok": bool(result.get("ok")),
        "enabled": True,
        "campaign": current,
        "progress": current.get("progress") or result.get("progress") or {},
        "queue": current.get("queue") or result.get("queue") or {},
        "image_batch_size": settings.social_daily_image_batch_size,
    }


@router.get("/status")
def get_operator_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    payload = operator_status()
    payload["paused"] = _operator_paused
    payload["facebook_permissions"] = _meta_permission_diagnostics()
    payload["daily_campaign"] = campaign_status()
    payload["daily_campaign_enabled"] = settings.social_daily_campaign_enabled

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost).where(
                    SocialPost.status.in_(["scheduled", "published"]),
                )
            ).all()
        )
    rows = [
        row
        for row in rows
        if row.source == "operator:growth-loop"
        or str(row.source or "").startswith("dailycampaign:")
    ]
    today_rows = [
        row
        for row in rows
        if counts_toward_daily_coverage(
            status=row.status,
            scheduled_for=row.scheduled_for,
            created_at=row.created_at,
            updated_at=row.updated_at,
            now=now,
            timezone_name=settings.pitmark_timezone,
        )
    ]
    payload["today"] = {
        "posts_planned": len(today_rows),
        "platforms": sorted({str(row.platform or "").lower() for row in today_rows if row.platform}),
    }
    return payload


@router.get("/daily-campaign/status")
def get_daily_campaign_status(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    return {
        "enabled": settings.social_daily_campaign_enabled,
        "image_generation_enabled": settings.social_daily_image_generation_enabled,
        "image_batch_size": settings.social_daily_image_batch_size,
        "campaign": campaign_status(),
    }


@router.post("/daily-campaign/run")
def run_daily_campaign(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    return _build_daily_campaign_once()


@router.post("/run")
def run_operator(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    daily = None
    if settings.social_daily_campaign_enabled:
        try:
            daily = _build_daily_campaign_once()
        except Exception as exc:
            log.exception("Manual Daily Campaign pass failed")
            daily = {"ok": False, "error": str(exc)}
    result = run_operator_once()
    result["daily_campaign"] = (daily or {}).get("campaign")
    result["daily_progress"] = (daily or {}).get("progress")
    result["daily_error"] = (daily or {}).get("error")
    return result


@router.post("/pause")
def pause_operator(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    global _operator_paused
    _operator_paused = True
    settings.social_operator_enabled = False
    return {"ok": True, "paused": True}


@router.post("/resume")
def resume_operator(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    global _operator_paused
    _operator_paused = False
    settings.social_operator_enabled = True
    return {"ok": True, "paused": False}


@router.get("/engagement")
def list_engagement(
    request: Request,
    status: str | None = None,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        query = select(SocialEngagementEvent).order_by(SocialEngagementEvent.id.desc()).limit(100)
        if status:
            query = (
                select(SocialEngagementEvent)
                .where(SocialEngagementEvent.action_status == status)
                .order_by(SocialEngagementEvent.id.desc())
                .limit(100)
            )
        rows = list(db.scalars(query).all())
    return {
        "items": [
            {
                "id": row.id,
                "platform": row.platform,
                "external_id": row.external_id,
                "parent_external_id": row.parent_external_id,
                "author_name": row.author_name,
                "body": row.body,
                "classification": row.classification,
                "action_status": row.action_status,
                "response": row.response,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]
    }


@router.post("/engagement/{event_id}/reply")
def reply_to_engagement(
    event_id: int,
    payload: EngagementReplyRequest,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    message = payload.message.strip()
    if not message:
        raise HTTPException(400, "Reply message is empty.")
    with SessionLocal() as db:
        event = db.get(SocialEngagementEvent, event_id)
        if not event:
            raise HTTPException(404, "Engagement event not found.")
        platform = event.platform
        raw_external_id = event.external_id.split(":", 1)[1] if ":" in event.external_id else event.external_id
        try:
            if platform == "facebook":
                result = reply_facebook_comment(raw_external_id, message)
            elif platform == "instagram":
                result = reply_instagram_comment(raw_external_id, message)
            else:
                raise HTTPException(400, "Manual X replies are not enabled in Social Operator v1.")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, str(exc)) from exc
        event.action_status = "replied"
        event.response = message
        from services.control_center import utcnow

        event.updated_at = utcnow()
        db.commit()
    return {"ok": True, "publish": result}


@router.post("/engagement/{event_id}/dismiss")
def dismiss_engagement(
    event_id: int,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        event = db.get(SocialEngagementEvent, event_id)
        if not event:
            raise HTTPException(404, "Engagement event not found.")
        event.action_status = "dismissed"
        from services.control_center import utcnow

        event.updated_at = utcnow()
        db.commit()
    return {"ok": True}


def _install_control_center_operator_assets() -> None:
    """Layer Social Operations UI onto the already-loaded v202 Control Center bundle."""
    try:
        from api import control_center_ui

        for path, media_type, base_name, extra_names in (
            (
                "/control-center-v202.js",
                "application/javascript",
                "control_center_v202.js",
                ("control_social_operator.js", "control_social_daily_campaign.js"),
            ),
            (
                "/control-center-v202.css",
                "text/css",
                "control_center_v202.css",
                ("control_social_operator.css", "control_social_daily_campaign.css"),
            ),
        ):
            control_center_ui.router.routes[:] = [
                route
                for route in control_center_ui.router.routes
                if getattr(route, "path", None) != path
            ]

            def layered_asset(
                _base_name: str = base_name,
                _extra_names: tuple[str, ...] = extra_names,
                _media_type: str = media_type,
            ) -> Response:
                pieces = [
                    (control_center_ui.ASSET_DIR / _base_name).read_text(encoding="utf-8")
                ]
                pieces.extend(
                    (control_center_ui.ASSET_DIR / name).read_text(encoding="utf-8")
                    for name in _extra_names
                )
                return Response(
                    "\n\n".join(pieces),
                    media_type=_media_type,
                    headers={"Cache-Control": "no-store"},
                )

            control_center_ui.router.add_api_route(
                path,
                layered_asset,
                methods=["GET"],
                include_in_schema=False,
            )
    except Exception:
        log.exception("Could not install Social Operations Control Center assets")


_install_control_center_operator_assets()
