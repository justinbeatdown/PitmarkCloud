from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import Integer, String, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from utils.config import settings

SESSION_COOKIE = "pitmark_control_session"
SESSION_TTL_SECONDS = 60 * 60 * 12


def utcnow():
    return datetime.now(timezone.utc)


class ControlUser(Base):
    __tablename__ = "control_center_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_salt: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(256))
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@dataclass
class AuthenticatedUser:
    id: int
    username: str
    session_version: int


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _signing_key() -> bytes:
    secret = (settings.pitmark_signing_secret or settings.pitmark_admin_key or "").encode("utf-8")
    if len(secret) < 24:
        raise RuntimeError("Pitmark signing secret is not configured strongly enough for Control Center sessions.")
    return hashlib.sha256(b"pitmark-control-session\0" + secret).digest()


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    try:
        _, actual = hash_password(password, salt_hex)
        return hmac.compare_digest(actual, expected_hash)
    except Exception:
        return False


def admin_user_exists() -> bool:
    with SessionLocal() as db:
        return db.scalar(select(ControlUser.id).limit(1)) is not None


def create_initial_admin(username: str, password: str) -> ControlUser:
    username = username.strip().lower()
    if not username or len(username) > 80:
        raise ValueError("Invalid username.")
    with SessionLocal() as db:
        if db.scalar(select(ControlUser.id).limit(1)) is not None:
            raise RuntimeError("Control Center has already been initialized.")
        salt, password_hash = hash_password(password)
        user = ControlUser(username=username, password_salt=salt, password_hash=password_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def authenticate_password(username: str, password: str) -> AuthenticatedUser | None:
    username = username.strip().lower()
    with SessionLocal() as db:
        user = db.scalar(select(ControlUser).where(ControlUser.username == username))
        if not user or not verify_password(password, user.password_salt, user.password_hash):
            return None
        return AuthenticatedUser(user.id, user.username, user.session_version)


def issue_session(user: AuthenticatedUser) -> str:
    now = int(time.time())
    payload = {
        "uid": user.id,
        "usr": user.username,
        "sv": user.session_version,
        "iat": now,
        "exp": now + SESSION_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_session(token: str | None) -> AuthenticatedUser | None:
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
            user = db.get(ControlUser, uid)
            if not user or user.session_version != session_version:
                return None
            return AuthenticatedUser(user.id, user.username, user.session_version)
    except Exception:
        return None


def user_from_request(request: Request) -> AuthenticatedUser | None:
    return parse_session(request.cookies.get(SESSION_COOKIE))


def require_control_user(request: Request, admin_key: str | None = None) -> AuthenticatedUser | None:
    user = user_from_request(request)
    if user:
        return user
    # Preserve service-to-service / emergency access using the existing admin key.
    if admin_key and settings.pitmark_admin_key and hmac.compare_digest(admin_key, settings.pitmark_admin_key):
        return None
    raise HTTPException(status_code=401, detail="Control Center authentication required.")


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    with SessionLocal() as db:
        user = db.get(ControlUser, user_id)
        if not user or not verify_password(current_password, user.password_salt, user.password_hash):
            raise ValueError("Current password is incorrect.")
        salt, password_hash = hash_password(new_password)
        user.password_salt = salt
        user.password_hash = password_hash
        user.session_version += 1
        user.updated_at = utcnow()
        db.commit()


def invalidate_all_sessions(user_id: int) -> None:
    with SessionLocal() as db:
        user = db.get(ControlUser, user_id)
        if user:
            user.session_version += 1
            user.updated_at = utcnow()
            db.commit()
