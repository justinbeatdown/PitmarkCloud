"""Native Race Center finishing-order store. Source-backed, never inferred."""
from datetime import date, datetime, timezone
import hashlib
import re
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from services.database import Base, SessionLocal

def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")[:120]

class ResultEvent(Base):
    __tablename__ = "rc_result_events"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False)
    track = Column(String(180), nullable=False)
    series = Column(String(180), nullable=False)
    race_date = Column(Date, nullable=False)
    event_name = Column(String(220), nullable=False)
    source_url = Column(String(1000), nullable=False)
    source_name = Column(String(180), nullable=False)
    status = Column(String(16), nullable=False, default="provisional")
    updated_at = Column(DateTime(timezone=True), nullable=False)
    sessions = relationship("ResultSession", back_populates="event", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_rc_result_event_date", "race_date"),)

class ResultSession(Base):
    __tablename__ = "rc_result_sessions"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("rc_result_events.id"), nullable=False)
    class_name = Column(String(160), nullable=False)
    session_name = Column(String(160), nullable=False)
    event = relationship("ResultEvent", back_populates="sessions")
    entries = relationship("ResultEntry", back_populates="session", cascade="all, delete-orphan", order_by="ResultEntry.finish")
    __table_args__ = (UniqueConstraint("event_id", "class_name", "session_name", name="uq_rc_result_session"),)

class ResultEntry(Base):
    __tablename__ = "rc_result_entries"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("rc_result_sessions.id"), nullable=False)
    finish = Column(Integer, nullable=False)
    start = Column(Integer, nullable=True)
    driver = Column(String(180), nullable=False)
    car_number = Column(String(32), nullable=True)
    laps = Column(Integer, nullable=True)
    result_status = Column(String(32), nullable=False, default="finished")
    session = relationship("ResultSession", back_populates="entries")
    __table_args__ = (UniqueConstraint("session_id", "finish", name="uq_rc_result_finish"),)

def result_key(source_name, external_id):
    return hashlib.sha256(f"{source_name.strip().casefold()}:{external_id.strip()}".encode()).hexdigest()[:40]

def _event_dict(e, detailed=False):
    obj = dict(id=e.id, key=e.key, track=e.track, series=e.series, race_date=e.race_date.isoformat(),
               event_name=e.event_name, source_url=e.source_url, source_name=e.source_name,
               status=e.status, updated_at=e.updated_at.isoformat())
    if detailed:
        obj["sessions"] = [
            dict(id=s.id, class_name=s.class_name, session_name=s.session_name,
                 entries=[dict(finish=x.finish, start=x.start, driver=x.driver, car_number=x.car_number,
                               laps=x.laps, status=x.result_status) for x in s.entries])
            for s in e.sessions
        ]
    return obj

def list_events(q="", track="", series="", limit=30):
    with SessionLocal() as db:
        query = db.query(ResultEvent)
        if q:
            query = query.filter(ResultEvent.event_name.ilike(f"%{q}%"))
        if track:
            query = query.filter(ResultEvent.track.ilike(f"%{track}%"))
        if series:
            query = query.filter(ResultEvent.series.ilike(f"%{series}%"))
        return [_event_dict(e) for e in query.order_by(ResultEvent.race_date.desc(), ResultEvent.id.desc()).limit(min(100,max(1,limit))).all()]

def get_event(key):
    from sqlalchemy.orm import selectinload
    with SessionLocal() as db:
        event = db.query(ResultEvent).options(
            selectinload(ResultEvent.sessions).selectinload(ResultSession.entries)
        ).filter(ResultEvent.key == key).first()
        return _event_dict(event, detailed=True) if event else None

def driver_results(name, limit=20):
    with SessionLocal() as db:
        rows = (db.query(ResultEntry, ResultSession, ResultEvent)
            .join(ResultSession, ResultEntry.session_id == ResultSession.id)
            .join(ResultEvent, ResultSession.event_id == ResultEvent.id)
            .filter(ResultEntry.driver.ilike(name.strip()))
            .order_by(ResultEvent.race_date.desc()).limit(min(100,max(1,limit))).all())
        return [dict(event_key=e.key, race_date=e.race_date.isoformat(), track=e.track, series=e.series,
                     class_name=s.class_name, session_name=s.session_name, finish=x.finish,
                     start=x.start, car_number=x.car_number, laps=x.laps, status=e.status) for x,s,e in rows]

def upsert_verified(payload):
    """Administrative importer: caller MUST enforce editor authorization."""
    key = result_key(payload["source_name"], payload["external_id"])
    with SessionLocal.begin() as db:
        e = db.query(ResultEvent).filter_by(key=key).first()
        if e is None:
            e = ResultEvent(key=key)
            db.add(e)
            db.flush()
        for field in ("track","series","event_name","source_url","source_name","status"):
            setattr(e, field, payload[field])
        e.race_date = payload["race_date"]
        e.updated_at = datetime.now(timezone.utc)
        # Replace complete source snapshot atomically; avoids retaining stale withdrawn results.
        for s in list(e.sessions):
            db.delete(s)
        db.flush()
        for s in payload["sessions"]:
            session = ResultSession(event_id=e.id, class_name=s["class_name"], session_name=s["session_name"])
            db.add(session)
            db.flush()
            for x in s["entries"]:
                db.add(ResultEntry(session_id=session.id, **x))
        return key
