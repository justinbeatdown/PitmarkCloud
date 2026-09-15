from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def _zone(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _parse_scheduled(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return _as_aware(parsed)


def counts_toward_daily_coverage(
    *,
    status: str,
    scheduled_for: str | None,
    created_at: datetime | None,
    updated_at: datetime | None,
    now: datetime,
    timezone_name: str,
) -> bool:
    """Return whether a post really covers the current local posting day.

    Pending/approved drafts do not count. A published post counts on the local day it
    was actually updated/published; a scheduled post counts on its scheduled local day.
    """
    zone = _zone(timezone_name)
    current = _as_aware(now) or datetime.now(timezone.utc)
    local_day = current.astimezone(zone).date()
    normalized_status = (status or "").strip().lower()

    if normalized_status == "published":
        stamp = _as_aware(updated_at) or _as_aware(created_at)
        return bool(stamp and stamp.astimezone(zone).date() == local_day)

    if normalized_status == "scheduled":
        scheduled = _parse_scheduled(scheduled_for)
        return bool(scheduled and scheduled.astimezone(zone).date() == local_day)

    return False


def summarize_channel_health(channels: dict[str, dict]) -> tuple[str, str]:
    """Summarize engagement-reader health without stopping posting automation."""
    failures: list[str] = []
    for name, payload in channels.items():
        if payload.get("ok", True):
            continue
        error = str(payload.get("error") or "unavailable").strip()
        failures.append(f"{name}: {error}")
    if not failures:
        return "complete", ""
    return "degraded", " | ".join(failures)
