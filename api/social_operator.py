from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from services.control_auth import require_control_user
from services.database import SessionLocal
from services.meta_publish_service import reply_facebook_comment, reply_instagram_comment
from services.social_operator import (
    SocialEngagementEvent,
    operator_status,
    run_operator_once,
)
from utils.config import settings

router = APIRouter()
_operator_paused = False


class EngagementReplyRequest(BaseModel):
    message: str


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


@router.get("/status")
def get_operator_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    payload = operator_status()
    payload["paused"] = _operator_paused
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
