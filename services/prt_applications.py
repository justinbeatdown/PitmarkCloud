from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PrtEarlyAccessApplication(Base):
    __tablename__ = "prt_early_access_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(200), default="", index=True)
    discord_username: Mapped[str] = mapped_column(String(100), default="")
    iracing_name: Mapped[str] = mapped_column(String(120), default="")
    disciplines: Mapped[str] = mapped_column(String(320), default="")
    race_frequency: Mapped[str] = mapped_column(String(80), default="")
    current_tools: Mapped[str] = mapped_column(String(320), default="")
    goals: Mapped[str] = mapped_column(Text, default="")
    can_test: Mapped[bool] = mapped_column(Boolean, default=False)
    bug_reports: Mapped[bool] = mapped_column(Boolean, default=False)
    honest_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    expectations_agreed: Mapped[bool] = mapped_column(Boolean, default=False)
    campaign: Mapped[str] = mapped_column(String(80), default="", index=True)
    source: Mapped[str] = mapped_column(String(40), default="website", index=True)
    asset: Mapped[str] = mapped_column(String(40), default="", index=True)
    placement: Mapped[str] = mapped_column(String(60), default="quick-apply", index=True)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PrtFunnelEvent(Base):
    __tablename__ = "prt_funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(String(40), default="", index=True)
    placement: Mapped[str] = mapped_column(String(60), default="", index=True)
    campaign: Mapped[str] = mapped_column(String(80), default="", index=True)
    source: Mapped[str] = mapped_column(String(40), default="website", index=True)
    asset: Mapped[str] = mapped_column(String(40), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def _clean(value: str | None, limit: int) -> str:
    return " ".join((value or "").strip().split())[:limit]


def _clean_email(value: str | None) -> str:
    email = (value or "").strip().lower()[:200]
    if len(email) < 5 or "@" not in email:
        raise ValueError("Enter a valid email address.")
    local, _, domain = email.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Enter a valid email address.")
    return email


def record_funnel_event(
    *,
    stage: str,
    placement: str = "",
    campaign: str = "",
    source: str = "website",
    asset: str = "",
) -> dict:
    with SessionLocal() as db:
        row = PrtFunnelEvent(
            stage=_clean(stage, 40),
            placement=_clean(placement, 60),
            campaign=_clean(campaign, 80),
            source=_clean(source, 40) or "website",
            asset=_clean(asset, 40),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "event_id": row.id}


def submit_application(
    *,
    full_name: str,
    email: str,
    discord_username: str,
    iracing_name: str,
    disciplines: str,
    race_frequency: str,
    current_tools: str,
    goals: str,
    can_test: bool,
    bug_reports: bool,
    honest_feedback: bool,
    expectations_agreed: bool,
    campaign: str = "",
    source: str = "website",
    asset: str = "",
    placement: str = "quick-apply",
) -> dict:
    clean_name = _clean(full_name, 120)
    clean_email = _clean_email(email)
    clean_iracing = _clean(iracing_name, 120)
    clean_disciplines = _clean(disciplines, 320)
    clean_frequency = _clean(race_frequency, 80)

    if len(clean_name) < 2:
        raise ValueError("Enter your full name.")
    if len(clean_iracing) < 2:
        raise ValueError("Enter your iRacing display name.")
    if not clean_disciplines:
        raise ValueError("Choose at least one iRacing discipline.")
    if not clean_frequency:
        raise ValueError("Tell us how often you race.")
    if not (can_test and bug_reports and honest_feedback and expectations_agreed):
        raise ValueError("Please confirm all Early Access expectations before applying.")

    now = utcnow()
    recent_cutoff = now - timedelta(days=30)
    with SessionLocal() as db:
        existing = db.scalar(
            select(PrtEarlyAccessApplication)
            .where(
                func.lower(PrtEarlyAccessApplication.email) == clean_email,
                PrtEarlyAccessApplication.created_at >= recent_cutoff,
            )
            .order_by(PrtEarlyAccessApplication.id.desc())
            .limit(1)
        )
        if existing is not None:
            return {"ok": True, "duplicate": True, "application_id": existing.id}

        row = PrtEarlyAccessApplication(
            full_name=clean_name,
            email=clean_email,
            discord_username=_clean(discord_username, 100),
            iracing_name=clean_iracing,
            disciplines=clean_disciplines,
            race_frequency=clean_frequency,
            current_tools=_clean(current_tools, 320),
            goals=(goals or "").strip()[:1200],
            can_test=True,
            bug_reports=True,
            honest_feedback=True,
            expectations_agreed=True,
            campaign=_clean(campaign, 80),
            source=_clean(source, 40) or "website",
            asset=_clean(asset, 40),
            placement=_clean(placement, 60) or "quick-apply",
            status="new",
            created_at=now,
        )
        db.add(row)
        db.flush()
        db.add(
            PrtFunnelEvent(
                stage="application_submit",
                placement=row.placement,
                campaign=row.campaign,
                source=row.source,
                asset=row.asset,
                created_at=now,
            )
        )
        db.commit()
        db.refresh(row)
        return {"ok": True, "duplicate": False, "application_id": row.id}


def application_summary() -> dict:
    week = utcnow() - timedelta(days=7)
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(PrtEarlyAccessApplication)) or 0
        recent = db.scalar(
            select(func.count()).select_from(PrtEarlyAccessApplication).where(
                PrtEarlyAccessApplication.created_at >= week
            )
        ) or 0
        stage_rows = db.execute(
            select(PrtFunnelEvent.stage, func.count().label("events"))
            .where(PrtFunnelEvent.created_at >= week)
            .group_by(PrtFunnelEvent.stage)
            .order_by(func.count().desc(), PrtFunnelEvent.stage)
        ).all()
        source_rows = db.execute(
            select(PrtEarlyAccessApplication.source, func.count().label("applications"))
            .where(PrtEarlyAccessApplication.created_at >= week)
            .group_by(PrtEarlyAccessApplication.source)
            .order_by(func.count().desc(), PrtEarlyAccessApplication.source)
        ).all()
        last_created = db.scalar(select(func.max(PrtEarlyAccessApplication.created_at)))

    return {
        "quick_apply_tracking_ready": True,
        "quick_apply_applications": int(total),
        "quick_apply_applications_7d": int(recent),
        "quick_apply_last_application_at": last_created.isoformat() if last_created else None,
        "quick_apply_funnel_7d": [
            {"stage": stage or "", "events": int(events)} for stage, events in stage_rows
        ],
        "quick_apply_sources_7d": [
            {"source": source or "website", "applications": int(applications)}
            for source, applications in source_rows
        ],
    }


def list_applications(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit), 200))
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(PrtEarlyAccessApplication)
                .order_by(PrtEarlyAccessApplication.created_at.desc(), PrtEarlyAccessApplication.id.desc())
                .limit(safe_limit)
            ).all()
        )
    return [
        {
            "id": row.id,
            "full_name": row.full_name,
            "email": row.email,
            "discord_username": row.discord_username,
            "iracing_name": row.iracing_name,
            "disciplines": row.disciplines,
            "race_frequency": row.race_frequency,
            "current_tools": row.current_tools,
            "goals": row.goals,
            "source": row.source,
            "campaign": row.campaign,
            "asset": row.asset,
            "placement": row.placement,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
