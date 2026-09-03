from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PrtTesterFeedbackRow(Base):
    __tablename__ = "prt_tester_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invite_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    tester_name: Mapped[str] = mapped_column(String(180), default="")
    tester_email: Mapped[str] = mapped_column(String(254), default="", index=True)
    device_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    kind: Mapped[str] = mapped_column(String(32), default="feedback", index=True)
    severity: Mapped[str] = mapped_column(String(24), default="normal", index=True)
    title: Mapped[str] = mapped_column(String(220), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    source: Mapped[str] = mapped_column(String(32), default="control_center")
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


def _dict(row: PrtTesterFeedbackRow) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def create_feedback(*, invite_id: int | None = None, tester_name: str = "", tester_email: str = "", device_id: str = "", kind: str = "feedback", severity: str = "normal", title: str, detail: str, source: str = "control_center") -> dict:
    kind = (kind or "feedback").strip().lower()
    severity = (severity or "normal").strip().lower()
    if kind not in {"bug", "feedback", "feature"}:
        raise ValueError("Feedback type must be bug, feedback, or feature.")
    if severity not in {"low", "normal", "high", "blocker"}:
        raise ValueError("Severity must be low, normal, high, or blocker.")
    clean_title = (title or "").strip()
    clean_detail = (detail or "").strip()
    if not clean_title or not clean_detail:
        raise ValueError("Title and details are required.")
    with SessionLocal() as db:
        row = PrtTesterFeedbackRow(
            invite_id=invite_id,
            tester_name=(tester_name or "").strip()[:180],
            tester_email=(tester_email or "").strip().lower()[:254],
            device_id=(device_id or "").strip()[:64],
            kind=kind, severity=severity, title=clean_title[:220], detail=clean_detail,
            status="open", source=(source or "control_center")[:32],
        )
        db.add(row); db.commit(); db.refresh(row)
        return _dict(row)


def list_feedback(limit: int = 100, status: str | None = None) -> list[dict]:
    with SessionLocal() as db:
        q = select(PrtTesterFeedbackRow).order_by(PrtTesterFeedbackRow.id.desc()).limit(max(1, min(int(limit), 300)))
        if status:
            q = q.where(PrtTesterFeedbackRow.status == status.strip().lower())
        return [_dict(row) for row in db.scalars(q).all()]


def update_status(feedback_id: int, status: str) -> dict | None:
    clean = (status or "").strip().lower()
    if clean not in {"open", "reviewing", "resolved"}:
        raise ValueError("Feedback status must be open, reviewing, or resolved.")
    with SessionLocal() as db:
        row = db.get(PrtTesterFeedbackRow, int(feedback_id))
        if row is None:
            return None
        row.status = clean
        row.updated_at = _now_iso()
        db.commit(); db.refresh(row)
        return _dict(row)


def summary() -> dict:
    with SessionLocal() as db:
        rows = list(db.scalars(select(PrtTesterFeedbackRow)).all())
    return {
        "total": len(rows),
        "open": sum(1 for row in rows if row.status != "resolved"),
        "blockers": sum(1 for row in rows if row.status != "resolved" and row.severity == "blocker"),
    }
