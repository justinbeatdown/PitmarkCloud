from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from services.control_auth import hash_password, verify_password
from services.database import Base, SessionLocal
from utils.config import settings

SESSION_COOKIE = "pitmark_race_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def utcnow():
    return datetime.now(timezone.utc)


class RaceCenterUser(Base):
    __tablename__ = "race_center_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    password_salt: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(256))
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterFollow(Base):
    __tablename__ = "race_center_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "follow_key", name="uq_race_center_follow"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    follow_key: Mapped[str] = mapped_column(String(220))
    label: Mapped[str] = mapped_column(String(160), default="")
    series_key: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@dataclass
class RaceCenterAccount:
    id: int
    email: str
    display_name: str
    session_version: int


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_key() -> bytes:
    secret = (settings.pitmark_signing_secret or settings.pitmark_admin_key or "").encode("utf-8")
    if len(secret) < 24:
        raise RuntimeError("Pitmark signing secret is not configured strongly enough for Race Center sessions.")
    return hashlib.sha256(b"pitmark-race-center-session\0" + secret).digest()


def _clean_email(email: str) -> str:
    value = (email or "").strip().lower()
    if len(value) > 254 or not EMAIL_RE.fullmatch(value):
        raise ValueError("Enter a valid email address.")
    return value


def create_account(email: str, password: str, display_name: str = "") -> RaceCenterAccount:
    clean_email = _clean_email(email)
    clean_name = (display_name or "").strip()[:80]
    salt, password_hash = hash_password(password)
    with SessionLocal() as db:
        if db.scalar(select(RaceCenterUser.id).where(RaceCenterUser.email == clean_email)):
            raise ValueError("An account already exists for that email.")
        user = RaceCenterUser(
            email=clean_email,
            display_name=clean_name,
            password_salt=salt,
            password_hash=password_hash,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return RaceCenterAccount(user.id, user.email, user.display_name, user.session_version)


def authenticate(email: str, password: str) -> RaceCenterAccount | None:
    try:
        clean_email = _clean_email(email)
    except ValueError:
        return None
    with SessionLocal() as db:
        user = db.scalar(select(RaceCenterUser).where(RaceCenterUser.email == clean_email))
        if not user or not verify_password(password, user.password_salt, user.password_hash):
            return None
        return RaceCenterAccount(user.id, user.email, user.display_name, user.session_version)


def issue_session(user: RaceCenterAccount) -> str:
    now = int(time.time())
    payload = {
        "uid": user.id,
        "sv": user.session_version,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_session(token: str | None) -> RaceCenterAccount | None:
    if not token or "." not in token:
        return None
    try:
        body, sig = token.split(".", 1)
        expected = _b64e(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(body))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        uid = int(payload["uid"])
        session_version = int(payload["sv"])
        with SessionLocal() as db:
            user = db.get(RaceCenterUser, uid)
            if not user or user.session_version != session_version:
                return None
            return RaceCenterAccount(user.id, user.email, user.display_name, user.session_version)
    except Exception:
        return None


def account_from_request(request: Request) -> RaceCenterAccount | None:
    return parse_session(request.cookies.get(SESSION_COOKIE))


def serialize_account(account: RaceCenterAccount | None) -> dict:
    if not account:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": account.id,
        "email": account.email,
        "display_name": account.display_name,
    }


def list_follows(user_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RaceCenterFollow)
            .where(RaceCenterFollow.user_id == user_id)
            .order_by(RaceCenterFollow.kind.asc(), RaceCenterFollow.created_at.asc())
        ).all())
    return [
        {
            "kind": row.kind,
            "key": row.follow_key,
            "label": row.label,
            "series_key": row.series_key,
        }
        for row in rows
    ]


def set_follow(user_id: int, *, kind: str, key: str, label: str = "", series_key: str = "") -> dict:
    clean_kind = (kind or "").strip().lower()
    clean_key = (key or "").strip()[:220]
    if clean_kind not in {"series", "driver"}:
        raise ValueError("Follow kind must be series or driver.")
    if not clean_key:
        raise ValueError("Follow key is required.")
    clean_label = (label or "").strip()[:160]
    clean_series = (series_key or "").strip()[:120]
    with SessionLocal() as db:
        row = db.scalar(select(RaceCenterFollow).where(
            RaceCenterFollow.user_id == user_id,
            RaceCenterFollow.kind == clean_kind,
            RaceCenterFollow.follow_key == clean_key,
        ))
        if row is None:
            row = RaceCenterFollow(
                user_id=user_id,
                kind=clean_kind,
                follow_key=clean_key,
                label=clean_label,
                series_key=clean_series,
            )
            db.add(row)
        else:
            row.label = clean_label or row.label
            row.series_key = clean_series or row.series_key
        db.commit()
    return {"ok": True}


def remove_follow(user_id: int, *, kind: str, key: str) -> dict:
    clean_kind = (kind or "").strip().lower()
    clean_key = (key or "").strip()[:220]
    with SessionLocal() as db:
        db.execute(delete(RaceCenterFollow).where(
            RaceCenterFollow.user_id == user_id,
            RaceCenterFollow.kind == clean_kind,
            RaceCenterFollow.follow_key == clean_key,
        ))
        db.commit()
    return {"ok": True}
