from __future__ import annotations

import base64
import binascii
import json
import os
from datetime import datetime, timezone
from email.utils import formataddr, getaddresses, parseaddr, parsedate_to_datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services import google_gmail
from services.database import Base, SessionLocal


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json(value) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _loads(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (json.JSONDecodeError, TypeError):
        return fallback


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def default_sender() -> str:
    account = google_gmail.gmail_user()
    if account == "me":
        account = "justin@pitmarkracing.com"
    return _env("PITMARK_EMAIL_FROM", f"Pitmark Racing Co. <{account}>")


def default_reply_to() -> str | None:
    return _env("PITMARK_EMAIL_REPLY_TO") or None


def mailbox_domain() -> str:
    return _env("PITMARK_EMAIL_DOMAIN", "pitmarkracing.com")


def department_for_addresses(*values) -> str:
    domain = mailbox_domain().lower().lstrip("@")
    addresses: list[str] = []
    for value in values:
        if isinstance(value, str):
            value = [value]
        addresses.extend(
            address.strip().lower()
            for _, address in getaddresses([str(item) for item in (value or [])])
            if address.strip()
        )
    for local in google_gmail.DEPARTMENT_LABELS:
        if f"{local}@{domain}" in addresses:
            return local
    return "general"


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
        if lowered.startswith(("re:", "fw:", "fwd:")):
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
    provider = _loads(message.provider_payload_json, {})
    if not isinstance(provider, dict):
        provider = {}
    to = _loads(message.to_json, [])
    cc = _loads(message.cc_json, [])
    bcc = _loads(message.bcc_json, [])
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "provider_message_id": message.provider_message_id,
        "rfc_message_id": message.rfc_message_id,
        "direction": message.direction,
        "status": message.status,
        "from": message.from_address,
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "reply_to": _loads(message.reply_to_json, []),
        "subject": message.subject,
        "text": message.text_body or "",
        "html": message.html_body or "",
        "in_reply_to": message.in_reply_to,
        "references": message.references_header,
        "is_read": bool(message.is_read),
        "department": provider.get("department") or department_for_addresses(to, cc, bcc),
        "delivered_to": provider.get("delivered_to") or [],
        "gmail_labels": provider.get("label_ids") or [],
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
    connection = google_gmail.connection_status()
    return {
        "provider": "google_workspace",
        "provider_label": "Google Workspace / Gmail",
        "sending_configured": bool(connection.get("connected")),
        "inbound_fetch_configured": bool(connection.get("connected")),
        "mailbox_connected": bool(connection.get("connected")),
        "sync_mode": "gmail_api_poll",
        "sync_interval_seconds": max(30, int(_env("PITMARK_GMAIL_SYNC_SECONDS", "60"))),
        "mailbox_domain": mailbox_domain(),
        "default_sender": default_sender(),
        "default_sender_address": connection.get("email_address") or sender_address,
        "default_sender_name": sender_name,
        "reply_to": default_reply_to(),
        "google_workspace": connection,
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
        elif folder == "spam":
            stmt = stmt.where(MailMessage.status == "spam")
        else:
            stmt = stmt.where(MailMessage.status != "spam")
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
    provider_ids: list[str] = []
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
                    provider = _loads(msg.provider_payload_json, {})
                    if (
                        msg.provider_message_id
                        and isinstance(provider, dict)
                        and provider.get("provider") == "google_workspace"
                    ):
                        provider_ids.append(msg.provider_message_id)
            thread.unread_count = 0
            thread.updated_at = utcnow()
            db.commit()
        result = {"thread": serialize_thread(thread), "messages": [serialize_message(x) for x in messages]}
    for provider_id in provider_ids:
        try:
            google_gmail.mark_read(provider_id)
        except RuntimeError:
            pass
    return result


def send_message(*, to: list[str], subject: str, text: str = "", html: str = "", cc: list[str] | None = None,
                 bcc: list[str] | None = None, reply_to: list[str] | None = None, reply_to_message_id: int | None = None) -> dict:
    if not google_gmail.credentials_configured():
        raise RuntimeError("Google Workspace Gmail credentials are not configured in Pitmark Cloud.")
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
        configured_reply_to = reply_to or ([default_reply_to()] if default_reply_to() else [])
        parent_payload = _loads(parent.provider_payload_json, {}) if parent else {}
        raw = google_gmail.build_raw_message(
            sender=default_sender(),
            to=to,
            cc=cc,
            bcc=bcc,
            reply_to=configured_reply_to,
            subject=subject,
            text=text,
            html=html,
            headers=headers,
        )
        result = google_gmail.send_message(
            raw=raw,
            thread_id=parent_payload.get("gmail_thread_id") if isinstance(parent_payload, dict) else None,
        )
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
            provider_payload_json=json.dumps({
                "provider": "google_workspace",
                "gmail_message_id": result.get("id"),
                "gmail_thread_id": result.get("threadId"),
                "label_ids": result.get("labelIds") or [],
            }),
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


def _decode_gmail_data(value: str | None) -> str:
    if not value:
        return ""
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (binascii.Error, UnicodeError, ValueError):
        return ""


def _gmail_addresses(value: str | None) -> list[str]:
    rows = []
    for name, address in getaddresses([value or ""]):
        if address:
            rows.append(formataddr((name, address)) if name else address)
    return rows


def _gmail_parts(part: dict, text_parts: list[str], html_parts: list[str], attachments: list[dict]) -> None:
    body = part.get("body") or {}
    mime = str(part.get("mimeType") or "").lower()
    filename = str(part.get("filename") or "").strip()
    if filename and body.get("attachmentId"):
        attachments.append({
            "filename": filename[:255],
            "content_type": mime or "application/octet-stream",
            "size": int(body.get("size") or 0),
            "gmail_attachment_id": str(body.get("attachmentId")),
        })
    elif mime == "text/plain" and body.get("data"):
        text_parts.append(_decode_gmail_data(str(body.get("data"))))
    elif mime == "text/html" and body.get("data"):
        html_parts.append(_decode_gmail_data(str(body.get("data"))))
    for child in part.get("parts") or []:
        if isinstance(child, dict):
            _gmail_parts(child, text_parts, html_parts, attachments)


def _gmail_received_at(payload: dict, headers: dict[str, str]) -> datetime:
    try:
        internal_date = int(payload.get("internalDate") or 0)
    except (TypeError, ValueError):
        internal_date = 0
    if internal_date > 0:
        try:
            return datetime.fromtimestamp(internal_date / 1000, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return utcnow()
    try:
        parsed = parsedate_to_datetime(headers.get("date") or "")
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return utcnow()


def ingest_gmail_message(payload: dict) -> dict:
    provider_id = str(payload.get("id") or "").strip()
    if not provider_id:
        raise ValueError("Gmail did not include a message id.")
    with SessionLocal() as db:
        existing = db.scalar(select(MailMessage).where(MailMessage.provider_message_id == provider_id))
        if existing:
            return {"duplicate": True, "message_id": existing.id, "thread_id": existing.thread_id}

    root = payload.get("payload") or {}
    headers = {
        str(row.get("name") or "").lower(): str(row.get("value") or "")
        for row in (root.get("headers") or [])
        if isinstance(row, dict)
    }
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict] = []
    _gmail_parts(root, text_parts, html_parts, attachments)
    sender = headers.get("from") or ""
    to = _gmail_addresses(headers.get("to"))
    cc = _gmail_addresses(headers.get("cc"))
    bcc = _gmail_addresses(headers.get("bcc"))
    reply_to = _gmail_addresses(headers.get("reply-to"))
    subject = (headers.get("subject") or "(no subject)")[:500]
    in_reply_to = headers.get("in-reply-to") or None
    references = headers.get("references") or None
    labels = [str(x) for x in (payload.get("labelIds") or [])]
    delivered_to = [
        address
        for address in _gmail_addresses(headers.get("delivered-to"))
        if address.lower().endswith(f"@{mailbox_domain().lower().lstrip('@')}")
    ]
    department = department_for_addresses(delivered_to, to, cc, bcc)
    try:
        routed = google_gmail.apply_department_labels(provider_id, delivered_to + to + cc + bcc)
        if routed.get("labelIds"):
            labels = [str(value) for value in routed.get("labelIds") or []]
    except RuntimeError:
        pass
    now = _gmail_received_at(payload, headers)
    provider_record = {
        "provider": "google_workspace",
        "gmail_message_id": provider_id,
        "gmail_thread_id": payload.get("threadId"),
        "label_ids": labels,
        "department": department,
        "delivered_to": delivered_to,
        "snippet": payload.get("snippet") or "",
        "attachments": attachments,
        "automation_headers": {
            key: headers.get(key) or ""
            for key in (
                "auto-submitted",
                "precedence",
                "list-id",
                "list-unsubscribe",
                "x-auto-response-suppress",
            )
            if headers.get(key)
        },
    }
    with SessionLocal() as db:
        thread = None
        if in_reply_to:
            parent = db.scalar(select(MailMessage).where(MailMessage.rfc_message_id == in_reply_to))
            if parent:
                thread = db.get(MailThread, parent.thread_id)
        if thread is None:
            thread = _find_or_create_thread(db, subject, _participants(sender, to, cc), bump_unread="UNREAD" in labels)
        else:
            if "UNREAD" in labels:
                thread.unread_count = int(thread.unread_count or 0) + 1
            thread.last_message_at = now
            thread.updated_at = utcnow()
        msg = MailMessage(
            thread_id=thread.id,
            provider_message_id=provider_id,
            rfc_message_id=headers.get("message-id") or None,
            direction="inbound",
            status="spam" if "SPAM" in labels else "received",
            from_address=sender,
            to_json=_json(to),
            cc_json=_json(cc),
            bcc_json=_json(bcc),
            reply_to_json=_json(reply_to),
            subject=subject,
            text_body="\n".join(x for x in text_parts if x).strip() or None,
            html_body="\n".join(x for x in html_parts if x).strip() or None,
            in_reply_to=in_reply_to,
            references_header=references,
            is_read="UNREAD" not in labels,
            provider_payload_json=json.dumps(provider_record, ensure_ascii=False),
            created_at=now,
            updated_at=utcnow(),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return {"ok": True, "message_id": msg.id, "thread_id": msg.thread_id, "provider_message_id": provider_id}


def sync_gmail_inbox(limit: int | None = None) -> dict:
    if not google_gmail.credentials_configured():
        return {"connected": False, "synced": 0, "new_message_ids": [], "reason": "gmail-not-configured"}
    resolved_limit = limit or int(_env("PITMARK_GMAIL_SYNC_LIMIT", "100"))
    workspace_setup = google_gmail.ensure_workspace_setup()
    try:
        provider_ids = google_gmail.list_inbox_message_ids(resolved_limit)
    except RuntimeError as exc:
        return {
            "connected": False,
            "provider": "google_workspace",
            "synced": 0,
            "new_message_ids": [],
            "errors": [str(exc)[:500]],
            "workspace_setup": workspace_setup,
        }
    with SessionLocal() as db:
        known = set(db.scalars(select(MailMessage.provider_message_id).where(
            MailMessage.provider_message_id.in_(provider_ids)
        )).all()) if provider_ids else set()
    new_message_ids: list[int] = []
    errors: list[str] = []
    for provider_id in reversed(provider_ids):
        if provider_id in known:
            continue
        try:
            result = ingest_gmail_message(google_gmail.get_message(provider_id))
            if result.get("message_id"):
                new_message_ids.append(int(result["message_id"]))
        except (RuntimeError, ValueError) as exc:
            errors.append(str(exc)[:300])
    return {
        "connected": True,
        "provider": "google_workspace",
        "checked": len(provider_ids),
        "synced": len(new_message_ids),
        "new_message_ids": new_message_ids,
        "errors": errors[:5],
        "workspace_setup": workspace_setup,
    }
