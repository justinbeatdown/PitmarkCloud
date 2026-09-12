from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.control_center import SocialPost, utcnow
from services.database import Base, SessionLocal
from services.meta_publish_service import (
    fetch_facebook_page_comments,
    fetch_instagram_comments,
    reply_facebook_comment,
    reply_instagram_comment,
)
from services.x_publish_service import fetch_mentions as fetch_x_mentions
from utils.config import settings

log = logging.getLogger(__name__)


class SocialEngagementEvent(Base):
    __tablename__ = "social_operator_engagement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(24), index=True)
    external_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    parent_external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(40), default="review", index=True)
    action_status: Mapped[str] = mapped_column(String(40), default="captured", index=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SocialOperatorRun(Base):
    __tablename__ = "social_operator_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30), default="started", index=True)
    scanned_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    replies_sent_count: Mapped[int] = mapped_column(Integer, default=0)
    posts_planned_count: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


FACEBOOK_PROMPTS = [
    "🏁 BUILD THE ULTIMATE DIRT TRACK\n\nYou get to build one track from scratch. Pick ONE thing for it:\n• Track length\n• Banking\n• Surface\n• Location\n• Weekly headline class\n• One must-have concession stand item 😂\n\nWe’ll build the track from the comments. What are you adding first?",
    "Track roll call 🏁\n\nDrop your home track + state in the comments. Bonus points if you tell us the one race there that everybody should see at least once.",
    "You get ONE rule change to make grassroots racing better tomorrow. What are you changing? 🏁\n\nNo wrong answers. We want to hear what racers and fans actually think.",
    "Unlimited budget. One race car. One track. What are you building and where are you taking it first? 🏁",
    "What’s one thing a race track does that instantly makes you want to come back? Could be the racing, food, announcing, pits, anything. 🏁",
    "Settle a race-night argument for us: feature winner from the front row or somebody charging from deep in the field—which is more fun to watch? 👀🏁",
]

X_PROMPTS = [
    "Build the ultimate dirt track. Pick ONE: length, banking, surface, location, headline class, or concession item. What are you adding first? 🏁",
    "Track roll call: what’s your home track + state? 🏁",
    "You get one rule change to make grassroots racing better tomorrow. What are you changing?",
    "Unlimited budget. One race car. One track. What are you building and where are you taking it first? 🏁",
    "What’s one thing a race track does that instantly makes you want to come back?",
]

_BLOCKED_REPLY_TERMS = {
    "refund", "chargeback", "order", "shipping", "lawsuit", "lawyer", "legal",
    "harassment", "threat", "scam", "fraud", "password", "account", "payment",
    "bug", "crash", "broken", "not working", "support", "cancel", "subscription",
}
_POSITIVE_TERMS = {
    "love", "awesome", "great", "nice", "cool", "sick", "badass", "amazing",
    "fire", "hell yeah", "thank", "thanks", "looks good", "dope", "sweet",
}
_LINK_TERMS = {
    "where can i get", "where do i get", "where can i find", "link?", "got a link",
    "where can i buy", "where do i buy", "download?", "where can i download",
}


def _local_now() -> datetime:
    try:
        zone = ZoneInfo(settings.pitmark_timezone)
    except Exception:
        zone = timezone.utc
    return datetime.now(zone)


def _pick(items: list[str], salt: str) -> str:
    digest = hashlib.sha256(salt.encode("utf-8", "ignore")).digest()
    return items[int.from_bytes(digest[:4], "big") % len(items)]


def _classify_reply(text: str) -> tuple[str, str | None]:
    body = " ".join((text or "").lower().split())
    if not body:
        return "ignore", None
    if any(term in body for term in _BLOCKED_REPLY_TERMS):
        return "review", None
    if any(term in body for term in _LINK_TERMS):
        return "safe", "Absolutely — the current Pitmark links are all here: https://links.pitmarkracing.com 🏁"
    if "?" in body:
        return "review", None
    if any(term in body for term in _POSITIVE_TERMS) or len(body) <= 12:
        return "safe", _pick(
            [
                "Appreciate you! 🏁",
                "Hell yeah — thanks for being here. 🏁",
                "That means a lot. Appreciate the support! 🏁",
                "Thanks! We’re having a blast building this thing. 🏁",
            ],
            body,
        )
    return "captured", None


def _record_event(
    *,
    platform: str,
    external_id: str,
    parent_external_id: str | None,
    author_name: str | None,
    body: str,
) -> tuple[SocialEngagementEvent | None, bool]:
    with SessionLocal() as db:
        existing = db.scalar(select(SocialEngagementEvent).where(SocialEngagementEvent.external_id == external_id))
        if existing:
            return None, False
        classification, suggested = _classify_reply(body)
        event = SocialEngagementEvent(
            platform=platform,
            external_id=external_id,
            parent_external_id=parent_external_id,
            author_name=author_name,
            body=body or "",
            classification=classification,
            action_status="ready" if suggested else ("review" if classification == "review" else "captured"),
            response=suggested,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event, True


def _mark_event(event_id: int, status: str, response: str | None = None) -> None:
    with SessionLocal() as db:
        event = db.get(SocialEngagementEvent, event_id)
        if not event:
            return
        event.action_status = status
        if response is not None:
            event.response = response
        event.updated_at = utcnow()
        db.commit()


def _sync_meta_engagement() -> tuple[int, int, int]:
    scanned = 0
    review = 0
    replied = 0

    try:
        facebook_items = fetch_facebook_page_comments(limit_posts=12, limit_comments=50)
    except Exception as exc:
        log.warning("Social Operator Facebook read failed: %s", exc)
        facebook_items = []

    for item in facebook_items:
        scanned += 1
        external_id = str(item.get("id") or "").strip()
        if not external_id:
            continue
        event, created = _record_event(
            platform="facebook",
            external_id=f"facebook:{external_id}",
            parent_external_id=str(item.get("post_id") or "") or None,
            author_name=str(item.get("author_name") or "") or None,
            body=str(item.get("message") or ""),
        )
        if not created or not event:
            continue
        if event.classification == "review":
            review += 1
        if settings.social_operator_auto_reply_enabled and event.action_status == "ready" and event.response:
            try:
                reply_facebook_comment(external_id, event.response)
                _mark_event(event.id, "replied", event.response)
                replied += 1
            except Exception as exc:
                log.warning("Social Operator Facebook reply failed for %s: %s", external_id, exc)
                _mark_event(event.id, "reply_failed")

    try:
        instagram_items = fetch_instagram_comments(limit_media=12, limit_comments=50)
    except Exception as exc:
        log.warning("Social Operator Instagram read failed: %s", exc)
        instagram_items = []

    for item in instagram_items:
        scanned += 1
        external_id = str(item.get("id") or "").strip()
        if not external_id:
            continue
        event, created = _record_event(
            platform="instagram",
            external_id=f"instagram:{external_id}",
            parent_external_id=str(item.get("media_id") or "") or None,
            author_name=str(item.get("author_name") or "") or None,
            body=str(item.get("message") or ""),
        )
        if not created or not event:
            continue
        if event.classification == "review":
            review += 1
        if settings.social_operator_auto_reply_enabled and event.action_status == "ready" and event.response:
            try:
                reply_instagram_comment(external_id, event.response)
                _mark_event(event.id, "replied", event.response)
                replied += 1
            except Exception as exc:
                log.warning("Social Operator Instagram reply failed for %s: %s", external_id, exc)
                _mark_event(event.id, "reply_failed")

    # Capture X mentions so the operator can surface them. V1 deliberately does not
    # auto-reply to mentions because context is wider than a comment on our own post.
    try:
        x_items = fetch_x_mentions(max_results=25)
    except Exception as exc:
        log.warning("Social Operator X mention read failed: %s", exc)
        x_items = []
    for item in x_items:
        scanned += 1
        external_id = str(item.get("id") or "").strip()
        if not external_id:
            continue
        _, created = _record_event(
            platform="x",
            external_id=f"x:{external_id}",
            parent_external_id=None,
            author_name=str(item.get("author_name") or item.get("author_id") or "") or None,
            body=str(item.get("text") or ""),
        )
        if created:
            review += 1
            # Mentions always remain operator-visible even if their language looks safe.
            with SessionLocal() as db:
                row = db.scalar(select(SocialEngagementEvent).where(SocialEngagementEvent.external_id == f"x:{external_id}"))
                if row:
                    row.classification = "review"
                    row.action_status = "review"
                    row.response = None
                    row.updated_at = utcnow()
                    db.commit()

    return scanned, review, replied


def _next_growth_slot(platform: str) -> datetime:
    now = _local_now()
    slots = {
        "facebook": [(11, 15), (15, 30), (20, 15)],
        "x": [(10, 45), (18, 45), (21, 15)],
    }.get(platform, [(12, 0)])
    for hour, minute in slots:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate > now + timedelta(minutes=20):
            return candidate
    tomorrow = now + timedelta(days=1)
    hour, minute = slots[0]
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _recent_platform_post_count(platform: str) -> int:
    cutoff = utcnow() - timedelta(hours=20)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost).where(
                    SocialPost.platform == platform,
                    SocialPost.status.in_(["pending", "approved", "scheduled", "published"]),
                    SocialPost.created_at >= cutoff,
                )
            ).all()
        )
    return len(rows)


def _operator_post_exists(platform: str, scheduled_day: str) -> bool:
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost).where(
                    SocialPost.platform == platform,
                    SocialPost.source == "operator:growth-loop",
                    SocialPost.status.in_(["pending", "approved", "scheduled", "published"]),
                )
            ).all()
        )
    return any((row.scheduled_for or "").startswith(scheduled_day) for row in rows)


def _ensure_growth_posts() -> int:
    if not settings.social_operator_growth_posts_enabled:
        return 0

    planned = 0
    targets = {
        "facebook": max(0, int(settings.social_operator_min_facebook_posts_daily)),
        "x": max(0, int(settings.social_operator_min_x_posts_daily)),
    }
    now = _local_now()
    for platform, minimum in targets.items():
        if minimum <= 0 or _recent_platform_post_count(platform) >= minimum:
            continue
        schedule = _next_growth_slot(platform)
        day_key = schedule.date().isoformat()
        if _operator_post_exists(platform, day_key):
            continue
        prompts = FACEBOOK_PROMPTS if platform == "facebook" else X_PROMPTS
        body = _pick(prompts, f"{platform}:{day_key}")
        status = "scheduled" if settings.social_operator_autopublish_low_risk else "pending"
        with SessionLocal() as db:
            db.add(
                SocialPost(
                    platform=platform,
                    title="Social Operator growth prompt",
                    body=body,
                    content_type="community",
                    source="operator:growth-loop",
                    risk="low",
                    status=status,
                    scheduled_for=schedule.isoformat(),
                )
            )
            db.commit()
        planned += 1
        log.info("Social Operator planned %s growth post for %s", platform, schedule.isoformat())
    return planned


def run_operator_once() -> dict:
    run_id = None
    with SessionLocal() as db:
        run = SocialOperatorRun(status="started")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    try:
        scanned, review, replied = _sync_meta_engagement()
        planned = _ensure_growth_posts()
        with SessionLocal() as db:
            run = db.get(SocialOperatorRun, run_id)
            if run:
                run.status = "complete"
                run.scanned_count = scanned
                run.review_count = review
                run.replies_sent_count = replied
                run.posts_planned_count = planned
                run.note = "Safe comment replies are autonomous; questions/support-sensitive items and X mentions stay in review."
                db.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "scanned": scanned,
            "review": review,
            "replied": replied,
            "posts_planned": planned,
        }
    except Exception as exc:
        log.exception("Social Operator run failed")
        with SessionLocal() as db:
            run = db.get(SocialOperatorRun, run_id)
            if run:
                run.status = "failed"
                run.note = str(exc)[:1000]
                db.commit()
        return {"ok": False, "run_id": run_id, "error": str(exc)}


def operator_status() -> dict:
    with SessionLocal() as db:
        latest = db.scalar(select(SocialOperatorRun).order_by(SocialOperatorRun.id.desc()).limit(1))
        review_rows = list(
            db.scalars(
                select(SocialEngagementEvent)
                .where(SocialEngagementEvent.action_status == "review")
                .order_by(SocialEngagementEvent.id.desc())
                .limit(25)
            ).all()
        )
    return {
        "enabled": settings.social_operator_enabled,
        "auto_reply_enabled": settings.social_operator_auto_reply_enabled,
        "growth_posts_enabled": settings.social_operator_growth_posts_enabled,
        "autopublish_low_risk": settings.social_operator_autopublish_low_risk,
        "minimum_daily": {
            "facebook": settings.social_operator_min_facebook_posts_daily,
            "x": settings.social_operator_min_x_posts_daily,
            "instagram": 0,
        },
        "latest_run": None
        if not latest
        else {
            "id": latest.id,
            "status": latest.status,
            "scanned": latest.scanned_count,
            "review": latest.review_count,
            "replied": latest.replies_sent_count,
            "posts_planned": latest.posts_planned_count,
            "note": latest.note,
            "created_at": latest.created_at.isoformat() if latest.created_at else None,
        },
        "review_queue": [
            {
                "id": row.id,
                "platform": row.platform,
                "author_name": row.author_name,
                "body": row.body,
                "classification": row.classification,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in review_rows
        ],
        "guardrails": [
            "No autonomous replies to refunds, orders, payments, legal/security, support or bug reports.",
            "Questions that need product/context knowledge go to review.",
            "X mentions are captured for review, not auto-replied in v1.",
            "Operator fills posting gaps instead of stacking posts on already-active days.",
            "Facebook Groups sharing and invite-to-follow remain manual because the official APIs do not provide a safe general automation path.",
        ],
    }


async def social_operator_loop() -> None:
    # Give the rest of Cloud time to initialize before the first social read/write pass.
    await asyncio.sleep(45)
    while True:
        try:
            if settings.social_operator_enabled:
                result = await asyncio.to_thread(run_operator_once)
                if result.get("scanned") or result.get("replied") or result.get("posts_planned"):
                    log.info("Social Operator: %s", result)
        except Exception:
            log.exception("Social Operator background iteration failed")
        await asyncio.sleep(max(120, int(settings.social_operator_poll_seconds)))
