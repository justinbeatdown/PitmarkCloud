from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from services.control_center import SocialPost
from utils.config import settings

AUTOMATED_SOURCE_PREFIXES = ("dailycampaign:", "firstparty:", "operator:")
ACTIVE_STATUSES = ("scheduled", "published")
DEFAULT_DAILY_CAP = 2
BUSY_DAY_CAP = 3
DEFAULT_MIN_GAP_MINUTES = 180


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
