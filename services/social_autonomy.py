from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from services.autonomy_control import effective_mode
from services.control_center import AutopilotOpportunity, OpportunitySourceMeta, SocialPost, utcnow
from services.database import SessionLocal
from services.social_pacing import pacing_decision
from services.social_quality_gate import assess_automatic_post_quality
from utils.config import settings

log = logging.getLogger("pitmark.social.autonomy")

_AUTONOMOUS_SOURCES = (
    "operator:growth-loop",
    "control_center:auto",
)
_AUTONOMOUS_PREFIXES = (
    "intelligence:",
    "firstparty:",
    "dailycampaign:",
)

# Anything in these lanes can still become a post, but it does not go out unattended.
# These are exactly the kinds of claims where a bad headline or spoofed source can
# damage the brand much faster than a missed post.
_SENSITIVE_TERMS = (
    " died", " death", " dead", " killed", " fatal", " blood", " hospitalized",
    " hospital", " medical", " diagnosis", " diagnosed", " cancer", " injury",
    " injured", " arrest", " arrested", " charged", " lawsuit", " legal action",
    " allegation", " alleged", " accused", " assault", " abuse", " scandal",
    " suspension", " suspended", " banned", " investigation",
)


def _is_autonomous_source(source: str | None) -> bool:
    raw = str(source or "").strip()
    return raw in _AUTONOMOUS_SOURCES or raw.startswith(_AUTONOMOUS_PREFIXES)


def _is_sensitive(post: SocialPost, opportunity: AutopilotOpportunity | None) -> bool:
    text = " " + " ".join(
        str(value or "") for value in (
            post.title,
            post.body,
            opportunity.headline if opportunity else "",
        )
    ).lower()
    return any(term in text for term in _SENSITIVE_TERMS)


def _opportunity_for(db, post: SocialPost) -> tuple[AutopilotOpportunity | None, OpportunitySourceMeta | None]:
    source = str(post.source or "")
    if not source.startswith("intelligence:"):
        return None, None
    try:
        opportunity_id = int(source.split(":", 1)[1])
    except (TypeError, ValueError):
        return None, None
    return db.get(AutopilotOpportunity, opportunity_id), db.scalar(
        select(OpportunitySourceMeta).where(OpportunitySourceMeta.opportunity_id == opportunity_id)
    )


def _archive_if_stale(post: SocialPost, meta: OpportunitySourceMeta | None, now: datetime) -> bool:
    if not str(post.source or "").startswith("intelligence:"):
        return False
    if meta and meta.published_at:
        published = meta.published_at if meta.published_at.tzinfo else meta.published_at.replace(tzinfo=timezone.utc)
        age_hours = (now - published.astimezone(timezone.utc)).total_seconds() / 3600
        max_age = (settings.x_realtime_max_age_minutes / 60.0) if post.platform == "x" else settings.social_realtime_max_age_hours
        if age_hours > max_age:
            post.status = "archived"
            post.scheduled_for = None
            post.updated_at = utcnow()
            return True
    return False


def auto_schedule_pending_social(limit: int = 60) -> dict:
    """Turn safe automatic backlog into scheduled work without a human approval click.

    This is the default Pitmark social lane: low-risk automatic content publishes on
    its own. Sensitive claims, failed quality checks, unsupported IG carousels, and
    stale reactive news remain held or are archived instead of being blindly posted.
    """
    mode = effective_mode("low_risk_social_publish", uncertainty=0.05, fallback="auto")
    if mode != "auto":
        return {"enabled": False, "mode": mode, "scheduled": 0, "held": 0, "archived": 0}

    now = datetime.now(timezone.utc)
    scheduled = held = archived = 0
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost)
                .where(
                    SocialPost.status == "pending",
                    SocialPost.risk == "low",
                    SocialPost.platform.in_(["facebook", "instagram", "x"]),
                )
                .order_by(SocialPost.id.asc())
                .limit(max(1, min(limit, 200)))
            ).all()
        )
        for post in rows:
            if not _is_autonomous_source(post.source):
                continue

            opportunity, meta = _opportunity_for(db, post)
            if _archive_if_stale(post, meta, now):
                archived += 1
                continue

            if _is_sensitive(post, opportunity):
                post.risk = "needs_review"
                post.updated_at = utcnow()
                held += 1
                continue

            if post.platform == "instagram" and str(post.source or "").startswith("dailycampaign:"):
                # Preserve the real six-slide package until carousel publishing exists.
                held += 1
                continue

            # Never fill an unattended post with a loosely matched or randomly
            # selected asset. Only media explicitly assigned by its source may
            # pass the automatic Instagram quality gate below.
            quality = assess_automatic_post_quality(
                platform=post.platform,
                title=post.title,
                body=post.body,
                source=post.source,
                media_url=post.media_url,
            )
            if not quality["ok"]:
                post.risk = "needs_review"
                post.updated_at = utcnow()
                held += 1
                continue

            candidate = now + timedelta(minutes=3 + min(scheduled, 5) * 4)
            allowed, reason = pacing_decision(
                db,
                platform=post.platform,
                candidate=candidate,
                priority=str(post.source or "").startswith("intelligence:"),
            )
            if not allowed:
                log.info("Autonomous social held post %s for pacing: %s", post.id, reason)
                continue

            post.status = "scheduled"
            post.scheduled_for = candidate.isoformat()
            post.updated_at = utcnow()
            scheduled += 1

        if scheduled or held or archived:
            db.commit()

    return {
        "enabled": True,
        "mode": mode,
        "scheduled": scheduled,
        "held": held,
        "archived": archived,
    }
