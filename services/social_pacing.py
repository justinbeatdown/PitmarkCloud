from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from services.control_center import SocialPost
from utils.config import settings

AUTOMATED_SOURCE_PREFIXES = ("dailycampaign:", "firstparty:", "operator:", "intelligence:")
ACTIVE_STATUSES = ("scheduled", "published")
DEFAULT_DAILY_CAP = 3
BUSY_DAY_CAP = 5
DEFAULT_MIN_GAP_MINUTES = 120


def _zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.pitmark_timezone)
    except Exception:
        return ZoneInfo("America/New_York")


def _parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _effective_time(row: SocialPost) -> datetime | None:
    return _parse_dt(row.scheduled_for) or _parse_dt(row.updated_at) or _parse_dt(row.created_at)


def _is_automated(row: SocialPost) -> bool:
    source = str(row.source or "")
    return source.startswith(AUTOMATED_SOURCE_PREFIXES)


def platform_day_rows(db, platform: str, candidate: datetime) -> list[SocialPost]:
    zone = _zone()
    local_candidate = candidate.astimezone(zone)
    day = local_candidate.date()
    rows = list(db.scalars(select(SocialPost).where(
        SocialPost.platform == platform,
        SocialPost.status.in_(ACTIVE_STATUSES),
    )).all())
    result = []
    for row in rows:
        when = _effective_time(row)
        if when and when.astimezone(zone).date() == day:
            result.append(row)
    return result


def pacing_decision(
    db,
    *,
    platform: str,
    candidate: datetime,
    priority: bool = False,
    min_gap_minutes: int = DEFAULT_MIN_GAP_MINUTES,
) -> tuple[bool, str]:
    rows = platform_day_rows(db, platform, candidate)
    cap = BUSY_DAY_CAP if priority else DEFAULT_DAILY_CAP
    if len(rows) >= cap:
        return False, f"daily platform cap reached ({len(rows)}/{cap})"

    zone = _zone()
    proposed = candidate.astimezone(zone)
    for row in rows:
        when = _effective_time(row)
        if not when:
            continue
        delta = abs((proposed - when.astimezone(zone)).total_seconds())
        if delta < min_gap_minutes * 60:
            return False, f"minimum spacing not met ({min_gap_minutes}m)"

    manual_rows = [row for row in rows if not _is_automated(row)]
    if manual_rows and not priority:
        latest_manual = max(
            (_effective_time(row) for row in manual_rows if _effective_time(row)),
            default=None,
        )
        if latest_manual is not None:
            delta = (proposed - latest_manual.astimezone(zone)).total_seconds()
            if 0 <= delta < (min_gap_minutes + 60) * 60:
                return False, "recent manual post suppresses automated post"

    return True, "ok"


def facebook_publish_decision(db, candidate_post: SocialPost, now: datetime) -> tuple[bool, str]:
    """Final outbound gate. Count *actual* publishes, not planned records.

    Scheduling rules alone cannot protect against preexisting queues or direct
    writes to scheduled status. This must run immediately before Meta is called.
    """
    zone = _zone()
    today = now.astimezone(zone).date()
    published = list(db.scalars(select(SocialPost).where(
        SocialPost.platform == "facebook",
        SocialPost.status == "published",
    )).all())
    today_rows = []
    for post in published:
        when = _parse_dt(post.updated_at) or _parse_dt(post.created_at)
        if when and when.astimezone(zone).date() == today:
            today_rows.append(when)

    # Absolute outbound ceiling: campaign priority must NEVER raise the hard cap.
    # This is a safety gate for Control Center-originated publishes; Metricool
    # publications must also be accounted for by the coordinator.
    cap = BUSY_DAY_CAP
    if len(today_rows) >= cap:
        return False, f"daily published Facebook cap reached ({len(today_rows)}/{cap})"
    if today_rows:
        latest = max(today_rows)
        gap = (now - latest).total_seconds()
        if gap < DEFAULT_MIN_GAP_MINUTES * 60:
            return False, f"minimum published-post spacing not met ({DEFAULT_MIN_GAP_MINUTES}m)"
    return True, "ok"
