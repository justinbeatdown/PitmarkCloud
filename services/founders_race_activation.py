from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import threading

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services import prt_licensing_store
from services.founders_race import PrtFounderReferrer, ensure_referrers
from services.pitmark_mail_identities import send_message as send_mail

log = logging.getLogger("pitmark.founders_race_activation")
CANONICAL = "https://prt.pitmarkracing.com"


class PrtFounderRaceHubEmail(Base):
    __tablename__ = "prt_founders_race_hub_emails"

    invite_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(String(1000), default="")
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def _hub_message(display_name: str, hub: str) -> str:
    return (
        f"Hey {display_name}! 🏁\n\n"
        "You’re officially in the PRT Founder’s Race — our Early Access referral championship. "
        "This is your personal Race Hub:\n\n"
        f"{hub}\n\n"
        "Inside, you’ll find your unique recruit link, current position, qualified and pending referrals, "
        "milestone progress, and ready-made social copy you can share.\n\n"
        "A referral only counts after the racer applies through your link, gets approved, and actually activates PRT. "
        "When Early Access ends, P1 gets 12 months of the highest paid PRT tier, P2 gets 6 months, and P3 gets 3 months.\n\n"
        "Open your hub, grab your recruit link, and bring the grid. 🏁\n\n"
        "— Pitmark Racing Tools\nLeave your mark."
    )


def _send_hub_email(invite_id: int) -> None:
    try:
        ensure_referrers()
        with SessionLocal() as db:
            invite = db.get(prt_licensing_store.PrtEarlyAccessInviteRow, int(invite_id))
            referrer = db.scalar(
                select(PrtFounderReferrer).where(PrtFounderReferrer.invite_id == int(invite_id))
            )
            state = db.get(PrtFounderRaceHubEmail, int(invite_id))
            if invite is None or referrer is None or state is None:
                return
            if state.status == "sent":
                return
            email = (invite.email or "").strip().lower()
            name = (invite.applicant_name or referrer.display_name or "PRT Tester").strip()
            if not email:
                state.status = "failed"
                state.last_error = "Tester has no email address."
                state.updated_at = datetime.now(timezone.utc)
                db.commit()
                return
            state.status = "sending"
            state.attempts = int(state.attempts or 0) + 1
            state.updated_at = datetime.now(timezone.utc)
            db.commit()
            code = referrer.referral_code

        hub = f"{CANONICAL}/founders-race/t/{code}"
        send_mail(
            to=[email],
            from_identity="prt",
            subject="Your PRT Founder’s Race Hub is ready 🏁",
            text=_hub_message(name, hub),
        )

        with SessionLocal() as db:
            state = db.get(PrtFounderRaceHubEmail, int(invite_id))
            if state is not None:
                state.status = "sent"
                state.sent_at = datetime.now(timezone.utc)
                state.last_error = ""
                state.updated_at = datetime.now(timezone.utc)
                db.commit()
        log.info("Founder’s Race hub email sent automatically for invite_id=%s", invite_id)
    except Exception as exc:  # noqa: BLE001 - activation must never fail because email failed
        log.warning("Founder’s Race automatic hub email failed for invite_id=%s: %s", invite_id, exc)
        try:
            with SessionLocal() as db:
                state = db.get(PrtFounderRaceHubEmail, int(invite_id))
                if state is not None:
                    state.status = "failed"
                    state.last_error = str(exc)[:1000]
                    state.updated_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            pass


def queue_hub_email(invite: dict) -> None:
    invite_id = int(invite.get("id") or 0)
    if invite_id <= 0:
        return
    if str(invite.get("status") or "").strip().lower() != "redeemed":
        return
    if str(invite.get("tester_status") or "").strip().lower() not in {"active", "completed"}:
        return
    if not str(invite.get("bound_device_id") or "").strip():
        return

    now = datetime.now(timezone.utc)
    should_start = False
    with SessionLocal() as db:
        state = db.get(PrtFounderRaceHubEmail, invite_id)
        if state is None:
            state = PrtFounderRaceHubEmail(
                invite_id=invite_id,
                status="queued",
                attempts=0,
                queued_at=now,
                updated_at=now,
            )
            db.add(state)
            db.commit()
            should_start = True
        elif state.status == "sent":
            return
        elif state.status == "failed":
            state.status = "queued"
            state.updated_at = now
            db.commit()
            should_start = True
        elif state.status in {"queued", "sending"} and state.updated_at < now - timedelta(minutes=10):
            state.status = "queued"
            state.updated_at = now
            db.commit()
            should_start = True

    if should_start:
        threading.Thread(target=_send_hub_email, args=(invite_id,), daemon=True).start()


_ORIGINAL_REDEEM = prt_licensing_store.redeem_early_access_invite


def _redeem_with_founders_race_email(code: str, device_id: str):
    invite = _ORIGINAL_REDEEM(code, device_id)
    try:
        queue_hub_email(invite)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not queue Founder’s Race hub email for invite %s: %s", invite.get("id"), exc)
    return invite


if getattr(prt_licensing_store.redeem_early_access_invite, "__name__", "") != "_redeem_with_founders_race_email":
    prt_licensing_store.redeem_early_access_invite = _redeem_with_founders_race_email
