from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from services.autopilot_ai import compose_with_ai
from services.control_center import AutopilotOpportunity, SocialPost
from services.database import SessionLocal

log = logging.getLogger("pitmark.autopilot.multiplatform")

PLATFORMS = ("instagram", "x")


def _opportunity_id(source: str | None) -> int | None:
    raw = str(source or "")
    if not raw.startswith("intelligence:"):
        return None
    try:
        return int(raw.split(":", 1)[1])
    except (TypeError, ValueError):
        return None


def backfill_platform_variants(limit: int = 6) -> dict:
    """Create platform-native Instagram/X variants for intelligence posts.

    Facebook remains one useful output, but it is no longer the only platform
    Autopilot prepares. Existing manual posts are never cloned automatically.
    """
    created = 0
    checked = 0
    with SessionLocal() as db:
        facebook_rows = list(
            db.scalars(
                select(SocialPost)
                .where(
                    SocialPost.platform == "facebook",
                    SocialPost.source.like("intelligence:%"),
                    SocialPost.status.in_(["pending", "approved", "scheduled"]),
                )
                .order_by(SocialPost.id.desc())
                .limit(20)
            ).all()
        )

        for source_post in facebook_rows:
            if created >= max(1, min(limit, 12)):
                break
            checked += 1
            opportunity_id = _opportunity_id(source_post.source)
            opportunity = db.get(AutopilotOpportunity, opportunity_id) if opportunity_id else None
            headline = opportunity.headline if opportunity else ""
            context = headline or source_post.body

            for platform in PLATFORMS:
                if created >= max(1, min(limit, 12)):
                    break
                exists = db.scalar(
                    select(SocialPost.id).where(
                        SocialPost.platform == platform,
                        SocialPost.source == source_post.source,
                        ~SocialPost.status.in_(["rejected", "archived"]),
                    )
                )
                if exists:
                    continue

                prompt = (
                    "Create a platform-native Pitmark Racing Co. post based on this "
                    "already-approved intelligence context. Do not invent facts, imply "
                    "Pitmark involvement, or copy the Facebook wording. Keep the same "
                    "story idea but write for the selected platform. Context: "
                    f"{context}"
                )
                try:
                    ai = compose_with_ai(
                        platform=platform,
                        goal=source_post.content_type or "community",
                        prompt=prompt,
                        tone="pitmark",
                    )
                except Exception as exc:
                    log.warning("Multiplatform variant failed for %s: %s", platform, exc)
                    continue

                db.add(
                    SocialPost(
                        platform=platform,
                        title=source_post.title,
                        body=ai.body,
                        content_type=source_post.content_type or "community",
                        source=source_post.source,
                        risk=source_post.risk or "low",
                        status="pending",
                        media_url=None,
                    )
                )
                created += 1

        if created:
            db.commit()

    return {"checked": checked, "created": created, "platforms": list(PLATFORMS)}


async def scheduler_loop():
    # Give Pitmark Cloud and the normal intelligence scheduler time to start.
    await asyncio.sleep(75)
    while True:
        try:
            await asyncio.to_thread(backfill_platform_variants)
        except Exception:
            log.exception("Autopilot multiplatform backfill failed")
        await asyncio.sleep(300)
