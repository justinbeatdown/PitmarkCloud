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
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, delete, func, select
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


# Race Center V5 social layer

class RaceCenterProfile(Base):
    __tablename__ = "race_center_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    handle: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    bio: Mapped[str] = mapped_column(String(280), default="")
    favorite_track: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterProfilePhoto(Base):
    __tablename__ = "race_center_profile_photos"

    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    image_data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(80), default="image/webp")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterDriverClaim(Base):
    __tablename__ = "race_center_driver_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    driver_key: Mapped[str] = mapped_column(String(220), index=True)
    driver_name: Mapped[str] = mapped_column(String(160), default="")
    series_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    evidence_url: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterPost(Base):
    __tablename__ = "race_center_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    series_key: Mapped[str] = mapped_column(String(120), default="", index=True)
    driver_key: Mapped[str] = mapped_column(String(220), default="", index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="public", index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RaceCenterReaction(Base):
    __tablename__ = "race_center_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", "reaction", name="uq_race_center_reaction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("race_center_posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    reaction: Mapped[str] = mapped_column(String(20), default="checkered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterComment(Base):
    __tablename__ = "race_center_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("race_center_posts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


HANDLE_RE = re.compile(r"^[a-z0-9_]{3,40}$")
ALLOWED_REACTIONS = {"checkered", "fire", "eyes"}
ALLOWED_ACCOUNT_TYPES = {"fan", "driver", "team", "series", "track", "media"}

# Server-owned staff identity. These badges are never derived from editable
# profile fields, so Race Center users cannot award themselves Pitmark status.
PITMARK_STAFF_ACCOUNTS = {
    "justin@pitmarkracing.com": {
        "label": "Pitmark Founder",
        "title": "Founder · Pitmark Racing Co.",
        "level": "founder",
    },
    "pitmarkracingco@gmail.com": {
        "label": "Pitmark Staff",
        "title": "Pitmark Racing Co.",
        "level": "staff",
    },
}


def _pitmark_staff_identity(email: str) -> dict:
    return dict(PITMARK_STAFF_ACCOUNTS.get((email or "").strip().lower()) or {})


def _base_handle(account: RaceCenterAccount) -> str:
    source = (account.display_name or account.email.split("@", 1)[0] or "racer").lower()
    source = re.sub(r"[^a-z0-9_]+", "_", source).strip("_")
    if len(source) < 3:
        source = "racer"
    return source[:32]


def ensure_profile(user_id: int) -> dict:
    with SessionLocal() as db:
        profile = db.get(RaceCenterProfile, user_id)
        user = db.get(RaceCenterUser, user_id)
        if not user:
            raise ValueError("Race Center account not found.")
        if profile is None:
            account = RaceCenterAccount(user.id, user.email, user.display_name, user.session_version)
            base = _base_handle(account)
            candidate = base
            suffix = 1
            while db.scalar(select(RaceCenterProfile.user_id).where(RaceCenterProfile.handle == candidate)):
                suffix += 1
                candidate = f"{base[:32]}_{suffix}"[:40]
            profile = RaceCenterProfile(user_id=user_id, handle=candidate)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        identity = db.get(RaceCenterIdentity, user_id)
        return {
            "handle": profile.handle,
            "bio": profile.bio,
            "favorite_track": profile.favorite_track,
            "account_type": identity.account_type if identity else "fan",
            "photo_url": f"/api/public/race-center/profile-photo/{profile.handle}",
            "staff": _pitmark_staff_identity(user.email),
        }


def update_profile(
    user_id: int,
    *,
    handle: str,
    bio: str = "",
    favorite_track: str = "",
    account_type: str = "fan",
) -> dict:
    clean_handle = (handle or "").strip().lower()
    if not HANDLE_RE.fullmatch(clean_handle):
        raise ValueError("Handle must be 3–40 characters using letters, numbers, or underscores.")
    clean_bio = (bio or "").strip()[:280]
    clean_track = (favorite_track or "").strip()[:120]
    clean_account_type = (account_type or "fan").strip().lower()
    if clean_account_type not in ALLOWED_ACCOUNT_TYPES:
        raise ValueError("Choose a valid Race Center identity type.")
    with SessionLocal() as db:
        existing = db.scalar(select(RaceCenterProfile.user_id).where(
            RaceCenterProfile.handle == clean_handle,
            RaceCenterProfile.user_id != user_id,
        ))
        if existing:
            raise ValueError("That handle is already taken.")
        profile = db.get(RaceCenterProfile, user_id)
        if profile is None:
            profile = RaceCenterProfile(user_id=user_id, handle=clean_handle)
            db.add(profile)
        profile.handle = clean_handle
        profile.bio = clean_bio
        profile.favorite_track = clean_track
        profile.updated_at = utcnow()

        identity = db.get(RaceCenterIdentity, user_id)
        if identity is None:
            identity = RaceCenterIdentity(user_id=user_id, account_type=clean_account_type)
            db.add(identity)
        else:
            identity.account_type = clean_account_type
            identity.updated_at = utcnow()
        db.commit()
    return ensure_profile(user_id)


def create_post(user_id: int, *, body: str, series_key: str = "", driver_key: str = "") -> dict:
    clean_body = (body or "").strip()
    if not clean_body:
        raise ValueError("Write something before posting.")
    if len(clean_body) > 600:
        raise ValueError("Pit Wall posts are limited to 600 characters.")
    with SessionLocal() as db:
        row = RaceCenterPost(
            user_id=user_id,
            body=clean_body,
            series_key=(series_key or "").strip()[:120],
            driver_key=(driver_key or "").strip()[:220],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id}


def delete_post(user_id: int, post_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(RaceCenterPost, post_id)
        if not row:
            return {"ok": True}
        if row.user_id != user_id:
            raise ValueError("You can only delete your own posts.")
        row.deleted = True
        db.commit()
    return {"ok": True}


def toggle_reaction(user_id: int, post_id: int, reaction: str) -> dict:
    clean = (reaction or "").strip().lower()
    if clean not in ALLOWED_REACTIONS:
        raise ValueError("Unsupported reaction.")
    with SessionLocal() as db:
        post = db.get(RaceCenterPost, post_id)
        if not post or post.deleted:
            raise ValueError("Post not found.")
        existing = db.scalar(select(RaceCenterReaction).where(
            RaceCenterReaction.post_id == post_id,
            RaceCenterReaction.user_id == user_id,
            RaceCenterReaction.reaction == clean,
        ))
        if existing:
            db.delete(existing)
            active = False
        else:
            db.add(RaceCenterReaction(post_id=post_id, user_id=user_id, reaction=clean))
            active = True
        db.commit()
    return {"ok": True, "active": active}


def add_comment(user_id: int, post_id: int, body: str) -> dict:
    clean = (body or "").strip()
    if not clean:
        raise ValueError("Comment cannot be empty.")
    if len(clean) > 280:
        raise ValueError("Comments are limited to 280 characters.")
    with SessionLocal() as db:
        post = db.get(RaceCenterPost, post_id)
        if not post or post.deleted:
            raise ValueError("Post not found.")
        row = RaceCenterComment(post_id=post_id, user_id=user_id, body=clean)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id}


def list_posts(
    *,
    viewer_user_id: int | None = None,
    limit: int = 40,
    series_keys: list[str] | None = None,
    author_user_id: int | None = None,
) -> list[dict]:
    with SessionLocal() as db:
        stmt = select(RaceCenterPost).where(
            RaceCenterPost.deleted.is_(False),
            RaceCenterPost.visibility == "public",
        )
        if author_user_id:
            stmt = stmt.where(RaceCenterPost.user_id == author_user_id)
        followed_people: list[int] = []
        if viewer_user_id:
            followed_people = list(db.scalars(select(RaceCenterConnection.followed_user_id).where(
                RaceCenterConnection.follower_user_id == viewer_user_id
            )).all())
        if not author_user_id and (series_keys or followed_people):
            conditions = [RaceCenterPost.user_id == viewer_user_id] if viewer_user_id else []
            if followed_people:
                conditions.append(RaceCenterPost.user_id.in_(followed_people))
            if series_keys:
                conditions.append(RaceCenterPost.series_key.in_(series_keys))
            conditions.append(RaceCenterPost.series_key == "")
            stmt = stmt.where(__import__("sqlalchemy").or_(*conditions))
        posts = list(db.scalars(stmt.order_by(RaceCenterPost.created_at.desc()).limit(min(max(limit, 1), 80))).all())
        if not posts:
            return []
        user_ids = {p.user_id for p in posts}
        post_ids = [p.id for p in posts]
        users = {u.id: u for u in db.scalars(select(RaceCenterUser).where(RaceCenterUser.id.in_(user_ids))).all()}
        profiles = {p.user_id: p for p in db.scalars(select(RaceCenterProfile).where(RaceCenterProfile.user_id.in_(user_ids))).all()}
        reaction_rows = list(db.execute(
            select(RaceCenterReaction.post_id, RaceCenterReaction.reaction, func.count(RaceCenterReaction.id))
            .where(RaceCenterReaction.post_id.in_(post_ids))
            .group_by(RaceCenterReaction.post_id, RaceCenterReaction.reaction)
        ).all())
        counts: dict[int, dict[str, int]] = {}
        for post_id, reaction, count in reaction_rows:
            counts.setdefault(int(post_id), {})[str(reaction)] = int(count)
        viewer_reactions: dict[int, set[str]] = {}
        if viewer_user_id:
            for row in db.scalars(select(RaceCenterReaction).where(
                RaceCenterReaction.post_id.in_(post_ids),
                RaceCenterReaction.user_id == viewer_user_id,
            )).all():
                viewer_reactions.setdefault(row.post_id, set()).add(row.reaction)
        comments = list(db.scalars(select(RaceCenterComment).where(
            RaceCenterComment.post_id.in_(post_ids),
            RaceCenterComment.deleted.is_(False),
        ).order_by(RaceCenterComment.created_at.asc())).all())
        comment_users = {c.user_id for c in comments}
        if comment_users:
            for u in db.scalars(select(RaceCenterUser).where(RaceCenterUser.id.in_(comment_users))).all():
                users[u.id] = u
            for p in db.scalars(select(RaceCenterProfile).where(RaceCenterProfile.user_id.in_(comment_users))).all():
                profiles[p.user_id] = p
        comment_map: dict[int, list[dict]] = {}
        for item in comments:
            user = users.get(item.user_id)
            profile = profiles.get(item.user_id)
            comment_map.setdefault(item.post_id, []).append({
                "id": item.id,
                "body": item.body,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "author": {
                    "display_name": (user.display_name if user else "") or (profile.handle if profile else "Racer"),
                    "handle": profile.handle if profile else "",
                },
            })
        out = []
        for post in posts:
            user = users.get(post.user_id)
            profile = profiles.get(post.user_id)
            out.append({
                "id": post.id,
                "body": post.body,
                "series_key": post.series_key,
                "driver_key": post.driver_key,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "author": {
                    "display_name": (user.display_name if user else "") or (profile.handle if profile else "Racer"),
                    "handle": profile.handle if profile else "",
                },
                "owner": bool(viewer_user_id and post.user_id == viewer_user_id),
                "reactions": counts.get(post.id, {}),
                "viewer_reactions": sorted(viewer_reactions.get(post.id, set())),
                "comments": comment_map.get(post.id, [])[-6:],
                "comment_count": len(comment_map.get(post.id, [])),
            })
        return out


def set_profile_photo(user_id: int, image_data: bytes, content_type: str = "image/webp") -> dict:
    if not image_data:
        raise ValueError("Profile photo is empty.")
    with SessionLocal() as db:
        row = db.get(RaceCenterProfilePhoto, user_id)
        if row is None:
            row = RaceCenterProfilePhoto(user_id=user_id, image_data=image_data, content_type=content_type)
            db.add(row)
        else:
            row.image_data = image_data
            row.content_type = content_type
            row.updated_at = utcnow()
        db.commit()
    return {"ok": True}


def profile_photo_by_handle(handle: str) -> tuple[bytes, str] | None:
    clean = (handle or "").strip().lower()
    with SessionLocal() as db:
        profile = db.scalar(select(RaceCenterProfile).where(RaceCenterProfile.handle == clean))
        if not profile:
            return None
        row = db.get(RaceCenterProfilePhoto, profile.user_id)
        if not row:
            return None
        return bytes(row.image_data), row.content_type or "image/webp"


def submit_driver_claim(
    user_id: int,
    *,
    driver_key: str,
    driver_name: str,
    series_key: str = "",
    evidence_url: str = "",
    note: str = "",
) -> dict:
    clean_key = (driver_key or "").strip()[:220]
    clean_name = (driver_name or "").strip()[:160]
    clean_series = (series_key or "").strip()[:120]
    clean_evidence = (evidence_url or "").strip()[:1200]
    clean_note = (note or "").strip()[:1200]
    if not clean_key or not clean_name:
        raise ValueError("Driver identity is required.")
    if not clean_evidence and not clean_note:
        raise ValueError("Add a proof link or a short verification note.")
    if clean_evidence and not clean_evidence.lower().startswith(("http://", "https://")):
        raise ValueError("Proof link must start with http:// or https://.")
    with SessionLocal() as db:
        existing = db.scalar(select(RaceCenterDriverClaim).where(
            RaceCenterDriverClaim.user_id == user_id,
            RaceCenterDriverClaim.driver_key == clean_key,
            RaceCenterDriverClaim.status == "pending",
        ))
        if existing:
            return {"ok": True, "id": existing.id, "status": existing.status}
        row = RaceCenterDriverClaim(
            user_id=user_id,
            driver_key=clean_key,
            driver_name=clean_name,
            series_key=clean_series,
            evidence_url=clean_evidence,
            note=clean_note,
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "id": row.id, "status": row.status}


def driver_claims_for_user(user_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RaceCenterDriverClaim)
            .where(RaceCenterDriverClaim.user_id == user_id)
            .order_by(RaceCenterDriverClaim.created_at.desc())
        ).all())
    return [
        {
            "id": row.id,
            "driver_key": row.driver_key,
            "driver_name": row.driver_name,
            "series_key": row.series_key,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


class RaceCenterIdentity(Base):
    """Optional public identity/verification metadata kept separate for safe schema evolution."""
    __tablename__ = "race_center_identities"

    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    account_type: Mapped[str] = mapped_column(String(30), default="fan", index=True)  # fan/driver/team/series/track/media
    verification_status: Mapped[str] = mapped_column(String(30), default="unverified", index=True)
    official_label: Mapped[str] = mapped_column(String(120), default="")
    external_url: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterConnection(Base):
    __tablename__ = "race_center_connections"
    __table_args__ = (
        UniqueConstraint("follower_user_id", "followed_user_id", name="uq_race_center_connection"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    follower_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    followed_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def identity_for_user(user_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(RaceCenterIdentity, user_id)
        if row is None:
            return {
                "account_type": "fan",
                "verification_status": "unverified",
                "official_label": "",
                "external_url": "",
            }
        return {
            "account_type": row.account_type or "fan",
            "verification_status": row.verification_status or "unverified",
            "official_label": row.official_label or "",
            "external_url": row.external_url or "",
        }


def follow_user(follower_user_id: int, followed_user_id: int) -> dict:
    if follower_user_id == followed_user_id:
        raise ValueError("You cannot follow yourself.")
    with SessionLocal() as db:
        target = db.get(RaceCenterUser, followed_user_id)
        if not target:
            raise ValueError("Race Center user not found.")
        row = db.scalar(select(RaceCenterConnection).where(
            RaceCenterConnection.follower_user_id == follower_user_id,
            RaceCenterConnection.followed_user_id == followed_user_id,
        ))
        if row is None:
            db.add(RaceCenterConnection(
                follower_user_id=follower_user_id,
                followed_user_id=followed_user_id,
            ))
            db.commit()
    return {"ok": True}


def unfollow_user(follower_user_id: int, followed_user_id: int) -> dict:
    with SessionLocal() as db:
        db.execute(delete(RaceCenterConnection).where(
            RaceCenterConnection.follower_user_id == follower_user_id,
            RaceCenterConnection.followed_user_id == followed_user_id,
        ))
        db.commit()
    return {"ok": True}


def connection_counts(user_id: int) -> dict:
    with SessionLocal() as db:
        followers = db.scalar(select(func.count(RaceCenterConnection.id)).where(
            RaceCenterConnection.followed_user_id == user_id
        )) or 0
        following = db.scalar(select(func.count(RaceCenterConnection.id)).where(
            RaceCenterConnection.follower_user_id == user_id
        )) or 0
    return {"followers": int(followers), "following": int(following)}


def public_profile_by_handle(handle: str, viewer_user_id: int | None = None) -> dict | None:
    clean = (handle or "").strip().lower()
    with SessionLocal() as db:
        profile = db.scalar(select(RaceCenterProfile).where(RaceCenterProfile.handle == clean))
        if not profile:
            return None
        user = db.get(RaceCenterUser, profile.user_id)
        if not user:
            return None
        follows = list(db.scalars(select(RaceCenterFollow).where(
            RaceCenterFollow.user_id == profile.user_id
        )).all())
        identity = db.get(RaceCenterIdentity, profile.user_id)
        follower_count = db.scalar(select(func.count(RaceCenterConnection.id)).where(
            RaceCenterConnection.followed_user_id == profile.user_id
        )) or 0
        following_count = db.scalar(select(func.count(RaceCenterConnection.id)).where(
            RaceCenterConnection.follower_user_id == profile.user_id
        )) or 0
        viewer_follows = False
        if viewer_user_id:
            viewer_follows = db.scalar(select(RaceCenterConnection.id).where(
                RaceCenterConnection.follower_user_id == viewer_user_id,
                RaceCenterConnection.followed_user_id == profile.user_id,
            ).limit(1)) is not None
        return {
            "id": profile.user_id,
            "display_name": user.display_name or profile.handle,
            "handle": profile.handle,
            "bio": profile.bio,
            "favorite_track": profile.favorite_track,
            "identity": {
                "account_type": identity.account_type if identity else "fan",
                "verification_status": identity.verification_status if identity else "unverified",
                "official_label": identity.official_label if identity else "",
                "external_url": identity.external_url if identity else "",
            },
            "staff": _pitmark_staff_identity(user.email),
            "followers": int(follower_count),
            "following": int(following_count),
            "viewer_follows": viewer_follows,
            "photo_url": f"/api/public/race-center/profile-photo/{profile.handle}",
            "series": [
                {"key": x.follow_key, "label": x.label}
                for x in follows if x.kind == "series"
            ],
            "drivers": [
                {"key": x.follow_key, "label": x.label, "series_key": x.series_key}
                for x in follows if x.kind == "driver"
            ],
        }


def discover_people(user_id: int, limit: int = 12) -> list[dict]:
    """Rank people by shared series/driver follows; no hidden demographic profiling."""
    with SessionLocal() as db:
        mine = list(db.scalars(select(RaceCenterFollow).where(
            RaceCenterFollow.user_id == user_id
        )).all())
        mine_keys = {(x.kind, x.follow_key) for x in mine}
        already = set(db.scalars(select(RaceCenterConnection.followed_user_id).where(
            RaceCenterConnection.follower_user_id == user_id
        )).all())
        profiles = list(db.scalars(select(RaceCenterProfile).where(
            RaceCenterProfile.user_id != user_id
        )).all())
        candidates = []
        for profile in profiles:
            if profile.user_id in already:
                continue
            theirs = list(db.scalars(select(RaceCenterFollow).where(
                RaceCenterFollow.user_id == profile.user_id
            )).all())
            shared = sorted(mine_keys & {(x.kind, x.follow_key) for x in theirs})
            if not shared and mine_keys:
                continue
            user = db.get(RaceCenterUser, profile.user_id)
            identity = db.get(RaceCenterIdentity, profile.user_id)
            followers = db.scalar(select(func.count(RaceCenterConnection.id)).where(
                RaceCenterConnection.followed_user_id == profile.user_id
            )) or 0
            candidates.append({
                "id": profile.user_id,
                "display_name": (user.display_name if user else "") or profile.handle,
                "handle": profile.handle,
                "bio": profile.bio,
                "favorite_track": profile.favorite_track,
                "shared_count": len(shared),
                "shared": [{"kind": kind, "key": key} for kind, key in shared[:6]],
                "followers": int(followers),
                "photo_url": f"/api/public/race-center/profile-photo/{profile.handle}",
                "staff": _pitmark_staff_identity(user.email if user else ""),
                "identity": {
                    "account_type": identity.account_type if identity else "fan",
                    "verification_status": identity.verification_status if identity else "unverified",
                    "official_label": identity.official_label if identity else "",
                },
            })
        candidates.sort(key=lambda x: (
            1 if x["identity"]["verification_status"] == "verified" else 0,
            x["shared_count"],
            x["followers"],
        ), reverse=True)
        return candidates[:max(1, min(limit, 30))]


def followed_user_ids(user_id: int) -> list[int]:
    with SessionLocal() as db:
        return list(db.scalars(select(RaceCenterConnection.followed_user_id).where(
            RaceCenterConnection.follower_user_id == user_id
        )).all())
