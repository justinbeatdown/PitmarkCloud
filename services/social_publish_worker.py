from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.meta_publish_service import configured, publish_facebook_post
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


def publish_due_posts() -> int:
    if not configured():
        return 0

    now = datetime.now(timezone.utc)
    published = 0

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost)
                .where(
                    SocialPost.status == "scheduled",
                    SocialPost.platform == "facebook",
                )
                .order_by(SocialPost.id.asc())
            ).all()
        )

        for post in rows:
            due = _scheduled_time(post.scheduled_for)
            if due is None or due > now:
                continue

            try:
                publish_facebook_post(post.body)
            except Exception:
                log.exception("Scheduled Facebook publish failed for post %s", post.id)
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
