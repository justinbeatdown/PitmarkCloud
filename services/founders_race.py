from __future__ import annotations

from datetime import datetime, timezone
import secrets
import string

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.prt_applications import PrtEarlyAccessApplication
from services.prt_licensing_store import PrtEarlyAccessInviteRow


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PrtFounderReferrer(Base):
    __tablename__ = "prt_founders_race_referrers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invite_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(180), default="")
    email: Mapped[str] = mapped_column(String(254), default="", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PrtFounderReferral(Base):
    __tablename__ = "prt_founders_race_referrals"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_founders_race_application"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(Integer, index=True)
    application_id: Mapped[int] = mapped_column(Integer, index=True)
    applicant_email: Mapped[str] = mapped_column(String(254), default="", index=True)
    applicant_name: Mapped[str] = mapped_column(String(180), default="")
    fraud_reason: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


_ALPHABET = string.ascii_uppercase + string.digits


def _clean_email(value: str) -> str:
    return (value or "").strip().lower()[:254]


def _new_code() -> str:
    return "FR-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def ensure_referrers() -> int:
    """Create a stable Founder's Race code for every non-revoked Early Access tester."""
    created = 0
    with SessionLocal() as db:
        invites = list(
            db.scalars(
                select(PrtEarlyAccessInviteRow).where(
                    PrtEarlyAccessInviteRow.status != "revoked",
                    PrtEarlyAccessInviteRow.tester_status != "removed",
                )
            ).all()
        )
        existing_ids = set(db.scalars(select(PrtFounderReferrer.invite_id)).all())
        for invite in invites:
            if invite.id in existing_ids:
                continue
            code = ""
            for _ in range(30):
                candidate = _new_code()
                if db.scalar(select(PrtFounderReferrer.id).where(PrtFounderReferrer.referral_code == candidate)) is None:
                    code = candidate
                    break
            if not code:
                continue
            db.add(
                PrtFounderReferrer(
                    invite_id=invite.id,
                    referral_code=code,
                    display_name=(invite.applicant_name or "PRT Tester").strip()[:180],
                    email=_clean_email(invite.email),
                    active=True,
                )
            )
            created += 1
        if created:
            db.commit()
    return created


def get_referrer_by_code(code: str) -> dict | None:
    ensure_referrers()
    clean = (code or "").strip().upper()[:20]
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtFounderReferrer).where(
                PrtFounderReferrer.referral_code == clean,
                PrtFounderReferrer.active.is_(True),
            )
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "invite_id": row.invite_id,
            "referral_code": row.referral_code,
            "display_name": row.display_name or "PRT Tester",
            "email": row.email,
        }


def record_referral(*, referral_code: str, application_id: int, applicant_email: str, applicant_name: str) -> dict:
    referrer = get_referrer_by_code(referral_code)
    if referrer is None:
        return {"credited": False, "reason": "invalid_referral_code"}

    applicant_email = _clean_email(applicant_email)
    fraud_reason = ""
    if applicant_email and applicant_email == _clean_email(referrer["email"]):
        fraud_reason = "self_referral"

    with SessionLocal() as db:
        existing_application = db.scalar(
            select(PrtFounderReferral).where(PrtFounderReferral.application_id == int(application_id))
        )
        if existing_application is not None:
            return {"credited": False, "reason": "application_already_attributed"}

        existing_email = db.scalar(
            select(PrtFounderReferral).where(func.lower(PrtFounderReferral.applicant_email) == applicant_email)
        ) if applicant_email else None
        if existing_email is not None:
            fraud_reason = fraud_reason or "duplicate_referred_email"

        row = PrtFounderReferral(
            referrer_id=int(referrer["id"]),
            application_id=int(application_id),
            applicant_email=applicant_email,
            applicant_name=(applicant_name or "").strip()[:180],
            fraud_reason=fraud_reason,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "credited": not bool(fraud_reason),
            "reason": fraud_reason or "pending_activation",
            "referral_id": row.id,
        }


def _qualified_for_referral(db, referral: PrtFounderReferral) -> tuple[bool, str, str]:
    if referral.fraud_reason:
        return False, "fraud", ""

    application = db.get(PrtEarlyAccessApplication, referral.application_id)
    if application is None:
        return False, "missing_application", ""
    if (application.status or "").strip().lower() != "accepted":
        return False, "awaiting_approval", ""

    email = _clean_email(application.email)
    invite = db.scalar(
        select(PrtEarlyAccessInviteRow)
        .where(func.lower(PrtEarlyAccessInviteRow.email) == email)
        .order_by(PrtEarlyAccessInviteRow.id.desc())
        .limit(1)
    )
    if invite is None:
        return False, "awaiting_invite", ""
    if invite.status != "redeemed" or not invite.bound_device_id:
        return False, "awaiting_activation", invite.redeemed_at or ""
    if invite.tester_status not in {"active", "completed"}:
        return False, "inactive_tester", invite.redeemed_at or ""
    return True, "qualified", invite.redeemed_at or ""


def leaderboard() -> list[dict]:
    ensure_referrers()
    with SessionLocal() as db:
        referrers = list(
            db.scalars(
                select(PrtFounderReferrer)
                .where(PrtFounderReferrer.active.is_(True))
                .order_by(PrtFounderReferrer.id.asc())
            ).all()
        )
        referrals = list(db.scalars(select(PrtFounderReferral)).all())
        by_referrer: dict[int, list[PrtFounderReferral]] = {}
        for referral in referrals:
            by_referrer.setdefault(referral.referrer_id, []).append(referral)

        rows: list[dict] = []
        for referrer in referrers:
            items = by_referrer.get(referrer.id, [])
            qualified = 0
            pending = 0
            flagged = 0
            activation_times: list[str] = []
            detail: list[dict] = []
            for item in items:
                is_qualified, state, activated_at = _qualified_for_referral(db, item)
                if is_qualified:
                    qualified += 1
                    if activated_at:
                        activation_times.append(activated_at)
                elif state == "fraud":
                    flagged += 1
                else:
                    pending += 1
                detail.append({
                    "id": item.id,
                    "application_id": item.application_id,
                    "applicant_name": item.applicant_name,
                    "applicant_email": item.applicant_email,
                    "state": state,
                    "qualified": is_qualified,
                    "fraud_reason": item.fraud_reason,
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                    "activated_at": activated_at,
                })

            rows.append({
                "referrer_id": referrer.id,
                "invite_id": referrer.invite_id,
                "referral_code": referrer.referral_code,
                "display_name": referrer.display_name or "PRT Tester",
                "email": referrer.email,
                "qualified": qualified,
                "pending": pending,
                "flagged": flagged,
                "total": len(items),
                "latest_qualified_activation": max(activation_times) if activation_times else "",
                "referrals": detail,
            })

    rows.sort(key=lambda row: (-row["qualified"], row["latest_qualified_activation"] or "9999", row["display_name"].lower()))
    for index, row in enumerate(rows, start=1):
        row["position"] = index
        if row["qualified"] >= 10:
            row["milestone"] = "10 Referral Club"
            row["next_milestone"] = None
        elif row["qualified"] >= 5:
            row["milestone"] = "5 Referral Club"
            row["next_milestone"] = 10
        else:
            row["milestone"] = None
            row["next_milestone"] = 5
    return rows


def referrer_card(code: str) -> dict | None:
    clean = (code or "").strip().upper()
    for row in leaderboard():
        if row["referral_code"] == clean:
            return row
    return None
