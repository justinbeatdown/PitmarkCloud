from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from email.utils import parseaddr

import httpx
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal

RESEND_API = "https://api.resend.com"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(value) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _loads(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def send_api_key() -> str:
    return _env("RESEND_API_KEY")


def inbound_api_key() -> str:
    return _env("RESEND_INBOUND_API_KEY") or send_api_key()


def webhook_secret() -> str:
    return _env("RESEND_WEBHOOK_SECRET")


def default_sender() -> str:
    return _env("PITMARK_EMAIL_FROM", "Pitmark Racing Co. <mail@mail.pitmarkracing.com>")


def default_reply_to() -> str | None:
    return _env("PITMARK_EMAIL_REPLY_TO") or None


def mailbox_domain() -> str:
    return _env("PITMARK_EMAIL_DOMAIN", "mail.pitmarkracing.com")


class MailThread(Base):
    __tablename__ = "pitmark_mail_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(500), default="(no subject)")
    normalized_subject: Mapped[str] = mapped_column(String(500), index=True)
    participants_json: Mapped[str] = mapped_column(Text, default="[]")
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MailMessage(Base):
    __tablename__ = "pitmark_mail_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(Integer, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    rfc_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    direction: Mapped[str] = mapped_column(String(20), default="inbound", index=True)
    status: Mapped[str] = mapped_column(String(30), default="received", index=True)
    from_address: Mapped[str] = mapped_column(String(500), default="")
    to_json: Mapped[str] = mapped_column(Text, default="[]")
    cc_json: Mapped[str] = mapped_column(Text, default="[]")
    bcc_json: Mapped[str] = mapped_column(Text, default="[]")
    reply_to_json: Mapped[str] = mapped_column(Text, default="[]")
    subject: Mapped[str] = mapped_column(String(500), default="(no subject)")
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    references_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    provider_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _normalize_subject(subject: str) -> str:
    s = (subject or "(no subject)").strip()
    while True:
        lowered = s.lower()
        if lowered.startswith("re:") or lowered.startswith("fw:") or lowered.startswith("fwd:"):
            s = s.split(":", 1)[1].strip()
        else:
            break
    return " ".join(s.lower().split())[:500]


def _participants(*values) -> list[str]:
    found: list[str] = []
    for value in values:
        if isinstance(value, str):
            value = [value]
        for item in value or []:
            item = str(item or "").strip()
            if item and item.lower() not in {x.lower() for x in found}:
                found.append(item)
    return found


def _find_or_create_thread(db, subject: str, participants: list[str], *, bump_unread: bool) -> MailThread:
    normalized = _normalize_subject(subject)
    thread = db.scalars(
        select(MailThread).where(MailThread.normalized_subject == normalized).order_by(MailThread.last_message_at.desc())
    ).first()
    now = utcnow()
    if thread is None:
        thread = MailThread(
            subject=(subject or "(no subject)")[:500],
            normalized_subject=normalized,
            participants_json=_json(participants),
            unread_count=1 if bump_unread else 0,
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(thread)
        db.flush()
    else:
        merged = _participants(_loads(thread.participants_json, []), participants)
        thread.participants_json = _json(merged)
        thread.last_message_at = now
        thread.updated_at = now
        if bump_unread:
            thread.unread_count = int(thread.unread_count or 0) + 1
    return thread


def serialize_message(message: MailMessage) -> dict:
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "provider_message_id": message.provider_message_id,
        "rfc_message_id": message.rfc_message_id,
        "direction": message.direction,
        "status": message.status,
        "from": message.from_address,
        "to": _loads(message.to_json, []),
        "cc": _loads(message.cc_json, []),
        "bcc": _loads(message.bcc_json, []),
        "reply_to": _loads(message.reply_to_json, []),
        "subject": message.subject,
        "text": message.text_body or "",
        "html": message.html_body or "",
        "in_reply_to": message.in_reply_to,
        "references": message.references_header,
        "is_read": bool(message.is_read),
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
    }


def serialize_thread(thread: MailThread) -> dict:
    return {
        "id": thread.id,
        "subject": thread.subject,
        "participants": _loads(thread.participants_json, []),
        "unread_count": int(thread.unread_count or 0),
        "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
    }


def status() -> dict:
    sender_name, sender_address = parseaddr(default_sender())
    return {
        "sending_configured": bool(send_api_key()),
        "inbound_fetch_configured": bool(inbound_api_key()),
        "webhook_verification_configured": bool(webhook_secret()),
        "mailbox_domain": mailbox_domain(),
        "default_sender": default_sender(),
        "default_sender_address": sender_address,
        "default_sender_name": sender_name,
        "reply_to": default_reply_to(),
    }


def list_threads(folder: str = "inbox", limit: int = 100) -> list[dict]:
    folder = (folder or "inbox").lower().strip()
    with SessionLocal() as db:
        direction = "outbound" if folder in {"sent", "drafts"} else "inbound"
        status_filter = "draft" if folder == "drafts" else None
        stmt = select(MailMessage).where(MailMessage.direction == direction)
        if status_filter:
            stmt = stmt.where(MailMessage.status == status_filter)
        elif folder == "sent":
            stmt = stmt.where(MailMessage.status != "draft")
        stmt = stmt.order_by(MailMessage.created_at.desc()).limit(max(1, min(limit, 250)))
        messages = list(db.scalars(stmt).all())
        thread_ids = []
        latest_by_thread: dict[int, MailMessage] = {}
        for msg in messages:
            if msg.thread_id not in latest_by_thread:
                latest_by_thread[msg.thread_id] = msg
                thread_ids.append(msg.thread_id)
        threads = {
            t.id: t for t in db.scalars(select(MailThread).where(MailThread.id.in_(thread_ids))).all()
        } if thread_ids else {}
        output = []
        for thread_id in thread_ids:
            msg = latest_by_thread[thread_id]
            thread = threads.get(thread_id)
            row = serialize_message(msg)
            row["thread"] = serialize_thread(thread) if thread else {"id": thread_id, "subject": msg.subject, "unread_count": 0}
            output.append(row)
        return output


def get_thread(thread_id: int, mark_read: bool = True) -> dict | None:
    with SessionLocal() as db:
        thread = db.get(MailThread, thread_id)
        if not thread:
            return None
        messages = list(db.scalars(
            select(MailMessage).where(MailMessage.thread_id == thread_id).order_by(MailMessage.created_at.asc())
        ).all())
        if mark_read:
            for msg in messages:
                if msg.direction == "inbound":
                    msg.is_read = True
                    msg.updated_at = utcnow()
            thread.unread_count = 0
            thread.updated_at = utcnow()
            db.commit()
        return {"thread": serialize_thread(thread), "messages": [serialize_message(x) for x in messages]}


def _resend_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def send_message(*, to: list[str], subject: str, text: str = "", html: str = "", cc: list[str] | None = None,
                 bcc: list[str] | None = None, reply_to: list[str] | None = None, reply_to_message_id: int | None = None) -> dict:
    key = send_api_key()
    if not key:
        raise RuntimeError("RESEND_API_KEY is not configured in Pitmark Cloud.")
    to = [x.strip() for x in to if str(x).strip()]
    if not to:
        raise ValueError("At least one recipient is required.")
    subject = (subject or "(no subject)").strip()[:500]
    cc = [x.strip() for x in (cc or []) if str(x).strip()]
    bcc = [x.strip() for x in (bcc or []) if str(x).strip()]
    reply_to = [x.strip() for x in (reply_to or []) if str(x).strip()]
    headers: dict[str, str] = {}
    parent: MailMessage | None = None
    with SessionLocal() as db:
        if reply_to_message_id:
            parent = db.get(MailMessage, reply_to_message_id)
            if parent:
                if parent.rfc_message_id:
                    headers["In-Reply-To"] = parent.rfc_message_id
                    refs = (parent.references_header or "").strip()
                    headers["References"] = (refs + " " + parent.rfc_message_id).strip()
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"
        payload: dict = {
            "from": default_sender(),
            "to": to,
            "subject": subject,
        }
        if text:
            payload["text"] = text
        if html:
            payload["html"] = html
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        configured_reply_to = reply_to or ([default_reply_to()] if default_reply_to() else [])
        if configured_reply_to:
            payload["reply_to"] = configured_reply_to
        if headers:
            payload["headers"] = headers
        with httpx.Client(timeout=20.0) as client:
            response = client.post(f"{RESEND_API}/emails", headers=_resend_headers(key), json=payload)
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(f"Resend send failed ({response.status_code}): {detail}")
            result = response.json()
        participants = _participants(default_sender(), to, cc, bcc)
        thread = db.get(MailThread, parent.thread_id) if parent else None
        if thread is None:
            thread = _find_or_create_thread(db, subject, participants, bump_unread=False)
        else:
            thread.last_message_at = utcnow()
            thread.updated_at = utcnow()
        msg = MailMessage(
            thread_id=thread.id,
            provider_message_id=str(result.get("id") or "") or None,
            direction="outbound",
            status="sent",
            from_address=default_sender(),
            to_json=_json(to),
            cc_json=_json(cc),
            bcc_json=_json(bcc),
            reply_to_json=_json(configured_reply_to),
            subject=subject,
            text_body=text or None,
            html_body=html or None,
            in_reply_to=parent.rfc_message_id if parent else None,
            references_header=headers.get("References"),
            is_read=True,
            provider_payload_json=json.dumps(result),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return serialize_message(msg)


def save_draft(*, to: list[str], subject: str, text: str = "", html: str = "", cc: list[str] | None = None,
               bcc: list[str] | None = None, draft_id: int | None = None) -> dict:
    with SessionLocal() as db:
        msg = db.get(MailMessage, draft_id) if draft_id else None
        if msg and msg.status != "draft":
            raise ValueError("Only draft messages can be updated.")
        if msg is None:
            thread = _find_or_create_thread(db, subject, _participants(default_sender(), to, cc, bcc), bump_unread=False)
            msg = MailMessage(thread_id=thread.id, direction="outbound", status="draft", created_at=utcnow())
            db.add(msg)
        msg.from_address = default_sender()
        msg.to_json = _json(to)
        msg.cc_json = _json(cc or [])
        msg.bcc_json = _json(bcc or [])
        msg.subject = (subject or "(no subject)")[:500]
        msg.text_body = text or None
        msg.html_body = html or None
        msg.is_read = True
        msg.updated_at = utcnow()
        db.commit()
        db.refresh(msg)
        return serialize_message(msg)


def verify_svix_signature(raw_body: bytes, headers) -> bool:
    secret = webhook_secret()
    if not secret:
        return False
    message_id = headers.get("svix-id") or headers.get("webhook-id")
    timestamp = headers.get("svix-timestamp") or headers.get("webhook-timestamp")
    signatures = headers.get("svix-signature") or headers.get("webhook-signature") or ""
    if not message_id or not timestamp or not signatures:
        return False
    try:
        ts = int(timestamp)
    except Exception:
        return False
    if abs(int(time.time()) - ts) > 300:
        return False
    encoded = secret.split("_", 1)[1] if secret.startswith("whsec_") else secret
    try:
        key = base64.b64decode(encoded)
    except Exception:
        return False
    signed = f"{message_id}.{timestamp}.".encode() + raw_body
    digest = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    for token in signatures.split():
        if "," in token:
            version, value = token.split(",", 1)
            if version == "v1" and hmac.compare_digest(value, digest):
                return True
    return False


def _fetch_received_email(email_id: str) -> dict:
    key = inbound_api_key()
    if not key:
        return {}
    with httpx.Client(timeout=20.0) as client:
        response = client.get(f"{RESEND_API}/emails/receiving/{email_id}", headers=_resend_headers(key))
        if response.status_code >= 400:
            return {"_fetch_error": f"{response.status_code}: {response.text[:500]}"}
        return response.json()


def ingest_resend_event(event: dict) -> dict:
    if str(event.get("type") or "") != "email.received":
        return {"ignored": True, "type": event.get("type")}
    data = event.get("data") or {}
    provider_id = str(data.get("email_id") or data.get("id") or "").strip()
    if not provider_id:
        raise ValueError("Resend webhook did not include an email id.")
    with SessionLocal() as db:
        existing = db.scalars(select(MailMessage).where(MailMessage.provider_message_id == provider_id)).first()
        if existing:
            return {"duplicate": True, "message_id": existing.id, "thread_id": existing.thread_id}
    full = _fetch_received_email(provider_id)
    source = {**data, **({k: v for k, v in full.items() if k != "_fetch_error"} if full else {})}
    sender = str(source.get("from") or data.get("from") or "")
    to = source.get("to") or data.get("to") or []
    cc = source.get("cc") or data.get("cc") or []
    bcc = source.get("bcc") or data.get("bcc") or []
    reply_to = source.get("reply_to") or source.get("reply-to") or []
    subject = str(source.get("subject") or data.get("subject") or "(no subject)")[:500]
    text = source.get("text") or source.get("text_body") or ""
    html = source.get("html") or source.get("html_body") or ""
    headers_map = source.get("headers") or {}
    if isinstance(headers_map, list):
        headers_map = {str(x.get("name") or "").lower(): str(x.get("value") or "") for x in headers_map if isinstance(x, dict)}
    rfc_message_id = str(source.get("message_id") or data.get("message_id") or headers_map.get("message-id") or "") or None
    in_reply_to = headers_map.get("in-reply-to") if isinstance(headers_map, dict) else None
    references = headers_map.get("references") if isinstance(headers_map, dict) else None
    now = utcnow()
    with SessionLocal() as db:
        thread = None
        if in_reply_to:
            parent = db.scalars(select(MailMessage).where(MailMessage.rfc_message_id == in_reply_to)).first()
            if parent:
                thread = db.get(MailThread, parent.thread_id)
        if thread is None:
            thread = _find_or_create_thread(db, subject, _participants(sender, to, cc), bump_unread=True)
        else:
            thread.unread_count = int(thread.unread_count or 0) + 1
            thread.last_message_at = now
            thread.updated_at = now
        msg = MailMessage(
            thread_id=thread.id,
            provider_message_id=provider_id,
            rfc_message_id=rfc_message_id,
            direction="inbound",
            status="received",
            from_address=sender,
            to_json=_json(to),
            cc_json=_json(cc),
            bcc_json=_json(bcc),
            reply_to_json=_json(reply_to),
            subject=subject,
            text_body=str(text or "") or None,
            html_body=str(html or "") or None,
            in_reply_to=in_reply_to,
            references_header=references,
            is_read=False,
            provider_payload_json=json.dumps({"event": event, "received": full}, ensure_ascii=False)[:200000],
            created_at=now,
            updated_at=now,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return {
            "ok": True,
            "message_id": msg.id,
            "thread_id": msg.thread_id,
            "body_fetched": bool(text or html),
            "fetch_error": full.get("_fetch_error") if isinstance(full, dict) else None,
        }
