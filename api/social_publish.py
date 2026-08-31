from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from services.control_auth import require_control_user
from services.control_center import SocialPost, serialize, utcnow
from services.database import SessionLocal
from services.meta_publish_service import (
    MetaPublishError,
    facebook_connection_status,
    instagram_connection_status,
    publish_facebook_post,
    publish_instagram_post,
)
from services.social_asset_pool import add_asset, choose_asset, list_assets, mark_used, sync_shopify_images

router = APIRouter()


class AssetCreate(BaseModel):
    url: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


def auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


@router.get("/status")
def social_publish_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    facebook = facebook_connection_status()
    instagram = instagram_connection_status()
    supported = []
    if facebook.get("configured"): supported.append("facebook")
    if instagram.get("configured"): supported.append("instagram")
    return {"facebook": facebook, "instagram": instagram, "supported_platforms": supported}


@router.get("/assets")
def social_assets(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    return {"items": list_assets()}


@router.post("/assets")
def create_social_asset(payload: AssetCreate, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    try:
        asset = add_asset(url=payload.url, title=payload.title, source="manual", tags=payload.tags)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True, "asset": asset}


@router.post("/assets/sync/shopify")
def sync_social_assets_from_shopify(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    try:
        return sync_shopify_images()
    except Exception as exc:
        raise HTTPException(502, f"Shopify asset sync failed: {exc}")


def _auto_asset(post: SocialPost) -> dict | None:
    asset = choose_asset(body=post.body, content_type=post.content_type, platform=post.platform)
    if asset:
        return asset
    try:
        sync_shopify_images()
    except Exception:
        return None
    return choose_asset(body=post.body, content_type=post.content_type, platform=post.platform)


@router.post("/posts/{post_id}/assign-asset")
def assign_asset(post_id: int, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        post = db.get(SocialPost, post_id)
        if not post:
            raise HTTPException(404, "Post not found.")
        asset = _auto_asset(post)
        if not asset:
            raise HTTPException(409, "No approved Pitmark images are available yet.")
        post.media_url = asset["url"]
        post.updated_at = utcnow()
        db.commit(); db.refresh(post)
        return {"ok": True, "post": serialize(post), "asset": asset}


@router.post("/posts/{post_id}/publish")
def publish_post(post_id: int, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        post = db.get(SocialPost, post_id)
        if not post:
            raise HTTPException(404, "Post not found.")
        platform = (post.platform or "").strip().lower()
        if platform not in {"facebook", "instagram"}:
            raise HTTPException(400, f"Live publishing is not connected for {platform or 'this platform'} yet.")
        if post.status not in {"approved", "scheduled"}:
            raise HTTPException(409, "Only approved or scheduled posts may be published.")
        try:
            if platform == "facebook":
                result = publish_facebook_post(post.body)
            else:
                media_url = (post.media_url or "").strip()
                if not media_url:
                    asset = _auto_asset(post)
                    if not asset:
                        raise HTTPException(409, "Instagram needs an image and no Pitmark image could be selected.")
                    media_url = asset["url"]
                    post.media_url = media_url
                result = publish_instagram_post(caption=post.body, image_url=media_url)
                mark_used(media_url)
        except HTTPException:
            raise
        except MetaPublishError as exc:
            raise HTTPException(502, str(exc))
        post.status = "published"
        post.updated_at = utcnow()
        db.commit(); db.refresh(post)
        return {"ok": True, "post": serialize(post), "publish": result}
