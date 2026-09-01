from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Header, Request
from sqlalchemy import select

from services.control_auth import require_control_user
from services.control_center import BlogDraft, OutreachContact, ShieldEvent, SocialPost
from services.database import SessionLocal

router = APIRouter()

CLOSED_OUTREACH_STAGES = {
    "partner",
    "supporter",
    "closed",
    "declined",
    "inactive",
    "archived",
    "published",
    "alumni",
    "active_partner",
    "partnered",
    "complete",
    "completed",
}


def _due(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
    except Exception:
        pass
    try:
        return date.fromisoformat(raw[:10]) <= date.today()
    except Exception:
        return False


@router.get("/status")
def status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    user = require_control_user(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        outreach = list(db.scalars(select(OutreachContact)).all())
        followups = [
            row
            for row in outreach
            if str(row.stage or "").strip().lower() not in CLOSED_OUTREACH_STAGES
            and _due(row.next_follow_up)
        ]
        return {
            "service": "Pitmark Control Center",
            "username": user.username if user else "service-admin",
            "autopilot": True,
            "shield": True,
            "social_pending": len(
                db.scalars(select(SocialPost).where(SocialPost.status == "pending")).all()
            ),
            "shield_review": len(
                db.scalars(
                    select(ShieldEvent).where(
                        ShieldEvent.classification == "Review",
                        ~ShieldEvent.source_message_id.like("shield-test:%"),
                    )
                ).all()
            ),
            # Compatibility: old UI reads outreach_contacts. It now receives the
            # actionable count, not the historical total.
            "outreach_contacts": len(followups),
            "outreach_followups": len(followups),
            "outreach_total": len(outreach),
            "blog_drafts": len(
                db.scalars(select(BlogDraft).where(BlogDraft.status == "draft")).all()
            ),
        }
