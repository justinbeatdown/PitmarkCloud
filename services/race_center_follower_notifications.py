"""Opt-in Race Center new-follower emails, throttled and failure-isolated.

Emails are strictly optional and never affect following. Existing Race Center
accounts are not subscribed by default. Only newly created relationships can
trigger email (not page refreshes or repeated follow calls).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, select, func
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services import google_gmail, race_center_accounts

log = logging.getLogger("pitmark.race_center.follower_mail")
COOLDOWN_SECONDS = 7 * 86400
MAX_PER_DAY = 10


class RaceFollowerEmailPreference(Base):
    __tablename__ = "race_center_follower_email_preferences"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("race_center_users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RaceFollowerEmailSent(Base):
    __tablename__ = "race_center_follower_email_sent"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True
    )
    follower_id: Mapped[int] = mapped_column(
        ForeignKey("race_center_users.id", ondelete="CASCADE"), index=True
    )
    sent_at: Mapped[float] = mapped_column(Float, nullable=False)


def available() -> bool:
    return google_gmail.credentials_configured()


def preference(user_id: int) -> dict:
    with SessionLocal() as db:
        p = db.get(RaceFollowerEmailPreference, user_id)
        return {"enabled": bool(p and p.enabled), "provider_configured": available()}


def update_preference(user_id: int, enabled: bool) -> dict:
    with SessionLocal() as db:
        p = db.get(RaceFollowerEmailPreference, user_id)
        if p is None:
            p = RaceFollowerEmailPreference(user_id=user_id)
            db.add(p)
        p.enabled = bool(enabled)
        db.commit()
    return preference(user_id)


def _sender_address() -> str:
    addresses = google_gmail.list_send_as()
    accepted = [
        str(item.get("sendAsEmail") or "").strip()
        for item in addresses
        if item.get("verificationStatus") == "accepted" and item.get("sendAsEmail")
    ]
    preferred = next((value for value in accepted if value.lower() == "contact@pitmarkracing.com"), None)
    if preferred:
        return preferred
    if accepted:
        return next((value for value in accepted if value.lower().endswith("@pitmarkracing.com")), accepted[0])
    # Do not forge an unauthorized From address.
    result = google_gmail.connection_status()
    if not result.get("connected") or not result.get("email_address"):
        raise RuntimeError("No verified Gmail sender available")
    return str(result["email_address"])


def send_follower_email(followed_id: int, follower_id: int) -> None:
    """Called from a FastAPI background task only after new follow commit."""
    if followed_id == follower_id or not available():
        return
    now = time.time()
    with SessionLocal() as db:
        pref = db.get(RaceFollowerEmailPreference, followed_id)
        if not pref or not pref.enabled:
            return
        user = db.get(race_center_accounts.RaceCenterUser, followed_id)
        follower = db.get(race_center_accounts.RaceCenterUser, follower_id)
        if not user or not follower or not user.email:
            return
        # Only notify for currently existing relationships.
        relationship = db.scalar(select(race_center_accounts.RaceCenterConnection.id).where(
            race_center_accounts.RaceCenterConnection.followed_user_id == followed_id,
            race_center_accounts.RaceCenterConnection.follower_user_id == follower_id,
        ).limit(1))
        if relationship is None:
            return
        last = db.scalar(select(func.max(RaceFollowerEmailSent.sent_at)).where(
            RaceFollowerEmailSent.user_id == followed_id,
            RaceFollowerEmailSent.follower_id == follower_id,
        )) or 0
        if now-last < COOLDOWN_SECONDS:
            return
        sent_today = db.scalar(select(func.count(RaceFollowerEmailSent.id)).where(
            RaceFollowerEmailSent.user_id == followed_id,
            RaceFollowerEmailSent.sent_at > now-86400,
        )) or 0
        if sent_today >= MAX_PER_DAY:
            return
        target_email = str(user.email)
        follower_name = str(follower.display_name or "A racer").strip()[:80]
        follower_profile = race_center_accounts.ensure_profile(follower_id)
    # No user-provided HTML, external links, or unverified details in message.
    profile_url = "https://racecenter.pitmarkracing.com/race-center/u/" + follower_profile["handle"]
    preference_url = "https://racecenter.pitmarkracing.com/race-center/me#prt-history"
    body = (
        f"{follower_name} started following you on Pitmark Race Center.\n\n"
        f"See their profile: {profile_url}\n\n"
        "You can turn off new-follower emails on your Race Center profile.\n"
        f"Your profile: {preference_url}\n"
    )
    try:
        raw = google_gmail.build_raw_message(
            sender=_sender_address(),
            to=[target_email],
            subject="You have a new Race Center follower",
            text=body,
        )
        google_gmail.send_message(raw=raw)
        with SessionLocal() as db:
            db.add(RaceFollowerEmailSent(user_id=followed_id, follower_id=follower_id, sent_at=now))
            db.commit()
    except Exception:
        log.exception("New-follower email delivery failed recipient_id=%s", followed_id)
