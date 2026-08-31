from __future__ import annotations

import json
from email.utils import parseaddr

import httpx

from services import pitmark_mail as base


IDENTITIES = {
    "mail": {
        "key": "mail",
        "label": "Pitmark Mail",
        "name": "Pitmark Racing Co.",
        "address": "mail@mail.pitmarkracing.com",
    },
    "partnerships": {
        "key": "partnerships",
        "label": "Partnerships",
        "name": "Pitmark Racing Co. Partnerships",
        "address": "partnerships@mail.pitmarkracing.com",
    },
    "support": {
        "key": "support",
        "label": "Support",
        "name": "Pitmark Racing Co. Support",
        "address": "support@mail.pitmarkracing.com",
    },
    "orders": {
        "key": "orders",
        "label": "Orders",
        "name": "Pitmark Racing Co. Orders",
        "address": "orders@mail.pitmarkracing.com",
    },
    "hello": {
        "key": "hello",
        "label": "Hello / General",
        "name": "Pitmark Racing Co.",
        "address": "hello@mail.pitmarkracing.com",
    },
    "prt": {
        "key": "prt",
        "label": "PRT Support / Licensing",
        "name": "Pitmark Racing Tools",
        "address": "prt@mail.pitmarkracing.com",
    },
}


def _from_value(identity: dict) -> str:
    return f'{identity["name"]} <{identity["address"]}>'


def list_identities() -> list[dict]:
    default_address = parseaddr(base.default_sender())[1].lower()
    rows = []
    for identity in IDENTITIES.values():
        row = dict(identity)
        row["from"] = _from_value(identity)
        row["default"] = identity["address"].lower() == default_address
        rows.append(row)
    if not any(x["default"] for x in rows):
        rows[0]["default"] = True
    return rows


def _identity_from_value(value: str | None) -> dict | None:
    raw = (value or "").strip().lower()
    if not raw:
        return None
    parsed = parseaddr(value or "")[1].lower()
    for identity in IDENTITIES.values():
        if raw == identity["key"].lower():
            return identity
        if raw == identity["address"].lower():
            return identity
        if parsed and parsed == identity["address"].lower():
            return identity
    return None


def _recipient_identity(message) -> dict | None:
    if not message or getattr(message, "direction", "") != "inbound":
        return None
    try:
        recipients = json.loads(message.to_json or "[]")
    except Exception:
        recipients = []
    for recipient in recipients:
        identity = _identity_from_value(str(recipient))
        if identity:
            return identity
    return None


def resolve_identity(requested: str | None = None, parent=None) -> dict:
    if requested:
        identity = _identity_from_value(requested)
        if not identity:
            raise ValueError("That Pitmark Mail sending identity is not approved.")
        return identity

    inherited = _recipient_identity(parent)
    if inherited:
        return inherited

    configured = _identity_from_value(base.default_sender())
    return configured or IDENTITIES["mail"]


def status() -> dict:
    result = base.status()
    result["identities"] = list_identities()
    return result


def send_message(
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
) -> dict:
    key = base.send_api_key()
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

        payload: dict = {
            "from": sender,
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

        configured_reply_to = reply_to or [identity["address"]]
        if configured_reply_to:
            payload["reply_to"] = configured_reply_to
        if headers:
            payload["headers"] = headers

        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                f"{base.RESEND_API}/emails",
                headers=base._resend_headers(key),
                json=payload,
            )
            if response.status_code >= 400:
                detail = response.text[:1000]
                raise RuntimeError(f"Resend send failed ({response.status_code}): {detail}")
            result = response.json()

        participants = base._participants(sender, to, cc, bcc)
        thread = db.get(base.MailThread, parent.thread_id) if parent else None
        if thread is None:
            thread = base._find_or_create_thread(db, subject, participants, bump_unread=False)
        else:
            thread.last_message_at = base.utcnow()
            thread.updated_at = base.utcnow()

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
            provider_payload_json=json.dumps(result),
            created_at=base.utcnow(),
            updated_at=base.utcnow(),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return base.serialize_message(msg)


def save_draft(
    *,
    to: list[str],
    subject: str,
    text: str = "",
    html: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    draft_id: int | None = None,
    from_identity: str | None = None,
) -> dict:
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
        db.commit()
        db.refresh(msg)
        return base.serialize_message(msg)
