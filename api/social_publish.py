from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

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
from services.social_asset_pool import add_asset, choose_asset, get_uploaded_image, list_assets, mark_used, store_uploaded_image, sync_shopify_images

router = APIRouter()
public_router = APIRouter()


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


@router.post("/assets/suggest")
def suggest_social_asset(payload: dict, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    body = str(payload.get("body") or "")
    content_type = str(payload.get("content_type") or "community")
    asset = choose_asset(body=body, content_type=content_type, platform="instagram")
    if not asset:
        try:
            sync_shopify_images()
        except Exception:
            pass
        asset = choose_asset(body=body, content_type=content_type, platform="instagram")
    return {"asset": asset}


@router.post("/assets/upload")
async def upload_social_asset(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    auth(request, x_pitmark_admin_key)
    raw = await request.body()
    filename = request.headers.get("x-pitmark-filename", "pitmark-upload")
    add_to_library = request.headers.get("x-pitmark-add-to-library", "false").lower() == "true"
    try:
        stored = store_uploaded_image(data=raw, filename=filename, mime_type=request.headers.get("content-type", ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    base = str(request.base_url).rstrip("/")
    public_url = f"{base}/social-assets/{stored['public_token']}"
    asset = None
    if add_to_library:
        asset = add_asset(url=public_url, title=filename, source="upload", source_ref=f"upload:{stored['id']}", tags=["upload", "social", "instagram"])
    return {"ok": True, "url": public_url, "stored": {k:v for k,v in stored.items() if k != "public_token"}, "asset": asset}


@public_router.get("/social-assets/{public_token}")
def public_social_asset(public_token: str):
    item = get_uploaded_image(public_token)
    if not item:
        raise HTTPException(404, "Asset not found")
    return Response(item["data"], media_type=item["mime_type"], headers={"Cache-Control":"public, max-age=31536000, immutable","Content-Disposition":f'inline; filename="{item["filename"]}"'})


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

        # Reactive social posts sourced from intelligence expire quickly. Manual/evergreen posts do not.
        if (post.source or "").startswith("intelligence:") and platform in {"facebook", "instagram"}:
            try:
                opportunity_id = int((post.source or "").split(":", 1)[1])
                from services.control_center import OpportunitySourceMeta
                meta = db.scalar(select(OpportunitySourceMeta).where(OpportunitySourceMeta.opportunity_id == opportunity_id))
                if meta and meta.published_at:
                    from datetime import datetime, timezone
                    published = meta.published_at if meta.published_at.tzinfo else meta.published_at.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 3600
                    from utils.config import settings
                    if age_hours > settings.social_realtime_max_age_hours:
                        raise HTTPException(409, f"This reactive social opportunity is {age_hours:.1f} hours old and has expired from the real-time social lane. Use it for long-form/blog context instead.")
            except ValueError:
                pass
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
