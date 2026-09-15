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


def _meta_permission_diagnostics() -> dict:
    """Inspect only safe metadata about the actual Page token used by Social Operator.

    Never returns or logs the token itself. Cached briefly so the Control Center's
    status polling does not hammer Meta's debug_token endpoint.
    """
    global _meta_diag_cache
    now = datetime.now(timezone.utc)
    if _meta_diag_cache and now - _meta_diag_cache[0] < timedelta(minutes=10):
        return _meta_diag_cache[1]

    app_id = settings.meta_app_id.strip()
    app_secret = settings.meta_app_secret.strip()
    token = _page_token()
    if not app_id or not app_secret or not token:
        result = {
            "ok": False,
            "error": "Meta app credentials or Page token are not fully configured.",
            "scopes": [],
        }
        _meta_diag_cache = (now, result)
        return result

    try:
        response = httpx.get(
            f"https://graph.facebook.com/{settings.meta_graph_version.strip('/')}/debug_token",
            params={
                "input_token": token,
                "access_token": f"{app_id}|{app_secret}",
            },
            timeout=12.0,
        )
        payload = response.json()
        if response.is_error:
            error = (payload.get("error") or {}).get("message") if isinstance(payload, dict) else response.text
            raise RuntimeError(error or f"Meta debug_token failed with HTTP {response.status_code}")
        data = payload.get("data") or {}
        scopes = sorted({str(scope) for scope in (data.get("scopes") or []) if scope})
        granular = data.get("granular_scopes") or []
        comment_requirements = {
            "pages_read_engagement",
            "pages_read_user_content",
            "pages_manage_engagement",
            "pages_manage_metadata",
            "pages_show_list",
        }
        result = {
            "ok": bool(data.get("is_valid")),
            "is_valid": bool(data.get("is_valid")),
            "token_type": data.get("type"),
            "app_matches": str(data.get("app_id") or "") == app_id,
            "scopes": scopes,
            "granular_scopes": [
                {
                    "scope": str(item.get("scope") or ""),
                    "target_ids": [str(value) for value in (item.get("target_ids") or [])],
                }
                for item in granular
                if isinstance(item, dict)
            ],
            "missing_comment_scopes": sorted(comment_requirements.difference(scopes)),
        }
    except Exception as exc:
        result = {"ok": False, "error": str(exc)[:400], "scopes": []}

    _meta_diag_cache = (now, result)
    log.info(
        "Meta permission diagnostic: valid=%s type=%s scopes=%s missing_comment_scopes=%s",
        result.get("is_valid"),
        result.get("token_type"),
        result.get("scopes"),
        result.get("missing_comment_scopes"),
    )
    return result


@router.get("/status")
def get_operator_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    payload = operator_status()
    payload["paused"] = _operator_paused
    payload["facebook_permissions"] = _meta_permission_diagnostics()

    # Latest-run counters answer "what happened in the last pass?" but the Control
    # Center also needs to answer "did the operator actually line anything up today?".
    # Keep a daily activity snapshot so a healthy no-op pass does not visually erase
    # work the operator already completed earlier in the day.
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost).where(
                    SocialPost.source == "operator:growth-loop",
                    SocialPost.status.in_(["scheduled", "published"]),
                )
            ).all()
        )
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


@router.post("/run")
def run_operator(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    return run_operator_once()


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
            query = select(SocialEngagementEvent).where(SocialEngagementEvent.action_status == status).order_by(SocialEngagementEvent.id.desc()).limit(100)
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
    """Layer Social Operator UI onto the already-loaded v202 Control Center bundle."""
    try:
        from api import control_center_ui

        for path, media_type, base_name, operator_name in (
            ("/control-center-v202.js", "application/javascript", "control_center_v202.js", "control_social_operator.js"),
            ("/control-center-v202.css", "text/css", "control_center_v202.css", "control_social_operator.css"),
        ):
            control_center_ui.router.routes[:] = [
                route for route in control_center_ui.router.routes if getattr(route, "path", None) != path
            ]

            def layered_asset(
                _base_name: str = base_name,
                _operator_name: str = operator_name,
                _media_type: str = media_type,
            ) -> Response:
                base = (control_center_ui.ASSET_DIR / _base_name).read_text(encoding="utf-8")
                operator = (control_center_ui.ASSET_DIR / _operator_name).read_text(encoding="utf-8")
                return Response(
                    base + "\n\n" + operator,
                    media_type=_media_type,
                    headers={"Cache-Control": "no-store"},
                )

            control_center_ui.router.add_api_route(path, layered_asset, methods=["GET"], include_in_schema=False)
    except Exception:
        # A UI enhancement must never prevent Pitmark Cloud from starting.
        pass


_install_control_center_operator_assets()
