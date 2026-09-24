from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, delete, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services import race_center_entities


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RaceCenterDriverOwnerMeta(Base):
    __tablename__ = "race_center_driver_owner_meta"

    entity_key: Mapped[str] = mapped_column(String(220), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    hometown: Mapped[str] = mapped_column(String(180), default="")
    car_number: Mapped[str] = mapped_column(String(40), default="")
    primary_class: Mapped[str] = mapped_column(String(180), default="")
    classes_json: Mapped[str] = mapped_column(Text, default="[]")
    team_name: Mapped[str] = mapped_column(String(220), default="")
    car_info: Mapped[str] = mapped_column(Text, default="")
    social_links_json: Mapped[str] = mapped_column(Text, default="[]")
    website_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterEntityScheduleItem(Base):
    __tablename__ = "race_center_entity_schedule_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(220), default="")
    start_at: Mapped[str] = mapped_column(String(80), default="", index=True)
    venue: Mapped[str] = mapped_column(String(220), default="")
    location: Mapped[str] = mapped_column(String(220), default="")
    class_name: Mapped[str] = mapped_column(String(160), default="")
    event_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    flyer_media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterEntityMedia(Base):
    __tablename__ = "race_center_entity_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    media_kind: Mapped[str] = mapped_column(String(30), default="photo", index=True)
    title: Mapped[str] = mapped_column(String(220), default="")
    credit: Mapped[str] = mapped_column(String(220), default="")
    alt_text: Mapped[str] = mapped_column(String(320), default="")
    image_data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(80), default="image/webp")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterEntityUpdate(Base):
    __tablename__ = "race_center_entity_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RaceCenterEntitySponsor(Base):
    __tablename__ = "race_center_entity_sponsors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_key: Mapped[str] = mapped_column(String(220), index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    website_url: Mapped[str] = mapped_column(Text, default="")
    logo_url: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _kind_key(entity_type: str, entity_key: str) -> tuple[str, str]:
    kind = str(entity_type or "").strip().lower()
    key = str(entity_key or "").strip()
    if kind not in {"driver", "team", "track", "series"}:
        raise ValueError("Entity hub supports drivers, teams, tracks, and series.")
    if not key:
        raise ValueError("Entity key is required.")
    return kind, key[:220]


def user_can_manage(user_id: int, entity_type: str, entity_key: str) -> bool:
    kind, key = _kind_key(entity_type, entity_key)
    with SessionLocal() as db:
        claim = db.scalar(select(race_center_entities.RaceCenterEntityClaim.id).where(
            race_center_entities.RaceCenterEntityClaim.user_id == int(user_id),
            race_center_entities.RaceCenterEntityClaim.entity_type == kind,
            race_center_entities.RaceCenterEntityClaim.entity_key == key,
            race_center_entities.RaceCenterEntityClaim.status == "approved",
        ).limit(1))
        return claim is not None


def require_manage(user_id: int, entity_type: str, entity_key: str) -> tuple[str, str]:
    kind, key = _kind_key(entity_type, entity_key)
    if not user_can_manage(user_id, kind, key):
        raise ValueError("A verified claim is required before managing this racing profile.")
    return kind, key


def _media_payload(row: RaceCenterEntityMedia) -> dict:
    return {
        "id": row.id,
        "kind": row.media_kind,
        "title": row.title,
        "credit": row.credit,
        "alt_text": row.alt_text,
        "url": f"/api/public/race-center/entity-media/{row.id}",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _schedule_payload(row: RaceCenterEntityScheduleItem) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "start_at": row.start_at,
        "venue": row.venue,
        "location": row.location,
        "class_name": row.class_name,
        "event_url": row.event_url,
        "status": row.status,
        "notes": row.notes,
        "flyer_media_id": row.flyer_media_id,
        "flyer_url": f"/api/public/race-center/entity-media/{row.flyer_media_id}" if row.flyer_media_id else None,
    }


def driver_meta(entity_key: str) -> dict:
    key = str(entity_key or "").strip()
    with SessionLocal() as db:
        row = db.get(RaceCenterDriverOwnerMeta, key)
        if not row:
            return {}
        try:
            classes = json.loads(row.classes_json or "[]")
        except Exception:
            classes = []
        try:
            social_links = json.loads(row.social_links_json or "[]")
        except Exception:
            social_links = []
        return {
            "hometown": row.hometown,
            "car_number": row.car_number,
            "primary_class": row.primary_class,
            "classes": classes if isinstance(classes, list) else [],
            "team_name": row.team_name,
            "car_info": row.car_info,
            "social_links": social_links if isinstance(social_links, list) else [],
            "website_url": row.website_url,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


def update_driver_meta(user_id: int, entity_key: str, payload: dict) -> dict:
    kind, key = require_manage(user_id, "driver", entity_key)
    classes = [
        str(value or "").strip()[:180]
        for value in (payload.get("classes") or [])
        if str(value or "").strip()
    ][:20]
    social_links = []
    for item in (payload.get("social_links") or [])[:20]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()[:80]
        url = str(item.get("url") or "").strip()[:4000]
        if url:
            social_links.append({"label": label, "url": url})
    with SessionLocal() as db:
        row = db.get(RaceCenterDriverOwnerMeta, key)
        if row is None:
            row = RaceCenterDriverOwnerMeta(entity_key=key, owner_user_id=user_id)
            db.add(row)
        elif row.owner_user_id != user_id:
            raise ValueError("This driver profile is controlled by another verified owner.")
        row.hometown = str(payload.get("hometown") or "")[:180]
        row.car_number = str(payload.get("car_number") or "")[:40]
        row.primary_class = str(payload.get("primary_class") or "")[:180]
        row.classes_json = json.dumps(classes)
        row.team_name = str(payload.get("team_name") or "")[:220]
        row.car_info = str(payload.get("car_info") or "")[:4000]
        row.social_links_json = json.dumps(social_links)
        row.website_url = str(payload.get("website_url") or "")[:4000]
        row.updated_at = utcnow()
        db.commit()
    return driver_meta(key)


def public_hub(entity_type: str, entity_key: str, viewer_user_id: int | None = None) -> dict:
    kind, key = _kind_key(entity_type, entity_key)
    detail = race_center_entities.entity_detail(kind, key)
    if not detail:
        raise ValueError("Race Center entity not found.")
    with SessionLocal() as db:
        schedule = list(db.scalars(select(RaceCenterEntityScheduleItem).where(
            RaceCenterEntityScheduleItem.entity_type == kind,
            RaceCenterEntityScheduleItem.entity_key == key,
        ).order_by(RaceCenterEntityScheduleItem.start_at.asc(), RaceCenterEntityScheduleItem.id.asc())).all())
        media = list(db.scalars(select(RaceCenterEntityMedia).where(
            RaceCenterEntityMedia.entity_type == kind,
            RaceCenterEntityMedia.entity_key == key,
        ).order_by(RaceCenterEntityMedia.created_at.desc()).limit(36)).all())
        updates = list(db.scalars(select(RaceCenterEntityUpdate).where(
            RaceCenterEntityUpdate.entity_type == kind,
            RaceCenterEntityUpdate.entity_key == key,
        ).order_by(RaceCenterEntityUpdate.created_at.desc()).limit(40)).all())
        sponsors = list(db.scalars(select(RaceCenterEntitySponsor).where(
            RaceCenterEntitySponsor.entity_type == kind,
            RaceCenterEntitySponsor.entity_key == key,
        ).order_by(RaceCenterEntitySponsor.sort_order.asc(), RaceCenterEntitySponsor.id.asc())).all())
    return {
        "entity": detail,
        "driver_meta": driver_meta(key) if kind == "driver" else {},
        "can_manage": bool(viewer_user_id and user_can_manage(viewer_user_id, kind, key)),
        "schedule": [_schedule_payload(row) for row in schedule],
        "media": [_media_payload(row) for row in media],
        "updates": [{
            "id": row.id,
            "body": row.body,
            "media_id": row.media_id,
            "media_url": f"/api/public/race-center/entity-media/{row.media_id}" if row.media_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in updates],
        "sponsors": [{
            "id": row.id,
            "name": row.name,
            "website_url": row.website_url,
            "logo_url": row.logo_url,
            "description": row.description,
            "sort_order": row.sort_order,
        } for row in sponsors],
    }


def upsert_schedule(user_id: int, entity_type: str, entity_key: str, payload: dict, item_id: int | None = None) -> dict:
    kind, key = require_manage(user_id, entity_type, entity_key)
    status = str(payload.get("status") or "scheduled").strip().lower()
    if status not in {"scheduled", "completed", "canceled", "postponed"}:
        status = "scheduled"
    with SessionLocal() as db:
        row = db.get(RaceCenterEntityScheduleItem, int(item_id)) if item_id else None
        if row and (row.entity_type != kind or row.entity_key != key or row.owner_user_id != user_id):
            raise ValueError("Schedule item is not owned by this profile.")
        if row is None:
            row = RaceCenterEntityScheduleItem(entity_type=kind, entity_key=key, owner_user_id=user_id)
            db.add(row)
        row.title = str(payload.get("title") or "")[:220]
        row.start_at = str(payload.get("start_at") or "")[:80]
        row.venue = str(payload.get("venue") or "")[:220]
        row.location = str(payload.get("location") or "")[:220]
        row.class_name = str(payload.get("class_name") or "")[:160]
        row.event_url = str(payload.get("event_url") or "")[:4000]
        row.status = status
        row.notes = str(payload.get("notes") or "")[:4000]
        flyer = payload.get("flyer_media_id")
        flyer_id = int(flyer) if flyer not in (None, "", 0, "0") else None
        if flyer_id:
            media = db.get(RaceCenterEntityMedia, flyer_id)
            if not media or media.entity_type != kind or media.entity_key != key or media.owner_user_id != user_id:
                raise ValueError("Flyer is not part of this verified profile.")
        row.flyer_media_id = flyer_id
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return _schedule_payload(row)


def delete_schedule(user_id: int, entity_type: str, entity_key: str, item_id: int) -> dict:
    kind, key = require_manage(user_id, entity_type, entity_key)
    with SessionLocal() as db:
        row = db.get(RaceCenterEntityScheduleItem, int(item_id))
        if not row or row.entity_type != kind or row.entity_key != key or row.owner_user_id != user_id:
            raise ValueError("Schedule item not found.")
        db.delete(row)
        db.commit()
    return {"ok": True}


def add_media(user_id: int, entity_type: str, entity_key: str, *, image_data: bytes, content_type: str, media_kind: str, title: str, credit: str, alt_text: str) -> dict:
    kind, key = require_manage(user_id, entity_type, entity_key)
    if not image_data:
        raise ValueError("Image is empty.")
    clean_kind = str(media_kind or "photo").strip().lower()
    if clean_kind not in {"photo", "flyer"}:
        clean_kind = "photo"
    with SessionLocal() as db:
        row = RaceCenterEntityMedia(
            entity_type=kind,
            entity_key=key,
            owner_user_id=user_id,
            media_kind=clean_kind,
            title=str(title or "")[:220],
            credit=str(credit or "")[:220],
            alt_text=str(alt_text or "")[:320],
            image_data=image_data,
            content_type=str(content_type or "image/webp")[:80],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _media_payload(row)


def get_media(media_id: int) -> tuple[bytes, str] | None:
    with SessionLocal() as db:
        row = db.get(RaceCenterEntityMedia, int(media_id))
        if not row:
            return None
        return bytes(row.image_data), row.content_type or "image/webp"


def add_update(user_id: int, entity_type: str, entity_key: str, *, body: str, media_id: int | None = None) -> dict:
    kind, key = require_manage(user_id, entity_type, entity_key)
    clean = str(body or "").strip()
    if not clean:
        raise ValueError("Write an update before posting.")
    if len(clean) > 1200:
        raise ValueError("Updates are limited to 1200 characters.")
    with SessionLocal() as db:
        if media_id:
            media = db.get(RaceCenterEntityMedia, int(media_id))
            if not media or media.entity_type != kind or media.entity_key != key:
                raise ValueError("Attached media is not part of this profile.")
        row = RaceCenterEntityUpdate(entity_type=kind, entity_key=key, owner_user_id=user_id, body=clean, media_id=media_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id}


def replace_sponsors(user_id: int, entity_type: str, entity_key: str, sponsors: list[dict]) -> list[dict]:
    kind, key = require_manage(user_id, entity_type, entity_key)
    clean = []
    for index, item in enumerate((sponsors or [])[:30]):
        name = str((item or {}).get("name") or "").strip()[:180]
        if not name:
            continue
        clean.append({
            "name": name,
            "website_url": str((item or {}).get("website_url") or "")[:4000],
            "logo_url": str((item or {}).get("logo_url") or "")[:4000],
            "description": str((item or {}).get("description") or "")[:1000],
            "sort_order": int((item or {}).get("sort_order") or index),
        })
    with SessionLocal() as db:
        db.execute(delete(RaceCenterEntitySponsor).where(
            RaceCenterEntitySponsor.entity_type == kind,
            RaceCenterEntitySponsor.entity_key == key,
            RaceCenterEntitySponsor.owner_user_id == user_id,
        ))
        for item in clean:
            db.add(RaceCenterEntitySponsor(entity_type=kind, entity_key=key, owner_user_id=user_id, **item))
        db.commit()
    return clean



def followed_updates(follows: list[dict], limit: int = 30) -> list[dict]:
    targets: set[tuple[str, str]] = set()
    for item in follows or []:
        kind = str(item.get("kind") or "").strip().lower()
        raw_key = str(item.get("key") or "").strip()
        if kind == "driver":
            label = str(item.get("label") or "").strip()
            fallback = raw_key.split(":", 1)[1] if ":" in raw_key else raw_key
            key = race_center_entities.identity_key(label or fallback)
        elif kind in {"team", "track", "series"}:
            key = raw_key
        else:
            continue
        if key:
            targets.add((kind, key))
    if not targets:
        return []
    conditions = [
        (RaceCenterEntityUpdate.entity_type == kind) & (RaceCenterEntityUpdate.entity_key == key)
        for kind, key in targets
    ]
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RaceCenterEntityUpdate)
            .where(or_(*conditions))
            .order_by(RaceCenterEntityUpdate.created_at.desc())
            .limit(max(1, min(int(limit or 30), 60)))
        ).all())
    output = []
    for row in rows:
        detail = race_center_entities.entity_detail(row.entity_type, row.entity_key) or {}
        output.append({
            "id": row.id,
            "entity_type": row.entity_type,
            "entity_key": row.entity_key,
            "entity_name": detail.get("name") or detail.get("series_name") or row.entity_key,
            "body": row.body,
            "media_url": f"/api/public/race-center/entity-media/{row.media_id}" if row.media_id else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return output
