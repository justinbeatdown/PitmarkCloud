from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
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

router = APIRouter()


class EngagementReplyRequest(BaseModel):
    message: str


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


@router.get("/status")
def get_operator_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    return operator_status()


@router.post("/run")
def run_operator(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    return run_operator_once()


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
