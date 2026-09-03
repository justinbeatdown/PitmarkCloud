from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from threading import Lock

from sqlalchemy import DateTime, Integer, String, select, func
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.persistent_store import DeviceCredentialRow


def utcnow():
    return datetime.now(timezone.utc)


class PrtUsageSession(Base):
    __tablename__ = "prt_usage_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    discord_user_id: Mapped[str] = mapped_column(String(40), default="", index=True)
    track_name: Mapped[str] = mapped_column(String(180), default="")
    car_name: Mapped[str] = mapped_column(String(180), default="")
    max_lap: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PrtInstallEvent(Base):
    __tablename__ = "prt_install_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


_persist_lock = Lock()
_last_persist: dict[str, datetime] = {}


class PrtDownloadEvent(Base):
    __tablename__ = "prt_download_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(80), default="website", index=True)
    version: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


def record_install(device_id: str) -> None:
    clean = (device_id or "").strip()
    if not clean:
        return
    with SessionLocal() as db:
        if db.scalar(select(PrtInstallEvent.id).where(PrtInstallEvent.device_id == clean)):
            return
        db.add(PrtInstallEvent(device_id=clean))
        db.commit()


def record_download(*, source: str = "website", version: str = "") -> dict:
    with SessionLocal() as db:
        row = PrtDownloadEvent(source=(source or "website")[:80], version=(version or "")[:40])
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "event_id": row.id}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def record_live_update(device_id: str, discord_user_id: str, payload: dict) -> None:
    now = utcnow()
    # Telemetry may arrive several times per second. Analytics only needs a
    # heartbeat every 15 seconds, which keeps Postgres writes tiny.
    with _persist_lock:
        previous = _last_persist.get(device_id)
        if previous and (now - previous).total_seconds() < 15:
            return
        _last_persist[device_id] = now

    cutoff = now - timedelta(minutes=5)
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtUsageSession)
            .where(PrtUsageSession.device_id == device_id, PrtUsageSession.ended_at.is_(None))
            .order_by(PrtUsageSession.id.desc())
            .limit(1)
        )
        if row is not None and (_aware(row.last_seen_at) or now) < cutoff:
            row.ended_at = row.last_seen_at
            row = None

        if row is None:
            row = PrtUsageSession(
                device_id=device_id,
                discord_user_id=discord_user_id or "",
                track_name=str(payload.get("track_name") or "")[:180],
                car_name=str(payload.get("car_name") or "")[:180],
                max_lap=max(0, int(payload.get("lap") or 0)),
                started_at=now,
                last_seen_at=now,
            )
            db.add(row)
        else:
            row.last_seen_at = now
            row.discord_user_id = discord_user_id or row.discord_user_id
            row.track_name = str(payload.get("track_name") or row.track_name)[:180]
            row.car_name = str(payload.get("car_name") or row.car_name)[:180]
            try:
                row.max_lap = max(row.max_lap or 0, int(payload.get("lap") or 0))
            except Exception:
                pass
        db.commit()


def close_live_session(device_id: str) -> None:
    now = utcnow()
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtUsageSession)
            .where(PrtUsageSession.device_id == device_id, PrtUsageSession.ended_at.is_(None))
            .order_by(PrtUsageSession.id.desc())
            .limit(1)
        )
        if row:
            row.ended_at = now
            row.last_seen_at = now
            db.commit()



def active_device_ids(minutes: int = 15) -> set[str]:
    """Return device identities seen recently. Used for current-access counts.

    This intentionally does not treat every historical credential as a current
    racer. Security migrations and development builds can leave old device IDs
    behind, so the Control Center should only count recently seen identities.
    """
    cutoff = utcnow() - timedelta(minutes=max(1, int(minutes)))
    result: set[str] = set()
    with SessionLocal() as db:
        devices = list(db.scalars(select(DeviceCredentialRow)).all())
    for device in devices:
        try:
            last = datetime.fromisoformat(str(device.last_seen_at).replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last >= cutoff and getattr(device, "device_id", None):
                result.add(str(device.device_id))
        except Exception:
            continue
    return result


def summary() -> dict:
    now = utcnow()
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week = now - timedelta(days=7)
    active_cutoff = now - timedelta(seconds=35)
    day_cutoff = now - timedelta(hours=24)

    with SessionLocal() as db:
        registered = db.scalar(select(func.count()).select_from(DeviceCredentialRow)) or 0
        installs = db.scalar(select(func.count()).select_from(PrtInstallEvent)) or 0
        downloads = db.scalar(select(func.count()).select_from(PrtDownloadEvent)) or 0
        total_sessions = db.scalar(select(func.count()).select_from(PrtUsageSession)) or 0
        sessions_today = db.scalar(
            select(func.count()).select_from(PrtUsageSession).where(PrtUsageSession.started_at >= today)
        ) or 0
        sessions_7d = db.scalar(
            select(func.count()).select_from(PrtUsageSession).where(PrtUsageSession.started_at >= week)
        ) or 0
        active_now = db.scalar(
            select(func.count()).select_from(PrtUsageSession).where(
                PrtUsageSession.last_seen_at >= active_cutoff,
                PrtUsageSession.ended_at.is_(None),
            )
        ) or 0

        sessions = list(
            db.scalars(
                select(PrtUsageSession)
                .where(PrtUsageSession.started_at >= week)
                .order_by(PrtUsageSession.started_at.desc())
            ).all()
        )
        devices = list(db.scalars(select(DeviceCredentialRow)).all())

    active_24h = 0
    for device in devices:
        try:
            last = datetime.fromisoformat(str(device.last_seen_at).replace("Z", "+00:00"))
            if (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) >= day_cutoff:
                active_24h += 1
        except Exception:
            pass

    track_counts = Counter(x.track_name for x in sessions if x.track_name)
    car_counts = Counter(x.car_name for x in sessions if x.car_name)
    recent = [
        {
            "id": row.id,
            "device_id": row.device_id[-8:] if row.device_id else "",
            "track_name": row.track_name,
            "car_name": row.car_name,
            "max_lap": row.max_lap,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            "active": row.ended_at is None and (_aware(row.last_seen_at) or now) >= active_cutoff,
        }
        for row in sessions[:20]
    ]

    return {
        "downloads": int(downloads),
        "registered_installs": int(installs or registered),
        "registered_devices": int(registered),
        "active_now": int(active_now),
        "active_devices_24h": int(active_24h),
        "sessions_today": int(sessions_today),
        "sessions_7d": int(sessions_7d),
        "total_sessions": int(total_sessions),
        "top_tracks_7d": [{"name": name, "sessions": count} for name, count in track_counts.most_common(5)],
        "top_cars_7d": [{"name": name, "sessions": count} for name, count in car_counts.most_common(5)],
        "recent_sessions": recent,
        "download_tracking_ready": True,
    }
