from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.control_center import SocialPost, utcnow
from services.database import Base, SessionLocal


class FirstPartyEvent(Base):
    __tablename__ = "autopilot_first_party_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    draft_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FirstPartyState(Base):
    __tablename__ = "autopilot_first_party_state"

    state_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# TikTok is intentionally excluded from automatic first-party campaigns for now.
# Pitmark's goal there is ready-to-use vertical video, not a caption-only draft.
# Manual TikTok copy generation stays available separately if/when useful.
PLATFORMS = {
    "shopify_product": ("facebook", "instagram", "x"),
    "prt_release": ("facebook", "instagram", "x", "discord"),
    "blog_publish": ("facebook", "instagram", "x"),
    "partnership": ("facebook", "instagram", "x"),
    "street_team": ("facebook", "instagram", "x"),
    "prt_milestone": ("facebook", "instagram", "x"),
    "street_team_milestone": ("facebook", "instagram", "x"),
}

GOALS = {
    "shopify_product": "product",
    "prt_release": "authority",
    "blog_publish": "authority",
    "partnership": "partner",
    "street_team": "community",
    "prt_milestone": "community",
    "street_team_milestone": "community",
}


def get_state(key: str) -> str | None:
    with SessionLocal() as db:
        row = db.get(FirstPartyState, key)
        return row.value if row else None


def set_state(key: str, value: str) -> None:
    with SessionLocal() as db:
        row = db.get(FirstPartyState, key)
        if row is None:
            db.add(FirstPartyState(state_key=key, value=value))
        else:
            row.value = value
            row.updated_at = utcnow()
        db.commit()


def queue_event(*, event_key: str, event_type: str, title: str, summary: str = "", url: str | None = None,
                media_url: str | None = None, payload: dict | None = None) -> tuple[int, bool]:
    key = (event_key or "").strip()[:255]
    if not key:
        raise ValueError("event_key is required")
    with SessionLocal() as db:
        row = db.scalar(select(FirstPartyEvent).where(FirstPartyEvent.event_key == key))
        if row:
            changed = False
            for attr, value in (("url", url), ("media_url", media_url), ("summary", summary)):
                if value and not getattr(row, attr):
                    setattr(row, attr, value); changed = True
            if row.status == "failed" and row.attempts < 5:
                row.status = "queued"; changed = True
            if changed:
                row.updated_at = utcnow(); db.commit()
            return row.id, False
        row = FirstPartyEvent(
            event_key=key,
            event_type=(event_type or "update")[:60],
            title=(title or "Pitmark update")[:240],
            summary=(summary or "")[:2000],
            url=(url or "").strip() or None,
            media_url=(media_url or "").strip() or None,
            payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str)[:12000],
        )
        db.add(row); db.commit(); db.refresh(row)
        return row.id, True


def snapshot(event_id: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(FirstPartyEvent, event_id)
        if not row:
            return None
        try:
            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
        return {
            "id": row.id, "event_type": row.event_type, "title": row.title, "summary": row.summary or "",
            "url": row.url, "media_url": row.media_url, "payload": payload, "attempts": row.attempts or 0,
        }


def pending_ids(limit: int) -> list[int]:
    with SessionLocal() as db:
        return list(db.scalars(
            select(FirstPartyEvent.id)
            .where(FirstPartyEvent.status.in_(["queued", "failed"]), FirstPartyEvent.attempts < 5)
            .order_by(FirstPartyEvent.id.asc()).limit(max(1, min(limit, 12)))
        ).all())


def existing_platforms(event_id: int) -> set[str]:
    source = f"firstparty:{event_id}"
    with SessionLocal() as db:
        return set(db.scalars(select(SocialPost.platform).where(SocialPost.source == source)).all())
