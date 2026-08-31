from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.meta_publish_service import facebook_configured, instagram_configured, publish_facebook_post, publish_instagram_post
from services.social_asset_pool import choose_asset, mark_used, sync_shopify_images
from utils.config import settings

log = logging.getLogger(__name__)


def _scheduled_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        try:
            local_zone = ZoneInfo(settings.pitmark_timezone)
        except Exception:
            local_zone = timezone.utc
        dt = dt.replace(tzinfo=local_zone)
    return dt.astimezone(timezone.utc)


def _platform_ready(platform: str) -> bool:
    return facebook_configured() if platform == "facebook" else instagram_configured() if platform == "instagram" else False


def _asset_for(post: SocialPost) -> str | None:
    if (post.media_url or "").strip():
        return post.media_url.strip()
    asset = choose_asset(body=post.body, content_type=post.content_type, platform="instagram")
    if not asset:
        try:
            sync_shopify_images()
        except Exception:
            return None
        asset = choose_asset(body=post.body, content_type=post.content_type, platform="instagram")
    return asset["url"] if asset else None


def publish_due_posts() -> int:
    now = datetime.now(timezone.utc)
    published = 0
    with SessionLocal() as db:
        rows = list(db.scalars(select(SocialPost).where(SocialPost.status == "scheduled", SocialPost.platform.in_(["facebook", "instagram"])).order_by(SocialPost.id.asc())).all())
        for post in rows:
            platform = (post.platform or "").strip().lower()
            if not _platform_ready(platform):
                continue
            due = _scheduled_time(post.scheduled_for)
            if due is None or due > now:
                continue
            if (post.source or "").startswith("intelligence:"):
                try:
                    from services.control_center import OpportunitySourceMeta
                    opportunity_id = int((post.source or "").split(":", 1)[1])
                    meta = db.scalar(select(OpportunitySourceMeta).where(OpportunitySourceMeta.opportunity_id == opportunity_id))
                    if meta and meta.published_at:
                        published_at = meta.published_at if meta.published_at.tzinfo else meta.published_at.replace(tzinfo=timezone.utc)
                        age_hours = (now - published_at.astimezone(timezone.utc)).total_seconds() / 3600
                        if age_hours > settings.social_realtime_max_age_hours:
                            log.warning("Skipping expired reactive social post %s (%.1fh old)", post.id, age_hours)
                            post.status = "archived"
                            post.updated_at = utcnow()
                            db.commit()
                            continue
                except (ValueError, TypeError):
                    pass
            try:
                if platform == "facebook":
                    publish_facebook_post(post.body)
                else:
                    media_url = _asset_for(post)
                    if not media_url:
                        log.error("Scheduled Instagram post %s has no usable image", post.id)
                        continue
                    post.media_url = media_url
                    publish_instagram_post(caption=post.body, image_url=media_url)
                    mark_used(media_url)
            except Exception:
                log.exception("Scheduled %s publish failed for post %s", platform, post.id)
                continue
            post.status = "published"
            post.updated_at = utcnow()
            db.commit()
            published += 1
    return published


async def social_publish_worker_loop() -> None:
    while True:
        try:
            publish_due_posts()
        except Exception:
            log.exception("Social publishing worker iteration failed")
        await asyncio.sleep(60)
