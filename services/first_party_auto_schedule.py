from __future__ import annotations

import os
import re
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

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
PREVIEW_TERMS = ("where to watch", "preview", "lineup", "schedule", "coming up", "this weekend", "what to watch", "race weekend")
RESULT_TERMS = ("results", "recap", "winner", " won ", "victory", "champion crowned", "post-race", "after the race")


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


def _extract_event_window(posts: list[SocialPost], now_local: datetime) -> tuple[datetime | None, datetime | None]:
    text = " ".join(
        f"{post.title or ''} {post.body or ''}"
        for post in posts
    ).lower()
    # Examples: Sept. 18-26, September 18 at 7:30 PM, Sept 18 through 26.
    m = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})(?:\s*(?:-|–|—|to|through)\s*(\d{1,2}))?",
        text,
        re.I,
    )
    if not m:
        return None, None
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return None, None
    year = now_local.year
    start_day = int(m.group(2))
    end_day = int(m.group(3) or start_day)
    try:
        start = datetime(year, month, start_day, 0, 0, tzinfo=now_local.tzinfo)
        end = datetime(year, month, end_day, 23, 59, tzinfo=now_local.tzinfo)
    except ValueError:
        return None, None

    # Pull an explicit clock time near the date when one is present. Treat that as
    # the true event start instead of pretending the whole date is one giant window.
    nearby = text[m.end():m.end() + 140]
    clock = re.search(
        r"(?:\bat\s+|\b)(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b",
        nearby,
        re.I,
    )
    if clock:
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        marker = clock.group(3).lower().replace(".", "")
        if marker == "pm" and hour != 12:
            hour += 12
        if marker == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            start = start.replace(hour=hour, minute=minute)
            if not m.group(3):
                # A single race-night start gets a bounded event window so preview
                # copy can never be scheduled halfway through the program.
                end = min(end, start + timedelta(hours=6))

    # Handle year rollover for December content created in January and vice versa.
    if start < now_local - timedelta(days=180):
        try:
            start = start.replace(year=year + 1)
            end = end.replace(year=year + 1)
        except ValueError:
            pass
    elif start > now_local + timedelta(days=180):
        try:
            start = start.replace(year=year - 1)
            end = end.replace(year=year - 1)
        except ValueError:
            pass
    return start, end

def _content_timing(posts: list[SocialPost], now_local: datetime) -> dict:
    text = " ".join(f"{post.title or ''} {post.body or ''}" for post in posts).lower()
    start, end = _extract_event_window(posts, now_local)
    kind = "evergreen"
    if any(term in text for term in RESULT_TERMS):
        kind = "result"
    elif any(term in text for term in PREVIEW_TERMS) or start:
        kind = "preview"
    return {"kind": kind, "start": start, "end": end}


def _is_collision(slot: datetime, occupied: list[datetime], collision_minutes: int) -> bool:
    return any(abs((slot - existing).total_seconds()) < collision_minutes * 60 for existing in occupied)


def _candidate_slots(now_local: datetime, days: int = 8) -> list[datetime]:
    minimum = now_local + timedelta(minutes=_env_int("PITMARK_FIRST_PARTY_MIN_LEAD_MINUTES", 15, 5, 180))
    slots: list[datetime] = []
    for day_offset in range(0, max(1, days)):
        day = (now_local + timedelta(days=day_offset)).date()
        for hour in _post_hours():
            slot = datetime(day.year, day.month, day.day, hour, 0, tzinfo=now_local.tzinfo)
            if slot >= minimum:
                slots.append(slot)
    return slots


def _choose_campaign_slot(now_local: datetime, occupied: list[datetime], posts: list[SocialPost]) -> tuple[datetime | None, str]:
    collision_minutes = _env_int("PITMARK_FIRST_PARTY_SLOT_COLLISION_MINUTES", 75, 15, 240)
    lead_minutes = _env_int("PITMARK_FIRST_PARTY_MIN_LEAD_MINUTES", 15, 5, 180)
    timing = _content_timing(posts, now_local)
    candidates = _candidate_slots(now_local, 8)

    if timing["kind"] == "preview" and timing["end"]:
        candidates = [slot for slot in candidates if slot <= timing["end"]]
        if timing["start"]:
            if now_local >= timing["start"]:
                return None, "event already started; preview was not posted mid-event"
            before = [slot for slot in candidates if slot < timing["start"]]
            if before:
                candidates = before
            else:
                # Fixed posting hours may leave no slot before a nearby event.
                # Use the earliest safe lead-time slot instead of waiting until the race is underway.
                urgent = now_local + timedelta(minutes=lead_minutes)
                if urgent < timing["start"] and not _is_collision(urgent, occupied, collision_minutes):
                    return urgent, "urgent pre-event"
                return None, "no safe pre-event slot remains"
        if not candidates:
            return None, "event window expired or no pre-event slot remains"

    if timing["kind"] == "result":
        anchor = timing["end"] or timing["start"]
        if anchor and now_local < anchor:
            candidates = [slot for slot in candidates if slot >= anchor]

    for slot in candidates:
        if not _is_collision(slot, occupied, collision_minutes):
            return slot, timing["kind"]
    return None, "no safe event-aware slot available"

def _repair_time_sensitive_schedules(db, now: datetime) -> list[dict]:
    zone = _timezone()
    now_local = now.astimezone(zone)
    scheduled = list(db.scalars(select(SocialPost).where(
        SocialPost.status == "scheduled",
        SocialPost.source.like("firstparty:%"),
        SocialPost.platform.in_(SUPPORTED_PLATFORMS),
        SocialPost.scheduled_for.is_not(None),
    )).all())
    grouped: dict[str, list[SocialPost]] = {}
    for post in scheduled:
        grouped.setdefault(str(post.source or ""), []).append(post)

    occupied = [
        parsed.astimezone(zone)
        for parsed in (_parse_dt(post.scheduled_for) for post in scheduled)
        if parsed
    ]
    repaired: list[dict] = []
    for source, posts in grouped.items():
        current = _parse_dt(posts[0].scheduled_for)
        if not current:
            continue
        current_local = current.astimezone(zone)
        timing = _content_timing(posts, now_local)
        if timing["kind"] != "preview" or not timing["end"]:
            continue
        bad = current_local > timing["end"] or (
            timing["start"] and current_local >= timing["start"]
        )
        if not bad:
            continue
        occupied = [x for x in occupied if abs((x - current_local).total_seconds()) > 60]
        replacement, reason = _choose_campaign_slot(now_local, occupied, posts)
        if not replacement:
            for post in posts:
                # An expired preview is no longer actionable content. Archive it
                # instead of dumping stale race promotion back into the approval queue.
                post.status = "archived"
                post.scheduled_for = None
                post.updated_at = utcnow()
            repaired.append({"source": source, "action": "archived", "reason": reason})
            continue
        replacement_iso = replacement.isoformat()
        for post in posts:
            post.scheduled_for = replacement_iso
            post.updated_at = utcnow()
        occupied.append(replacement)
        repaired.append({"source": source, "action": "rescheduled", "scheduled_for": replacement_iso, "reason": "event-aware timing"})
    return repaired


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

    Existing backlog is preserved on first boot. Low-risk verified firstparty:* posts
    for Facebook, Instagram, and X are eligible here. Fresh reactive racing news
    and engagement prompts use the separate low-risk social autonomy lane.
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
        # Repair bad timing on already-scheduled event content even when there are
        # no new pending campaigns. This must happen before the early return below.
        repaired = _repair_time_sensitive_schedules(db, now)

        candidates = list(db.scalars(select(SocialPost).where(
            SocialPost.status == "pending",
            SocialPost.source.like("firstparty:%"),
            SocialPost.platform.in_(SUPPORTED_PLATFORMS),
            SocialPost.risk == "low",
            SocialPost.created_at > cutoff,
        ).order_by(SocialPost.id.asc()).limit(60)).all())
        if not candidates:
            if repaired:
                db.commit()
            return {"enabled": True, "mode": mode, "scheduled_campaigns": 0, "scheduled_posts": 0, "repaired": repaired}
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
        zone = _timezone()
        now_local = now.astimezone(zone)
        occupied = []
        for raw in scheduled_values:
            parsed = _parse_dt(raw)
            if parsed:
                occupied.append(parsed.astimezone(zone))

        # Rebuild occupied after repairs.
        occupied = []
        for raw in db.scalars(select(SocialPost.scheduled_for).where(
            SocialPost.status == "scheduled",
            SocialPost.scheduled_for.is_not(None),
        )).all():
            parsed = _parse_dt(raw)
            if parsed:
                occupied.append(parsed.astimezone(zone))

        scheduled_posts = 0
        assignments = []
        skipped = []
        # Time-sensitive campaigns first; evergreen content can wait.
        sources.sort(key=lambda key: 0 if _content_timing(grouped[key], now_local)["kind"] != "evergreen" else 1)
        for key in sources:
            posts = grouped[key]
            slot, timing_reason = _choose_campaign_slot(now_local, occupied, posts)
            if not slot:
                skipped.append({"source": key, "reason": timing_reason})
                continue
            slot_iso = slot.isoformat()
            platforms = []
            for post in posts:
                post.status = "scheduled"
                post.scheduled_for = slot_iso
                post.updated_at = utcnow()
                platforms.append(post.platform)
                scheduled_posts += 1
            occupied.append(slot)
            assignments.append({"source": key, "scheduled_for": slot_iso, "platforms": sorted(platforms), "timing": timing_reason})
        if scheduled_posts or repaired:
            db.commit()
    return {"enabled": True, "mode": mode, "scheduled_campaigns": len(assignments), "scheduled_posts": scheduled_posts, "assignments": assignments, "repaired": repaired, "skipped": skipped}
