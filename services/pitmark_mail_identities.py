from __future__ import annotations

import json
from email.utils import parseaddr

from services import google_gmail
from services import pitmark_mail as base

IDENTITIES = {
    "justin": {
        "key": "justin",
        "label": "Justin / General",
        "name": "Pitmark Racing Co.",
        "address": "justin@pitmarkracing.com",
    },
    "sales": {
        "key": "sales",
        "label": "Sales",
        "name": "Pitmark Racing Co. Sales",
        "address": "sales@pitmarkracing.com",
    },
    "partnerships": {
        "key": "partnerships",
        "label": "Partnerships",
        "name": "Pitmark Racing Co. Partnerships",
        "address": "partnerships@pitmarkracing.com",
    },
    "support": {
        "key": "support",
        "label": "Customer Service",
        "name": "Pitmark Racing Co. Customer Service",
        "address": "support@pitmarkracing.com",
    },
    "orders": {
        "key": "orders",
        "label": "Orders",
        "name": "Pitmark Racing Co. Orders",
        "address": "orders@pitmarkracing.com",
    },
    "hello": {
        "key": "hello",
        "label": "Hello / General",
        "name": "Pitmark Racing Co.",
        "address": "hello@pitmarkracing.com",
    },
    "prt": {
        "key": "prt",
        "label": "PRT / Ecosystem Support",
        "name": "Pitmark Racing Tools",
        "address": "prt@pitmarkracing.com",
    },
    "marketing": {
        "key": "marketing",
        "label": "Marketing",
        "name": "Pitmark Racing Co. Marketing",
        "address": "marketing@pitmarkracing.com",
    },
    "outreach": {
        "key": "outreach",
        "label": "Outreach",
        "name": "Pitmark Racing Co. Outreach",
        "address": "outreach@pitmarkracing.com",
    },
}


def _identity_label(address: str) -> str:
    local = address.split("@", 1)[0].lower()
    return {
        "justin": "Justin / General",
        "sales": "Sales",
        "support": "Customer Service",
        "partnerships": "Partnerships / Sponsorships",
        "prt": "PRT / Ecosystem Support",
        "marketing": "Marketing",
        "outreach": "Outreach",
        "orders": "Orders",
        "hello": "Hello / General",
    }.get(local, local.replace(".", " ").replace("-", " ").title())


def _available_identities() -> dict[str, dict]:
    send_as = google_gmail.list_send_as()
    if not send_as:
        if google_gmail.credentials_configured():
            name, address = parseaddr(base.default_sender())
            address = (address or google_gmail.gmail_user()).strip().lower()
            key = address.split("@", 1)[0] if "@" in address else "primary"
            return {
                key: {
                    "key": key,
                    "label": _identity_label(address),
                    "name": name or "Pitmark Racing Co.",
                    "address": address,
                    "primary": True,
                    "gmail_default": True,
                }
            }
        return IDENTITIES
    rows: dict[str, dict] = {}
    domain = google_gmail.business_domain()
    for value in send_as:
        address = str(value.get("sendAsEmail") or "").strip().lower()
        verification = str(value.get("verificationStatus") or "").strip().lower()
        if not address.endswith(f"@{domain}"):
            continue
        if verification and verification != "accepted" and not value.get("isPrimary"):
            continue
        key = address.split("@", 1)[0]
        rows[key] = {
            "key": key,
            "label": _identity_label(address),
            "name": str(value.get("displayName") or "Pitmark Racing Co."),
            "address": address,
            "verification_status": value.get("verificationStatus"),
            "primary": bool(value.get("isPrimary")),
            "gmail_default": bool(value.get("isDefault")),
        }
    return rows or IDENTITIES


def _from_value(identity: dict) -> str:
    return f'{identity["name"]} <{identity["address"]}>'


def list_identities() -> list[dict]:
    default_address = parseaddr(base.default_sender())[1].lower()
    rows = []
    for identity in _available_identities().values():
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
    for identity in _available_identities().values():
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
    except (json.JSONDecodeError, TypeError):
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
    if configured:
        return configured
    available = list(_available_identities().values())
    primary = next((x for x in available if x.get("gmail_default") or x.get("primary")), None)
    return primary or available[0]


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
    message_headers: dict[str, str] | None = None,
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
    headers: dict[str, str] = {
        str(name): str(value)
        for name, value in (message_headers or {}).items()
        if name and value
    }
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
            provider_payload_json=json.dumps({
                "provider": "google_workspace",
                "gmail_message_id": result.get("id"),
                "gmail_thread_id": result.get("threadId"),
                "label_ids": result.get("labelIds") or [],
            }),
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
