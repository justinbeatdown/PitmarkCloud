from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from services.autonomy_control import effective_mode
from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.first_party_models import get_state, set_state
from utils.config import settings

SUPPORTED_PLATFORMS = ("facebook", "instagram", "x")
STATE_BOOTSTRAP_AT = "first_party_auto_schedule_bootstrap_at"


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name) or default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.pitmark_timezone)
    except Exception:
        return ZoneInfo("America/New_York")


def _post_hours() -> tuple[int, ...]:
    raw = (os.getenv("PITMARK_FIRST_PARTY_POST_HOURS") or "10,14,18").strip()
    hours: list[int] = []
    for item in raw.split(","):
        try:
            hour = int(item.strip())
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23 and hour not in hours:
            hours.append(hour)
    return tuple(sorted(hours)) or (10, 14, 18)


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _available_slots(now_utc: datetime, scheduled_values: list[str | None], needed: int) -> list[datetime]:
    zone = _timezone()
    now_local = now_utc.astimezone(zone)
    minimum = now_local + timedelta(minutes=_env_int("PITMARK_FIRST_PARTY_MIN_LEAD_MINUTES", 15, 5, 180))
    collision_minutes = _env_int("PITMARK_FIRST_PARTY_SLOT_COLLISION_MINUTES", 75, 15, 240)
    occupied: list[datetime] = []
    for raw in scheduled_values:
        parsed = _parse_dt(raw)
        if parsed:
            occupied.append(parsed.astimezone(zone))
    slots: list[datetime] = []
    for day_offset in range(0, 8):
        day = (now_local + timedelta(days=day_offset)).date()
        for hour in _post_hours():
            slot = datetime(day.year, day.month, day.day, hour, 0, tzinfo=zone)
            if slot < minimum:
                continue
            if any(abs((slot - existing).total_seconds()) < collision_minutes * 60 for existing in occupied):
                continue
            slots.append(slot)
            occupied.append(slot)
            if len(slots) >= needed:
                return slots
    return slots


def auto_schedule_verified_first_party() -> dict:
    """Schedule only newly-created, verified first-party Pitmark campaigns.

    Existing backlog is preserved on first boot. Only low-risk firstparty:* posts
    for Facebook, Instagram, and X are eligible. Reactive intelligence, manual
    posts, TikTok, and Discord remain human-controlled.
    """
    now = datetime.now(timezone.utc)
    bootstrap_raw = get_state(STATE_BOOTSTRAP_AT)
    if not bootstrap_raw:
        set_state(STATE_BOOTSTRAP_AT, now.isoformat())
        return {"enabled": True, "bootstrapped": True, "scheduled_campaigns": 0, "scheduled_posts": 0, "reason": "existing backlog preserved for human review"}
    bootstrap_at = _parse_dt(bootstrap_raw)
    if bootstrap_at is None:
        set_state(STATE_BOOTSTRAP_AT, now.isoformat())
        return {"enabled": True, "bootstrapped": True, "scheduled_campaigns": 0, "scheduled_posts": 0, "reason": "invalid bootstrap state reset safely"}
    mode = effective_mode("first_party_social_publish", uncertainty=0.05, fallback="auto")
    if mode != "auto":
        return {"enabled": False, "mode": mode, "scheduled_campaigns": 0, "scheduled_posts": 0}
    max_age_hours = _env_int("PITMARK_FIRST_PARTY_AUTO_MAX_AGE_HOURS", 72, 1, 168)
    cutoff = max(bootstrap_at, now - timedelta(hours=max_age_hours))
    max_campaigns = _env_int("PITMARK_FIRST_PARTY_AUTO_CAMPAIGNS_PER_PASS", 3, 1, 6)
    with SessionLocal() as db:
        candidates = list(db.scalars(select(SocialPost).where(
            SocialPost.status == "pending",
            SocialPost.source.like("firstparty:%"),
            SocialPost.platform.in_(SUPPORTED_PLATFORMS),
            SocialPost.risk == "low",
            SocialPost.created_at > cutoff,
        ).order_by(SocialPost.id.asc()).limit(60)).all())
        if not candidates:
            return {"enabled": True, "mode": mode, "scheduled_campaigns": 0, "scheduled_posts": 0}
        scheduled_values = list(db.scalars(select(SocialPost.scheduled_for).where(
            SocialPost.status == "scheduled",
            SocialPost.scheduled_for.is_not(None),
        )).all())
        sources: list[str] = []
        grouped: dict[str, list[SocialPost]] = {}
        for post in candidates:
            key = str(post.source or "")
            if key not in grouped:
                if len(sources) >= max_campaigns:
                    continue
                sources.append(key)
                grouped[key] = []
            grouped[key].append(post)
        slots = _available_slots(now, scheduled_values, len(sources))
        if not slots:
            return {"enabled": True, "mode": mode, "scheduled_campaigns": 0, "scheduled_posts": 0, "reason": "no safe posting slot available"}
        scheduled_posts = 0
        assignments = []
        for key, slot in zip(sources, slots):
            posts = grouped[key]
            slot_iso = slot.isoformat()
            platforms = []
            for post in posts:
                post.status = "scheduled"
                post.scheduled_for = slot_iso
                post.updated_at = utcnow()
                platforms.append(post.platform)
                scheduled_posts += 1
            assignments.append({"source": key, "scheduled_for": slot_iso, "platforms": sorted(platforms)})
        if scheduled_posts:
            db.commit()
    return {"enabled": True, "mode": mode, "scheduled_campaigns": len(assignments), "scheduled_posts": scheduled_posts, "assignments": assignments}
