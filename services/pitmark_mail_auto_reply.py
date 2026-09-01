from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from services.control_center import SecurityAuditEvent, ShieldEvent, utcnow
from services.database import Base, SessionLocal
from services.google_gmail import business_domain
from services.pitmark_mail import MailMessage, department_for_addresses


DEFAULT_AUTO_REPLIES = {
    "sales": (
        "Sales",
        "Thanks for contacting Pitmark Racing Co. Sales. We received your message and will review it as soon as possible.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "support": (
        "Customer Service",
        "Thanks for contacting Pitmark Racing Co. Customer Service. Your message has been received and our support queue has been notified.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "partnerships": (
        "Partnerships & Sponsorships",
        "Thanks for contacting Pitmark Racing Co. Partnerships & Sponsorships. We received your message and will review the opportunity.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "prt": (
        "PRT / Ecosystem Technical Support",
        "Thanks for contacting Pitmark Racing Tools support. We received your message and will review the technical details.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "marketing": (
        "Marketing",
        "Thanks for contacting Pitmark Racing Co. Marketing. We received your message and will review it.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "outreach": (
        "Outreach",
        "Thanks for contacting Pitmark Racing Co. Outreach. We received your message and will review it.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "orders": (
        "Orders",
        "Thanks for contacting Pitmark Racing Co. Orders. We received your message and will review your order inquiry.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
    "hello": (
        "General",
        "Thanks for contacting Pitmark Racing Co. We received your message and will get back to you as soon as possible.\n\nThis is an automated confirmation from Pitmark Racing Co.",
    ),
}

BLOCKED_LOCAL_PARTS = {"mailer-daemon", "postmaster", "noreply", "no-reply", "donotreply", "do-not-reply"}


class MailAutoReplySetting(Base):
    __tablename__ = "pitmark_mail_auto_reply_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    body: Mapped[str] = mapped_column(Text)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MailAutoReplyLog(Base):
    __tablename__ = "pitmark_mail_auto_reply_log"
    __table_args__ = (
        UniqueConstraint("conversation_key", "department", name="uq_mail_auto_reply_conversation_department"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(Integer, index=True)
    conversation_key: Mapped[str] = mapped_column(String(320), index=True)
    message_id: Mapped[int] = mapped_column(Integer, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    department: Mapped[str] = mapped_column(String(40), index=True)
    sender: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(30), default="processing", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def ensure_auto_reply_settings() -> list[MailAutoReplySetting]:
    with SessionLocal() as db:
        existing = {
            row.department: row
            for row in db.scalars(select(MailAutoReplySetting)).all()
        }
        changed = False
        for department, (label, body) in DEFAULT_AUTO_REPLIES.items():
            if department not in existing:
                row = MailAutoReplySetting(
                    department=department,
                    label=label,
                    enabled=True,
                    body=body,
                    enabled_at=utcnow(),
                    updated_at=utcnow(),
                )
                db.add(row)
                existing[department] = row
                changed = True
        if changed:
            db.commit()
        return [existing[key] for key in DEFAULT_AUTO_REPLIES]


def _serialize_setting(row: MailAutoReplySetting) -> dict:
    return {
        "department": row.department,
        "label": row.label,
        "address": f"{row.department}@{business_domain()}",
        "enabled": bool(row.enabled),
        "enabled_at": row.enabled_at.isoformat() if row.enabled_at else None,
        "body": row.body,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_auto_reply_settings() -> dict:
    ensure_auto_reply_settings()
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(MailAutoReplySetting).order_by(MailAutoReplySetting.id.asc())
        ).all())
        logs = list(db.scalars(
            select(MailAutoReplyLog).order_by(MailAutoReplyLog.id.desc()).limit(25)
        ).all())
    return {
        "settings": [_serialize_setting(row) for row in rows],
        "recent": [
            {
                "id": row.id,
                "department": row.department,
                "sender": row.sender,
                "status": row.status,
                "attempts": int(row.attempts or 0),
                "detail": row.detail,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in logs
        ],
    }


def save_auto_reply_setting(department: str, *, enabled: bool, body: str) -> dict:
    department = (department or "").strip().lower()
    if department not in DEFAULT_AUTO_REPLIES:
        raise ValueError("Unknown Pitmark email department.")
    body = (body or "").strip()
    if enabled and not body:
        raise ValueError("An enabled automatic response must have a message.")
    if len(body) > 10000:
        raise ValueError("Automatic response must be 10,000 characters or fewer.")
    ensure_auto_reply_settings()
    with SessionLocal() as db:
        row = db.scalar(select(MailAutoReplySetting).where(
            MailAutoReplySetting.department == department
        ))
        if not row:
            raise ValueError("Automatic response setting was not found.")
        if enabled and (not row.enabled or not row.enabled_at):
            row.enabled_at = utcnow()
        row.enabled = bool(enabled)
        row.body = body
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_setting(row)


def _message_payload(message: MailMessage) -> dict:
    try:
        value = json.loads(message.provider_payload_json or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _stored_addresses(value: str | None) -> list[str]:
    try:
        rows = json.loads(value or "[]")
        return [str(item) for item in rows] if isinstance(rows, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _eligibility(message: MailMessage, classification: str) -> tuple[bool, str, str]:
    sender = parseaddr(message.from_address or "")[1].strip().lower()
    if not sender or "@" not in sender:
        return False, "invalid-sender", sender
    local, domain = sender.rsplit("@", 1)
    if domain == business_domain():
        return False, "pitmark-sender", sender
    if local in BLOCKED_LOCAL_PARTS or any(token in local for token in ("noreply", "no-reply", "donotreply")):
        return False, "no-reply-sender", sender
    if classification not in {"Legit", "Unverified"}:
        return False, f"shield-{classification.lower()}", sender

    headers = _message_payload(message).get("automation_headers") or {}
    auto_submitted = str(headers.get("auto-submitted") or "").strip().lower()
    precedence = str(headers.get("precedence") or "").strip().lower()
    if auto_submitted and auto_submitted != "no":
        return False, "automated-message", sender
    if precedence in {"bulk", "list", "junk"}:
        return False, "bulk-message", sender
    if headers.get("list-id") or headers.get("list-unsubscribe"):
        return False, "mailing-list", sender
    return True, "safe-first-message", sender


def _claim(message: MailMessage, department: str, sender: str, status: str, detail: str) -> int | None:
    payload = _message_payload(message)
    provider_thread_id = str(payload.get("gmail_thread_id") or "").strip()
    conversation_key = (
        f"gmail:{provider_thread_id}"
        if provider_thread_id
        else f"pitmark:{message.thread_id}:{sender}"
    )
    with SessionLocal() as db:
        row = MailAutoReplyLog(
            thread_id=message.thread_id,
            conversation_key=conversation_key,
            message_id=message.id,
            provider_message_id=message.provider_message_id,
            department=department,
            sender=sender,
            status=status,
            attempts=1,
            detail=detail,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(MailAutoReplyLog).where(
                MailAutoReplyLog.conversation_key == conversation_key,
                MailAutoReplyLog.department == department,
            ))
            if not existing or existing.status != "error" or int(existing.attempts or 0) >= 3:
                return None
            retry_after = existing.updated_at
            if retry_after and retry_after.tzinfo is None:
                retry_after = retry_after.replace(tzinfo=timezone.utc)
            if retry_after and retry_after > utcnow() - timedelta(minutes=15):
                return None
            existing.message_id = message.id
            existing.provider_message_id = message.provider_message_id
            existing.sender = sender
            existing.status = status
            existing.attempts = int(existing.attempts or 0) + 1
            existing.detail = detail
            existing.updated_at = utcnow()
            db.commit()
            return existing.id
        db.refresh(row)
        return row.id


def process_auto_replies(limit: int = 50) -> dict:
    ensure_auto_reply_settings()
    with SessionLocal() as db:
        settings = {
            row.department: row
            for row in db.scalars(select(MailAutoReplySetting)).all()
        }
        messages = list(db.scalars(
            select(MailMessage)
            .where(MailMessage.direction == "inbound")
            .order_by(MailMessage.id.desc())
            .limit(max(1, min(limit * 4, 200)))
        ).all())

    sent = 0
    skipped = 0
    errors = 0
    cutoff = utcnow() - timedelta(hours=24)
    for message in reversed(messages):
        payload = _message_payload(message)
        department = str(payload.get("department") or department_for_addresses(
            _stored_addresses(message.to_json),
            _stored_addresses(message.cc_json),
            _stored_addresses(message.bcc_json),
        )).lower()
        setting = settings.get(department)
        if not setting or not setting.enabled:
            continue
        created_at = message.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at and created_at < cutoff:
            continue
        enabled_at = setting.enabled_at
        if enabled_at and enabled_at.tzinfo is None:
            enabled_at = enabled_at.replace(tzinfo=timezone.utc)
        if created_at and enabled_at and created_at < enabled_at:
            continue

        source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
        with SessionLocal() as db:
            shield = db.scalar(select(ShieldEvent).where(ShieldEvent.source_message_id == source_id))
        if not shield:
            continue
        eligible, reason, sender = _eligibility(message, shield.classification)
        if not eligible:
            if _claim(message, department, sender, "skipped", reason):
                skipped += 1
            continue

        log_id = _claim(message, department, sender, "processing", reason)
        if not log_id:
            continue
        try:
            from services.pitmark_mail_identities import send_message

            result = send_message(
                to=[sender],
                subject=message.subject or "Your message to Pitmark Racing Co.",
                text=setting.body,
                reply_to_message_id=message.id,
                from_identity=department,
                message_headers={
                    "Auto-Submitted": "auto-replied",
                    "X-Auto-Response-Suppress": "All",
                },
            )
            with SessionLocal() as db:
                log = db.get(MailAutoReplyLog, log_id)
                if log:
                    log.status = "sent"
                    log.detail = f"Automatic acknowledgment sent from {department}@{business_domain()}."
                    log.sent_message_id = result.get("id")
                    log.updated_at = utcnow()
                db.add(SecurityAuditEvent(
                    event_type="pitmark_mail_auto_reply_sent",
                    severity="info",
                    actor=sender,
                    source="pitmark_mail_auto_reply",
                    detail=f"Shield-approved automatic reply sent from {department}@{business_domain()} for message #{message.id}.",
                    created_at=utcnow(),
                ))
                db.commit()
            sent += 1
        except (RuntimeError, ValueError) as exc:
            with SessionLocal() as db:
                log = db.get(MailAutoReplyLog, log_id)
                if log:
                    log.status = "error"
                    log.detail = str(exc)[:1000]
                    log.updated_at = utcnow()
                db.commit()
            errors += 1
        if sent + skipped + errors >= limit:
            break
    return {"sent": sent, "skipped": skipped, "errors": errors}
