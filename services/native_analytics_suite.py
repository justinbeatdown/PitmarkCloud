from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from services.control_center import BlogDraft, OutreachContact, SocialPost
from services.database import SessionLocal
from services.social_operator import SocialEngagementEvent, SocialOperatorRun
from utils.config import settings

_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_SECONDS = 120


def _cached(key: str) -> dict[str, Any] | None:
    now = time.time()
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= now:
            _CACHE.pop(key, None)
            return None
        return value


def _store(key: str, value: dict[str, Any]) -> dict[str, Any]:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time() + _CACHE_SECONDS, value)
    return value


def clear_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _post_row(row: SocialPost) -> dict[str, Any]:
    return {
        "id": row.id,
        "platform": row.platform,
        "title": row.title,
        "body": row.body,
        "content_type": row.content_type,
        "source": row.source,
        "risk": row.risk,
        "status": row.status,
        "media_url": row.media_url,
        "scheduled_for": row.scheduled_for,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _latest_operator_health() -> dict[str, Any]:
    with SessionLocal() as db:
        latest = db.scalar(select(SocialOperatorRun).order_by(SocialOperatorRun.id.desc()).limit(1))
        review_count = db.query(SocialEngagementEvent).filter(
            SocialEngagementEvent.action_status == "review"
        ).count()
    if not latest:
        return {
            "status": "never_run",
            "review_queue": review_count,
            "channels": {},
            "audience": {},
            "created_at": None,
        }
    note: dict[str, Any] = {}
    if latest.note:
        try:
            parsed = json.loads(latest.note)
            if isinstance(parsed, dict):
                note = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            note = {"summary": latest.note}
    return {
        "status": latest.status,
        "scanned": latest.scanned_count,
        "review": latest.review_count,
        "replied": latest.replies_sent_count,
        "posts_planned": latest.posts_planned_count,
        "review_queue": review_count,
        "channels": note.get("channels") or {},
        "audience": note.get("audience") or {},
        "summary": note.get("summary"),
        "created_at": latest.created_at.isoformat() if latest.created_at else None,
    }


def _calendar(days_back: int = 7, days_forward: int = 21) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)
    end = now + timedelta(days=days_forward)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SocialPost)
                .order_by(SocialPost.id.desc())
                .limit(2000)
            ).all()
        )
    selected: list[dict[str, Any]] = []
    for row in rows:
        scheduled = _dt(row.scheduled_for)
        reference = scheduled or _dt(row.updated_at) or _dt(row.created_at)
        if reference and start <= reference <= end:
            selected.append(_post_row(row))
    selected.sort(key=lambda item: str(item.get("scheduled_for") or item.get("updated_at") or ""), reverse=False)

    status_counts = Counter(str(row.status or "unknown").lower() for row in rows)
    platform_counts = Counter(str(row.platform or "unknown").lower() for row in rows)
    content_counts = Counter(str(row.content_type or "unknown").lower() for row in rows)
    upcoming = [
        item for item in selected
        if str(item.get("status") or "").lower() == "scheduled"
        and (_dt(item.get("scheduled_for")) or now) >= now
    ]
    recent_published = [
        item for item in selected
        if str(item.get("status") or "").lower() == "published"
    ]
    return {
        "items": selected,
        "upcoming": upcoming[:80],
        "recent_published": list(reversed(recent_published))[:80],
        "status_counts": dict(status_counts),
        "platform_counts": dict(platform_counts),
        "content_type_counts": dict(content_counts),
    }


def _posting_windows() -> dict[str, list[str]]:
    return {
        "facebook": ["11:15", "15:30", "20:15"],
        "instagram": ["12:30", "17:30", "20:45"],
        "x": ["10:45", "18:45", "21:15"],
        "tiktok": ["12:00", "18:30", "21:00"],
        "youtube": ["12:00", "19:00"],
    }


def social_desk(days: int = 30, *, force: bool = False) -> dict[str, Any]:
    safe_days = max(7, min(int(days), 90))
    key = f"social:{safe_days}"
    if not force:
        cached = _cached(key)
        if cached:
            return {**cached, "cached": True}

    calendar = _calendar()
    operator = _latest_operator_health()
    status_counts = calendar["status_counts"]
    platform_counts = calendar["platform_counts"]
    total = sum(status_counts.values())
    publishable = sum(status_counts.get(s, 0) for s in ("approved", "scheduled", "published"))
    queue_pressure = status_counts.get("pending", 0) + status_counts.get("approved", 0)
    recommendations: list[dict[str, str]] = []
    if queue_pressure > 12:
        recommendations.append({
            "priority": "medium",
            "title": "Content queue is crowded",
            "detail": f"{queue_pressure} posts are pending or approved. Retire duplicates before generating more.",
        })
    if status_counts.get("scheduled", 0) > 20:
        recommendations.append({
            "priority": "medium",
            "title": "Schedule density is high",
            "detail": f"{status_counts.get('scheduled', 0)} posts are scheduled. Keep cadence intentional instead of filling every open slot.",
        })
    if operator.get("review_queue", 0) > 0:
        recommendations.append({
            "priority": "high",
            "title": "Engagement needs review",
            "detail": f"{operator.get('review_queue', 0)} captured interaction(s) need a human decision.",
        })
    channels = operator.get("channels") or {}
    degraded = [name for name, value in channels.items() if isinstance(value, dict) and not value.get("ok", True)]
    if degraded:
        recommendations.append({
            "priority": "high",
            "title": "Social connector degradation",
            "detail": "Read health is degraded for: " + ", ".join(sorted(degraded)) + ".",
        })

    payload = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": safe_days,
        "timezone": settings.pitmark_timezone,
        "summary": {
            "total_posts": total,
            "pending": status_counts.get("pending", 0),
            "approved": status_counts.get("approved", 0),
            "scheduled": status_counts.get("scheduled", 0),
            "published": status_counts.get("published", 0),
            "archived": status_counts.get("archived", 0),
            "publishable": publishable,
            "review_queue": operator.get("review_queue", 0),
        },
        "platforms": platform_counts,
        "calendar": calendar,
        "operator": operator,
        "posting_windows": _posting_windows(),
        "recommendations": recommendations,
        "cached": False,
    }
    return _store(key, payload)


def analytics_overview(days: int = 30, *, force: bool = False) -> dict[str, Any]:
    safe_days = max(7, min(int(days), 90))
    key = f"analytics:{safe_days}"
    if not force:
        cached = _cached(key)
        if cached:
            return {**cached, "cached": True}

    from services.business_intelligence import overview as business_overview

    business = business_overview(safe_days)
    social = social_desk(safe_days, force=force)

    commerce = business.get("commerce") or {}
    growth = business.get("growth") or {}
    sources = business.get("sources") or {}
    meta = ((business.get("social") or {}).get("meta") or {})
    google = ((business.get("social") or {}).get("google") or {})
    ads = meta.get("ads") or {}
    ads_summary = ads.get("summary") or {}
    ga4 = google.get("ga4") or {}
    search = google.get("search_console") or {}
    youtube = google.get("youtube") or {}

    executive = {
        "revenue": commerce.get("revenue", 0),
        "orders": commerce.get("orders", 0),
        "average_order_value": commerce.get("average_order_value", 0),
        "sessions": (ga4.get("summary") or {}).get("sessions", 0),
        "users": (ga4.get("summary") or {}).get("total_users", 0),
        "page_views": (ga4.get("summary") or {}).get("page_views", 0),
        "meta_spend": ads_summary.get("spend", 0),
        "meta_clicks": ads_summary.get("clicks", 0),
        "prt_applications": ((growth.get("prt") or {}).get("applications_total", 0)),
        "relationships": ((growth.get("relationships") or {}).get("total", 0)),
        "social_published": ((social.get("summary") or {}).get("published", 0)),
        "social_scheduled": ((social.get("summary") or {}).get("scheduled", 0)),
        "youtube_subscribers": (youtube.get("summary") or {}).get("subscribers", 0),
        "search_queries_loaded": len(search.get("top_queries") or []),
        "live_sources": sum(1 for value in sources.values() if isinstance(value, dict) and value.get("live")),
        "source_count": len(sources),
    }

    payload = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": safe_days,
        "executive": executive,
        "commerce": commerce,
        "growth": growth,
        "social": business.get("social") or {},
        "sources": sources,
        "recommendations": business.get("recommendations") or [],
        "social_desk": {
            "summary": social.get("summary") or {},
            "platforms": social.get("platforms") or {},
            "operator": social.get("operator") or {},
        },
        "cached": False,
    }
    return _store(key, payload)
