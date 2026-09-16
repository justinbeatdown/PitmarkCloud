from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from services.autopilot_ai import compose_with_ai
from services.control_center import AutopilotOpportunity, SocialPost
from services.database import SessionLocal
from services.first_party_autopilot import scan_and_generate as scan_first_party_events
from services.first_party_auto_schedule import auto_schedule_verified_first_party
from services.discord_racing_culture_feed import sync_racing_culture_feed
from services.social_daily_campaign import ensure_daily_campaign
from services.social_daily_package import generate_daily_package
from utils.config import settings

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
    # Start before the Social Operator gap-filler pass so the daily campaign owns
    # today's coverage whenever it can be generated safely.
    await asyncio.sleep(20)
    while True:
        try:
            await asyncio.to_thread(backfill_platform_variants)
        except Exception:
            log.exception("Autopilot multiplatform backfill failed")

        # First-party Autopilot watches Pitmark itself: product drops, PRT releases,
        # published blogs, partnership/street-team changes, and useful milestones.
        try:
            result = await asyncio.to_thread(scan_first_party_events)
            if result.get("queued") or (result.get("processed") or {}).get("attempted"):
                log.info(
                    "First-party Autopilot: queued=%s processed=%s",
                    result.get("queued", 0),
                    (result.get("processed") or {}).get("attempted", 0),
                )
        except Exception:
            log.exception("First-party Autopilot scan failed")

        # Social Operations owns one coherent campaign per local day. The campaign
        # reuses verified first-party events when available and falls back to a safe
        # community-growth concept. Repeated passes are idempotent.
        if settings.social_daily_campaign_enabled:
            try:
                campaign = await asyncio.to_thread(ensure_daily_campaign)
                daily = await asyncio.to_thread(generate_daily_package, campaign["id"])
                progress = daily.get("progress") or {}
                log.info(
                    "Daily Social Campaign: id=%s topic=%s copy=%s/%s ig=%s/%s vertical=%s/%s complete=%s",
                    campaign.get("id"),
                    campaign.get("topic_type"),
                    progress.get("copy_ready", 0),
                    progress.get("copy_total", 5),
                    progress.get("ig_assets_ready", 0),
                    progress.get("ig_assets_total", 6),
                    progress.get("vertical_assets_ready", 0),
                    progress.get("vertical_assets_total", 4),
                    progress.get("complete", False),
                )
            except Exception:
                log.exception("Daily Social Campaign generation failed")

        # Keep the Pitmark Discord community synced with newly published Racing Culture
        # articles. This creates #racing-culture under the Racing Community category when
        # the bot can manage channels, and safely falls back to #community-events.
        try:
            discord_feed = await sync_racing_culture_feed()
            if discord_feed.get("posted") or discord_feed.get("created_channel"):
                log.info(
                    "Discord Racing Culture feed: channel=%s posted=%s created=%s fallback=%s",
                    discord_feed.get("channel"),
                    discord_feed.get("posted", 0),
                    discord_feed.get("created_channel", False),
                    discord_feed.get("fallback", False),
                )
        except Exception:
            log.exception("Discord Racing Culture feed sync failed")

        # Verified first-party campaigns can be scheduled automatically under their
        # own narrow autonomy policy. The scheduler bootstraps without touching any
        # existing backlog, and never handles intelligence/manual/TikTok/Discord.
        try:
            scheduled = await asyncio.to_thread(auto_schedule_verified_first_party)
            if scheduled.get("scheduled_posts"):
                log.info(
                    "First-party auto-schedule: campaigns=%s posts=%s",
                    scheduled.get("scheduled_campaigns", 0),
                    scheduled.get("scheduled_posts", 0),
                )
        except Exception:
            log.exception("First-party auto-schedule failed")

        await asyncio.sleep(300)
