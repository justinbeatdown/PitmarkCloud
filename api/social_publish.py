from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from services.control_auth import require_control_user
from services.control_center import SocialPost, serialize, utcnow
from services.database import SessionLocal
from services.meta_publish_service import (
    MetaPublishError,
    connection_status as meta_connection_status,
    publish_facebook_post,
)

router = APIRouter()


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


@router.get("/status")
def social_publish_status(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)
    return {
        "facebook": meta_connection_status(),
        "supported_platforms": ["facebook"],
    }


@router.post("/posts/{post_id}/publish")
def publish_post(
    post_id: int,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    auth(request, x_pitmark_admin_key)

    with SessionLocal() as db:
        post = db.get(SocialPost, post_id)
        if not post:
            raise HTTPException(404, "Post not found.")

        platform = (post.platform or "").strip().lower()
        if platform != "facebook":
            raise HTTPException(
                400,
                f"Live publishing is not connected for {platform or 'this platform'} yet.",
            )

        if post.status not in {"approved", "scheduled"}:
            raise HTTPException(
                409,
                "Only approved or scheduled posts may be published.",
            )

        try:
            result = publish_facebook_post(post.body)
        except MetaPublishError as exc:
            raise HTTPException(502, str(exc))

        post.status = "published"
        post.updated_at = utcnow()
        db.commit()
        db.refresh(post)

        return {
            "ok": True,
            "post": serialize(post),
            "publish": result,
        }
