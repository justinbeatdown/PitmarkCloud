from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, and_, delete, func, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.race_center_accounts import (
    RaceCenterAccount,
    RaceCenterConnection,
    RaceCenterProfile,
    RaceCenterUser,
)
from services.control_auth import hash_password, verify_password
from utils.config import settings

VISIBILITIES = {"public", "friends", "private"}
REPORT_REASONS = {"spam", "harassment", "impersonation", "hate", "threat", "sexual", "misinformation", "other"}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def utcnow():
    return datetime.now(timezone.utc)


class RaceCenterProfileExtra(Base):
    __tablename__ = "race_center_profile_extras"
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    avatar_url: Mapped[str] = mapped_column(Text, default="")
    cover_url: Mapped[str] = mapped_column(Text, default="")
    accent_color: Mapped[str] = mapped_column(String(7), default="#ff5500")
    hometown: Mapped[str] = mapped_column(String(100), default="")
    website_url: Mapped[str] = mapped_column(Text, default="")
    profile_visibility: Mapped[str] = mapped_column(String(20), default="public", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterFriendship(Base):
    __tablename__ = "race_center_friendships"
    __table_args__ = (UniqueConstraint("user_low", "user_high", name="uq_race_center_friend_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_low: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    user_high: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterBlock(Base):
    __tablename__ = "race_center_blocks"
    __table_args__ = (UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_race_center_block"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blocker_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RaceCenterReport(Base):
    __tablename__ = "race_center_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    target_kind: Mapped[str] = mapped_column(String(20), index=True)
    target_id: Mapped[str] = mapped_column(String(220), index=True)
    reason: Mapped[str] = mapped_column(String(40), index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    moderator_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RaceCenterNotification(Base):
    __tablename__ = "race_center_notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    target_kind: Mapped[str] = mapped_column(String(40), default="")
    target_id: Mapped[str] = mapped_column(String(220), default="")
    text: Mapped[str] = mapped_column(String(280), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RaceCenterUserModeration(Base):
    __tablename__ = "race_center_user_moderation"
    user_id: Mapped[int] = mapped_column(ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _safe_https_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if len(raw) > 1000 or parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Profile links must use a valid https:// URL.")
    return raw


def _safe_profile_image_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    configured = {
        urlparse(str(getattr(settings, "social_asset_public_url", "") or "")).netloc.lower(),
        urlparse(str(getattr(settings, "pitmark_cloud_public_url", "") or "")).netloc.lower(),
        "pcc.pitmarkracing.com",
    }
    allowed_hosts = {host for host in configured if host}
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() not in allowed_hosts
        or not parsed.path.startswith("/social-assets/")
        or len(raw) > 1000
    ):
        raise ValueError("Profile images must be uploaded through Race Center.")
    return raw


def _public_user(db, user_id: int) -> dict:
    user = db.get(RaceCenterUser, user_id)
    profile = db.get(RaceCenterProfile, user_id)
    extra = db.get(RaceCenterProfileExtra, user_id)
    if not user:
        return {}
    return {
        "id": user.id,
        "display_name": user.display_name or (profile.handle if profile else "Racer"),
        "handle": profile.handle if profile else "",
        "bio": profile.bio if profile else "",
        "favorite_track": profile.favorite_track if profile else "",
        "avatar_url": extra.avatar_url if extra else "",
        "cover_url": extra.cover_url if extra else "",
        "accent_color": extra.accent_color if extra else "#ff5500",
        "hometown": extra.hometown if extra else "",
        "website_url": extra.website_url if extra else "",
        "profile_visibility": extra.profile_visibility if extra else "public",
    }


def ensure_extra(user_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(RaceCenterProfileExtra, user_id)
        if row is None:
            row = RaceCenterProfileExtra(user_id=user_id)
            db.add(row)
            db.commit()
        return _public_user(db, user_id)


def update_extra(user_id: int, *, avatar_url: str, cover_url: str, accent_color: str, hometown: str, website_url: str, profile_visibility: str, display_name: str) -> dict:
    accent = (accent_color or "#ff5500").strip().lower()
    if not HEX_RE.fullmatch(accent):
        raise ValueError("Accent color must be a six-digit hex color.")
    visibility = (profile_visibility or "public").strip().lower()
    if visibility not in VISIBILITIES:
        raise ValueError("Profile visibility must be public, friends, or private.")
    name = (display_name or "").strip()[:80]
    if len(name) < 2:
        raise ValueError("Display name must be at least 2 characters.")
    with SessionLocal() as db:
        user = db.get(RaceCenterUser, user_id)
        if not user:
            raise ValueError("Race Center account not found.")
        row = db.get(RaceCenterProfileExtra, user_id)
        if row is None:
            row = RaceCenterProfileExtra(user_id=user_id)
            db.add(row)
        user.display_name = name
        user.updated_at = utcnow()
        row.avatar_url = _safe_profile_image_url(avatar_url)
        row.cover_url = _safe_profile_image_url(cover_url)
        row.accent_color = accent
        row.hometown = (hometown or "").strip()[:100]
        row.website_url = _safe_https_url(website_url)
        row.profile_visibility = visibility
        row.updated_at = utcnow()
        db.commit()
        return _public_user(db, user_id)


def blocked_ids(user_id: int) -> set[int]:
    with SessionLocal() as db:
        a = set(db.scalars(select(RaceCenterBlock.blocked_user_id).where(RaceCenterBlock.blocker_user_id == user_id)).all())
        b = set(db.scalars(select(RaceCenterBlock.blocker_user_id).where(RaceCenterBlock.blocked_user_id == user_id)).all())
    return a | b


def list_blocks(user_id: int) -> list[dict]:
    with SessionLocal() as db:
        ids = list(db.scalars(select(RaceCenterBlock.blocked_user_id).where(RaceCenterBlock.blocker_user_id == user_id)).all())
        return [_public_user(db, x) for x in ids if x]


def block_user(user_id: int, target_id: int) -> dict:
    if user_id == target_id:
        raise ValueError("You cannot block yourself.")
    low, high = _pair(user_id, target_id)
    with SessionLocal() as db:
        if not db.get(RaceCenterUser, target_id):
            raise ValueError("Race Center user not found.")
        row = db.scalar(select(RaceCenterBlock).where(RaceCenterBlock.blocker_user_id == user_id, RaceCenterBlock.blocked_user_id == target_id))
        if row is None:
            db.add(RaceCenterBlock(blocker_user_id=user_id, blocked_user_id=target_id))
        db.execute(delete(RaceCenterFriendship).where(RaceCenterFriendship.user_low == low, RaceCenterFriendship.user_high == high))
        db.execute(delete(RaceCenterConnection).where(or_(
            and_(RaceCenterConnection.follower_user_id == user_id, RaceCenterConnection.followed_user_id == target_id),
            and_(RaceCenterConnection.follower_user_id == target_id, RaceCenterConnection.followed_user_id == user_id),
        )))
        db.commit()
    return {"ok": True}


def unblock_user(user_id: int, target_id: int) -> dict:
    with SessionLocal() as db:
        db.execute(delete(RaceCenterBlock).where(RaceCenterBlock.blocker_user_id == user_id, RaceCenterBlock.blocked_user_id == target_id))
        db.commit()
    return {"ok": True}


def friendship_state(viewer_id: int, target_id: int) -> str:
    if viewer_id == target_id:
        return "self"
    low, high = _pair(viewer_id, target_id)
    with SessionLocal() as db:
        row = db.scalar(select(RaceCenterFriendship).where(RaceCenterFriendship.user_low == low, RaceCenterFriendship.user_high == high))
        if row is None:
            return "none"
        if row.status == "accepted":
            return "friends"
        return "incoming" if row.requested_by == target_id else "outgoing"


def send_friend_request(user_id: int, target_id: int) -> dict:
    if user_id == target_id:
        raise ValueError("You cannot add yourself as a friend.")
    if target_id in blocked_ids(user_id):
        raise ValueError("Friend request unavailable.")
    low, high = _pair(user_id, target_id)
    with SessionLocal() as db:
        if not db.get(RaceCenterUser, target_id):
            raise ValueError("Race Center user not found.")
        row = db.scalar(select(RaceCenterFriendship).where(RaceCenterFriendship.user_low == low, RaceCenterFriendship.user_high == high))
        if row and row.status == "accepted":
            return {"ok": True, "state": "friends"}
        if row and row.status == "pending" and row.requested_by == user_id:
            return {"ok": True, "state": "outgoing"}
        if row and row.status == "pending" and row.requested_by == target_id:
            row.status = "accepted"
            row.updated_at = utcnow()
            state = "friends"
            for follower, followed in ((user_id, target_id), (target_id, user_id)):
                existing_follow = db.scalar(select(RaceCenterConnection).where(
                    RaceCenterConnection.follower_user_id == follower,
                    RaceCenterConnection.followed_user_id == followed,
                ))
                if existing_follow is None:
                    db.add(RaceCenterConnection(follower_user_id=follower, followed_user_id=followed))
            db.add(RaceCenterNotification(user_id=target_id, actor_user_id=user_id, kind="friend_accept", target_kind="user", target_id=str(user_id), text="accepted your friend request"))
        else:
            if row is None:
                row = RaceCenterFriendship(user_low=low, user_high=high, requested_by=user_id)
                db.add(row)
            else:
                row.status = "pending"
                row.requested_by = user_id
                row.updated_at = utcnow()
            state = "outgoing"
            db.add(RaceCenterNotification(user_id=target_id, actor_user_id=user_id, kind="friend_request", target_kind="user", target_id=str(user_id), text="sent you a friend request"))
        db.commit()
    return {"ok": True, "state": state}


def respond_friend_request(user_id: int, target_id: int, accept: bool) -> dict:
    low, high = _pair(user_id, target_id)
    with SessionLocal() as db:
        row = db.scalar(select(RaceCenterFriendship).where(RaceCenterFriendship.user_low == low, RaceCenterFriendship.user_high == high))
        if not row or row.requested_by != target_id or row.status != "pending":
            raise ValueError("Friend request not found.")
        if accept:
            row.status = "accepted"
            row.updated_at = utcnow()
            for follower, followed in ((user_id, target_id), (target_id, user_id)):
                existing_follow = db.scalar(select(RaceCenterConnection).where(
                    RaceCenterConnection.follower_user_id == follower,
                    RaceCenterConnection.followed_user_id == followed,
                ))
                if existing_follow is None:
                    db.add(RaceCenterConnection(follower_user_id=follower, followed_user_id=followed))
            db.add(RaceCenterNotification(user_id=target_id, actor_user_id=user_id, kind="friend_accept", target_kind="user", target_id=str(user_id), text="accepted your friend request"))
        else:
            db.delete(row)
        db.commit()
    return {"ok": True, "state": "friends" if accept else "none"}


def remove_friend(user_id: int, target_id: int) -> dict:
    low, high = _pair(user_id, target_id)
    with SessionLocal() as db:
        db.execute(delete(RaceCenterFriendship).where(RaceCenterFriendship.user_low == low, RaceCenterFriendship.user_high == high))
        db.commit()
    return {"ok": True}


def list_friendship_dashboard(user_id: int) -> dict:
    blocked = blocked_ids(user_id)
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterFriendship).where(or_(
            RaceCenterFriendship.user_low == user_id,
            RaceCenterFriendship.user_high == user_id,
        ))).all())
        friends, incoming, outgoing = [], [], []
        for row in rows:
            other = row.user_high if row.user_low == user_id else row.user_low
            if other in blocked:
                continue
            person = _public_user(db, other)
            if row.status == "accepted":
                friends.append(person)
            elif row.requested_by == user_id:
                outgoing.append(person)
            else:
                incoming.append(person)
        return {"friends": friends, "incoming": incoming, "outgoing": outgoing, "blocked": list_blocks(user_id)}


def create_report(user_id: int, *, target_kind: str, target_id: str, reason: str, details: str = "") -> dict:
    kind = (target_kind or "").strip().lower()
    if kind not in {"user", "post", "comment"}:
        raise ValueError("Report target must be a user, post, or comment.")
    clean_reason = (reason or "").strip().lower()
    if clean_reason not in REPORT_REASONS:
        raise ValueError("Choose a valid report reason.")
    clean_target = str(target_id or "").strip()[:220]
    if not clean_target:
        raise ValueError("Report target is required.")

    from services.race_center_accounts import RaceCenterComment, RaceCenterPost
    with SessionLocal() as db:
        try:
            numeric_target = int(clean_target)
        except Exception:
            numeric_target = 0

        if kind == "user":
            target = db.get(RaceCenterUser, numeric_target)
            if not target:
                raise ValueError("Race Center user not found.")
            if numeric_target == user_id:
                raise ValueError("You cannot report your own account.")
        elif kind == "post":
            target = db.get(RaceCenterPost, numeric_target)
            if not target or target.deleted:
                raise ValueError("Post not found.")
            if target.user_id == user_id:
                raise ValueError("You cannot report your own post.")
        else:
            target = db.get(RaceCenterComment, numeric_target)
            if not target or target.deleted:
                raise ValueError("Comment not found.")
            if target.user_id == user_id:
                raise ValueError("You cannot report your own comment.")

        existing = db.scalar(select(RaceCenterReport.id).where(
            RaceCenterReport.reporter_user_id == user_id,
            RaceCenterReport.target_kind == kind,
            RaceCenterReport.target_id == clean_target,
            RaceCenterReport.status == "open",
        ).limit(1))
        if existing:
            return {"ok": True, "report_id": int(existing), "duplicate": True}

        row = RaceCenterReport(
            reporter_user_id=user_id,
            target_kind=kind,
            target_id=clean_target,
            reason=clean_reason,
            details=(details or "").strip()[:1000],
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "report_id": row.id, "duplicate": False}


def list_notifications(user_id: int, limit: int = 40) -> list[dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterNotification).where(RaceCenterNotification.user_id == user_id).order_by(RaceCenterNotification.created_at.desc()).limit(min(max(limit, 1), 80))).all())
        return [{
            "id": row.id,
            "kind": row.kind,
            "text": row.text,
            "read": row.read,
            "actor": ({
                "id": row.actor_user_id,
                "display_name": _public_user(db, row.actor_user_id).get("display_name", ""),
                "handle": _public_user(db, row.actor_user_id).get("handle", ""),
                "avatar_url": _public_user(db, row.actor_user_id).get("avatar_url", ""),
            } if row.actor_user_id else None),
            "target_kind": row.target_kind,
            "target_id": row.target_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in rows]


def mark_notifications_read(user_id: int) -> dict:
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterNotification).where(RaceCenterNotification.user_id == user_id, RaceCenterNotification.read.is_(False))).all())
        for row in rows:
            row.read = True
        db.commit()
    return {"ok": True}


def moderation_queue(status: str = "open", limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(RaceCenterReport).where(RaceCenterReport.status == status).order_by(RaceCenterReport.created_at.asc()).limit(min(max(limit, 1), 200))).all())
        return [{
            "id": row.id,
            "reporter": _public_user(db, row.reporter_user_id),
            "target_kind": row.target_kind,
            "target_id": row.target_id,
            "reason": row.reason,
            "details": row.details,
            "status": row.status,
            "moderator_note": row.moderator_note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in rows]


def resolve_report(report_id: int, *, status: str, note: str = "") -> dict:
    clean = (status or "").strip().lower()
    if clean not in {"resolved", "dismissed"}:
        raise ValueError("Report status must be resolved or dismissed.")
    with SessionLocal() as db:
        row = db.get(RaceCenterReport, report_id)
        if not row:
            raise ValueError("Report not found.")
        row.status = clean
        row.moderator_note = (note or "").strip()[:1000]
        row.resolved_at = utcnow()
        db.commit()
    return {"ok": True}



def notify(user_id: int, *, actor_user_id: int | None, kind: str, target_kind: str = "", target_id: str = "", text: str = "") -> None:
    if not user_id or (actor_user_id and user_id == actor_user_id):
        return
    with SessionLocal() as db:
        if actor_user_id and actor_user_id in blocked_ids(user_id):
            return
        db.add(RaceCenterNotification(
            user_id=user_id,
            actor_user_id=actor_user_id,
            kind=(kind or "update")[:40],
            target_kind=(target_kind or "")[:40],
            target_id=str(target_id or "")[:220],
            text=(text or "")[:280],
        ))
        db.commit()


def moderation_state(user_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(RaceCenterUserModeration, user_id)
        return {
            "status": row.status if row else "active",
            "reason": row.reason if row else "",
        }


def ensure_account_allowed(user_id: int) -> None:
    state = moderation_state(user_id)
    if state["status"] == "banned":
        raise ValueError("This Race Center account has been banned.")
    if state["status"] == "suspended":
        raise ValueError("This Race Center account is suspended.")


def set_user_moderation(user_id: int, *, status: str, reason: str = "") -> dict:
    clean = (status or "").strip().lower()
    if clean not in {"active", "suspended", "banned"}:
        raise ValueError("User status must be active, suspended, or banned.")
    with SessionLocal() as db:
        user = db.get(RaceCenterUser, user_id)
        if not user:
            raise ValueError("Race Center user not found.")
        row = db.get(RaceCenterUserModeration, user_id)
        if row is None:
            row = RaceCenterUserModeration(user_id=user_id)
            db.add(row)
        row.status = clean
        row.reason = (reason or "").strip()[:1000]
        row.updated_at = utcnow()
        if clean in {"suspended", "banned"}:
            user.session_version = (user.session_version or 1) + 1
            user.updated_at = utcnow()
        db.commit()
    return {"ok": True, "user_id": user_id, "status": clean}


def moderate_report(report_id: int, *, action: str, note: str = "") -> dict:
    clean = (action or "").strip().lower()
    if clean not in {"dismiss", "resolve", "hide_content", "suspend_user", "ban_user"}:
        raise ValueError("Unsupported moderation action.")
    from services.race_center_accounts import RaceCenterPost, RaceCenterComment
    with SessionLocal() as db:
        row = db.get(RaceCenterReport, report_id)
        if not row:
            raise ValueError("Report not found.")
        if clean == "hide_content":
            if row.target_kind == "post":
                try:
                    post = db.get(RaceCenterPost, int(row.target_id))
                except Exception:
                    post = None
                if not post:
                    raise ValueError("Reported post not found.")
                post.deleted = True
            elif row.target_kind == "comment":
                try:
                    comment = db.get(RaceCenterComment, int(row.target_id))
                except Exception:
                    comment = None
                if not comment:
                    raise ValueError("Reported comment not found.")
                comment.deleted = True
            else:
                raise ValueError("Hide content is only available for post/comment reports.")
            row.status = "resolved"
        elif clean in {"suspend_user", "ban_user"}:
            if row.target_kind != "user":
                raise ValueError("Account actions are only available for user reports.")
            try:
                target_user_id = int(row.target_id)
            except Exception as exc:
                raise ValueError("Reported user is invalid.") from exc
            target = db.get(RaceCenterUser, target_user_id)
            if not target:
                raise ValueError("Reported user not found.")
            moderation = db.get(RaceCenterUserModeration, target_user_id)
            if moderation is None:
                moderation = RaceCenterUserModeration(user_id=target_user_id)
                db.add(moderation)
            moderation.status = "suspended" if clean == "suspend_user" else "banned"
            moderation.reason = (note or row.reason or "moderation action").strip()[:1000]
            moderation.updated_at = utcnow()
            target.session_version = (target.session_version or 1) + 1
            target.updated_at = utcnow()
            row.status = "resolved"
        else:
            row.status = "dismissed" if clean == "dismiss" else "resolved"
        row.moderator_note = (note or "").strip()[:1000]
        row.resolved_at = utcnow()
        status = row.status
        db.commit()
    return {"ok": True, "status": status}


def set_identity(
    user_id: int,
    *,
    account_type: str,
    verification_status: str,
    official_label: str = "",
    external_url: str = "",
) -> dict:
    from services.race_center_accounts import RaceCenterIdentity
    clean_type=(account_type or "fan").strip().lower()
    clean_status=(verification_status or "unverified").strip().lower()
    if clean_type not in {"fan","driver","team","series","track","media"}:
        raise ValueError("Unsupported Race Center account type.")
    if clean_status not in {"unverified","verified"}:
        raise ValueError("Verification status must be unverified or verified.")
    clean_url=_safe_https_url(external_url)
    with SessionLocal() as db:
        if not db.get(RaceCenterUser,user_id):
            raise ValueError("Race Center user not found.")
        row=db.get(RaceCenterIdentity,user_id)
        if row is None:
            row=RaceCenterIdentity(user_id=user_id)
            db.add(row)
        row.account_type=clean_type
        row.verification_status=clean_status
        row.official_label=(official_label or "").strip()[:120]
        row.external_url=clean_url
        row.updated_at=utcnow()
        db.commit()
        return {
            "account_type":row.account_type,
            "verification_status":row.verification_status,
            "official_label":row.official_label,
            "external_url":row.external_url,
        }


def moderated_users(limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(RaceCenterUserModeration)
            .where(RaceCenterUserModeration.status.in_(["suspended", "banned"]))
            .order_by(RaceCenterUserModeration.updated_at.desc())
            .limit(min(max(limit, 1), 200))
        ).all())
        return [{
            **_public_user(db, row.user_id),
            "moderation_status": row.status,
            "moderation_reason": row.reason,
            "moderation_updated_at": row.updated_at.isoformat() if row.updated_at else None,
        } for row in rows]


def search_people(user_id: int, query: str, limit: int = 20) -> list[dict]:
    term=(query or "").strip().lower()
    if len(term)<2:
        return []
    blocked=blocked_ids(user_id)
    with SessionLocal() as db:
        profiles=list(db.scalars(select(RaceCenterProfile).order_by(RaceCenterProfile.handle.asc()).limit(500)).all())
        out=[]
        for profile in profiles:
            if profile.user_id==user_id or profile.user_id in blocked:
                continue
            user=db.get(RaceCenterUser, profile.user_id)
            haystack=" ".join([
                profile.handle or "",
                profile.bio or "",
                profile.favorite_track or "",
                user.display_name if user else "",
            ]).lower()
            if term not in haystack:
                continue
            extra=db.get(RaceCenterProfileExtra, profile.user_id)
            if extra and extra.profile_visibility=="private":
                continue
            person=_public_user(db, profile.user_id)
            friend_state=friendship_state(user_id, profile.user_id)
            person["friend_state"]=friend_state
            if extra and extra.profile_visibility=="friends" and friend_state!="friends":
                person["bio"]=""
                person["favorite_track"]=""
                person["hometown"]=""
                person["website_url"]=""
            person["followers"]=db.scalar(select(func.count(RaceCenterConnection.id)).where(
                RaceCenterConnection.followed_user_id==profile.user_id
            )) or 0
            out.append(person)
            if len(out)>=max(1,min(limit,50)):
                break
        return out


def can_interact_with_post(user_id: int, post_id: int) -> bool:
    from services.race_center_accounts import RaceCenterPost
    with SessionLocal() as db:
        post = db.get(RaceCenterPost, post_id)
        if not post or post.deleted:
            return False
        if post.user_id == user_id:
            return True
        if post.user_id in blocked_ids(user_id):
            return False
        if post.visibility == "public":
            return True
        if post.visibility == "friends":
            return post.user_id in friend_ids(user_id)
        return False


def enrich_people(items: list[dict], viewer_user_id: int | None = None) -> list[dict]:
    if not items:
        return []
    with SessionLocal() as db:
        out=[]
        friend_set = friend_ids(viewer_user_id) if viewer_user_id else set()
        for item in items:
            person=dict(item)
            user_id=int(person.get("id") or 0)
            if user_id:
                public=_public_user(db,user_id)
                visibility=public.get("profile_visibility") or "public"
                person["avatar_url"]=public.get("avatar_url") or ""
                person["cover_url"]=public.get("cover_url") or ""
                person["accent_color"]=public.get("accent_color") or "#ff5500"
                person["profile_visibility"]=visibility
                if visibility=="public" or user_id==viewer_user_id or user_id in friend_set:
                    person["hometown"]=public.get("hometown") or ""
                    person["website_url"]=public.get("website_url") or ""
                else:
                    person["hometown"]=""
                    person["website_url"]=""
            out.append(person)
        return out


def enrich_feed_posts(posts: list[dict]) -> list[dict]:
    if not posts:
        return []
    with SessionLocal() as db:
        out=[]
        for raw in posts:
            post=dict(raw)
            author=dict(post.get("author") or {})
            author_id=int(author.get("id") or 0)
            if author_id:
                public=_public_user(db,author_id)
                author["avatar_url"]=public.get("avatar_url") or ""
                author["accent_color"]=public.get("accent_color") or "#ff5500"
            post["author"]=author
            comments=[]
            for raw_comment in post.get("comments") or []:
                comment=dict(raw_comment)
                c_author=dict(comment.get("author") or {})
                c_id=int(c_author.get("id") or 0)
                if c_id:
                    public=_public_user(db,c_id)
                    c_author["avatar_url"]=public.get("avatar_url") or ""
                    c_author["accent_color"]=public.get("accent_color") or "#ff5500"
                comment["author"]=c_author
                comments.append(comment)
            post["comments"]=comments
            out.append(post)
        return out


def change_password(user_id: int, current_password: str, new_password: str) -> RaceCenterAccount:
    if len(new_password or "") < 12:
        raise ValueError("New password must be at least 12 characters.")
    with SessionLocal() as db:
        user=db.get(RaceCenterUser,user_id)
        if not user or not verify_password(current_password or "",user.password_salt,user.password_hash):
            raise ValueError("Current password is incorrect.")
        salt,password_hash=hash_password(new_password)
        user.password_salt=salt
        user.password_hash=password_hash
        user.session_version=(user.session_version or 1)+1
        user.updated_at=utcnow()
        db.commit()
        db.refresh(user)
        return RaceCenterAccount(user.id,user.email,user.display_name,user.session_version)


def delete_account(user_id: int, password: str) -> dict:
    from services.race_center_accounts import (
        RaceCenterComment,
        RaceCenterFollow,
        RaceCenterIdentity,
        RaceCenterPost,
        RaceCenterReaction,
    )
    with SessionLocal() as db:
        user=db.get(RaceCenterUser,user_id)
        if not user or not verify_password(password or "",user.password_salt,user.password_hash):
            raise ValueError("Password is incorrect.")
        post_ids=list(db.scalars(select(RaceCenterPost.id).where(RaceCenterPost.user_id==user_id)).all())
        if post_ids:
            db.execute(delete(RaceCenterReaction).where(RaceCenterReaction.post_id.in_(post_ids)))
            db.execute(delete(RaceCenterComment).where(RaceCenterComment.post_id.in_(post_ids)))
        db.execute(delete(RaceCenterReaction).where(RaceCenterReaction.user_id==user_id))
        db.execute(delete(RaceCenterComment).where(RaceCenterComment.user_id==user_id))
        db.execute(delete(RaceCenterPost).where(RaceCenterPost.user_id==user_id))
        db.execute(delete(RaceCenterFollow).where(RaceCenterFollow.user_id==user_id))
        db.execute(delete(RaceCenterConnection).where(or_(
            RaceCenterConnection.follower_user_id==user_id,
            RaceCenterConnection.followed_user_id==user_id,
        )))
        db.execute(delete(RaceCenterFriendship).where(or_(
            RaceCenterFriendship.user_low==user_id,
            RaceCenterFriendship.user_high==user_id,
        )))
        db.execute(delete(RaceCenterBlock).where(or_(
            RaceCenterBlock.blocker_user_id==user_id,
            RaceCenterBlock.blocked_user_id==user_id,
        )))
        db.execute(delete(RaceCenterNotification).where(or_(
            RaceCenterNotification.user_id==user_id,
            RaceCenterNotification.actor_user_id==user_id,
        )))
        db.execute(delete(RaceCenterReport).where(RaceCenterReport.reporter_user_id==user_id))
        db.execute(delete(RaceCenterIdentity).where(RaceCenterIdentity.user_id==user_id))
        db.execute(delete(RaceCenterProfileExtra).where(RaceCenterProfileExtra.user_id==user_id))
        db.execute(delete(RaceCenterProfile).where(RaceCenterProfile.user_id==user_id))
        db.delete(user)
        db.commit()
    return {"ok":True}


def friend_ids(user_id: int) -> set[int]:
    with SessionLocal() as db:
        rows=list(db.scalars(select(RaceCenterFriendship).where(
            RaceCenterFriendship.status=="accepted",
            or_(RaceCenterFriendship.user_low==user_id,RaceCenterFriendship.user_high==user_id),
        )).all())
        return {
            row.user_high if row.user_low==user_id else row.user_low
            for row in rows
        }
