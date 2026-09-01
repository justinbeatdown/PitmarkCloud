from __future__ import annotations

import json

from services import google_gmail
from services import pitmark_mail as base
from services.pitmark_mail_attachments import normalize_attachments, stored_attachments
from services.pitmark_mail_identities import _from_value, resolve_identity


def send_rich_message(
    *,
    to: list[str],
    subject: str,
    text: str = "",
    html: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: list[str] | None = None,
    reply_to_message_id: int | None = None,
    from_identity: str | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    if not google_gmail.credentials_configured():
        raise RuntimeError("Google Workspace Gmail credentials are not configured in Pitmark Cloud.")

    to = [x.strip() for x in to if str(x).strip()]
    if not to:
        raise ValueError("At least one recipient is required.")

    subject = (subject or "(no subject)").strip()[:500]
    cc = [x.strip() for x in (cc or []) if str(x).strip()]
    bcc = [x.strip() for x in (bcc or []) if str(x).strip()]
    reply_to = [x.strip() for x in (reply_to or []) if str(x).strip()]
    gmail_attachments, stored = normalize_attachments(attachments)
    headers: dict[str, str] = {}
    parent = None

    with base.SessionLocal() as db:
        if reply_to_message_id:
            parent = db.get(base.MailMessage, reply_to_message_id)
            if parent:
                if parent.rfc_message_id:
                    headers["In-Reply-To"] = parent.rfc_message_id
                    refs = (parent.references_header or "").strip()
                    headers["References"] = (refs + " " + parent.rfc_message_id).strip()
                if not subject.lower().startswith("re:"):
                    subject = f"Re: {subject}"

        identity = resolve_identity(from_identity, parent=parent)
        sender = _from_value(identity)

        configured_reply_to = reply_to or [identity["address"]]
        parent_payload = base._loads(parent.provider_payload_json, {}) if parent else {}
        raw = google_gmail.build_raw_message(
            sender=sender,
            to=to,
            cc=cc,
            bcc=bcc,
            reply_to=configured_reply_to,
            subject=subject,
            text=text,
            html=html,
            headers=headers,
            attachments=gmail_attachments,
        )
        result = google_gmail.send_message(
            raw=raw,
            thread_id=parent_payload.get("gmail_thread_id") if isinstance(parent_payload, dict) else None,
        )

        participants = base._participants(sender, to, cc, bcc)
        thread = db.get(base.MailThread, parent.thread_id) if parent else None
        if thread is None:
            thread = base._find_or_create_thread(db, subject, participants, bump_unread=False)
        else:
            thread.last_message_at = base.utcnow()
            thread.updated_at = base.utcnow()

        provider_record = {
            "provider": "google_workspace",
            "gmail_message_id": result.get("id"),
            "gmail_thread_id": result.get("threadId"),
            "label_ids": result.get("labelIds") or [],
        }
        if stored:
            provider_record["attachments"] = [
                {
                    "filename": x["filename"],
                    "content_type": x["content_type"],
                    "size": x["size"],
                }
                for x in stored
            ]

        msg = base.MailMessage(
            thread_id=thread.id,
            provider_message_id=str(result.get("id") or "") or None,
            direction="outbound",
            status="sent",
            from_address=sender,
            to_json=base._json(to),
            cc_json=base._json(cc),
            bcc_json=base._json(bcc),
            reply_to_json=base._json(configured_reply_to),
            subject=subject,
            text_body=text or None,
            html_body=html or None,
            in_reply_to=parent.rfc_message_id if parent else None,
            references_header=headers.get("References"),
            is_read=True,
            provider_payload_json=json.dumps(provider_record, ensure_ascii=False),
            created_at=base.utcnow(),
            updated_at=base.utcnow(),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        row = base.serialize_message(msg)
        row["attachments"] = provider_record.get("attachments", [])
        return row


def save_rich_draft(
    *,
    to: list[str],
    subject: str,
    text: str = "",
    html: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    draft_id: int | None = None,
    from_identity: str | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    _, stored = normalize_attachments(attachments)

    with base.SessionLocal() as db:
        msg = db.get(base.MailMessage, draft_id) if draft_id else None
        if msg and msg.status != "draft":
            raise ValueError("Only draft messages can be updated.")

        identity = resolve_identity(from_identity)
        sender = _from_value(identity)

        if msg is None:
            thread = base._find_or_create_thread(
                db,
                subject,
                base._participants(sender, to, cc, bcc),
                bump_unread=False,
            )
            msg = base.MailMessage(
                thread_id=thread.id,
                direction="outbound",
                status="draft",
                created_at=base.utcnow(),
            )
            db.add(msg)

        msg.from_address = sender
        msg.to_json = base._json(to)
        msg.cc_json = base._json(cc or [])
        msg.bcc_json = base._json(bcc or [])
        msg.reply_to_json = base._json([identity["address"]])
        msg.subject = (subject or "(no subject)")[:500]
        msg.text_body = text or None
        msg.html_body = html or None
        msg.is_read = True
        msg.updated_at = base.utcnow()
        msg.provider_payload_json = json.dumps(
            {"draft_attachments": stored},
            ensure_ascii=False,
        )
        db.commit()
        db.refresh(msg)
        row = base.serialize_message(msg)
        row["attachments"] = [
            {
                "filename": x["filename"],
                "content_type": x["content_type"],
                "size": x["size"],
                "content": x["content"],
            }
            for x in stored
        ]
        return row


def draft_attachments(message_id: int) -> list[dict]:
    with base.SessionLocal() as db:
        msg = db.get(base.MailMessage, message_id)
        if not msg or msg.status != "draft":
            return []
        return stored_attachments(msg)
