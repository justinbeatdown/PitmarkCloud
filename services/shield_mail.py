from __future__ import annotations

import json
import re
from html import unescape

from sqlalchemy import select

from services.control_center import SecurityAuditEvent, ShieldEvent, classify, fingerprint, utcnow
from services.database import SessionLocal
from services.pitmark_mail import MailMessage, ingest_resend_event as base_ingest_resend_event
from services.shield_ecosystem import inspect_external_url

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.I)
TAG_RE = re.compile(r'<[^>]+>')
PHISHING_PATTERNS = (
    "verify your account",
    "verify account",
    "confirm your password",
    "password expires",
    "password has expired",
    "urgent action required",
    "immediate action required",
    "suspended account",
    "account suspended",
    "wire transfer",
    "gift card",
    "crypto payment",
    "seed phrase",
    "recovery phrase",
    "click immediately",
)


def _plain_text(message: MailMessage) -> str:
    if message.text_body:
        return str(message.text_body)
    if message.html_body:
        return unescape(TAG_RE.sub(" ", str(message.html_body)))
    return ""


def _shield_result(message: MailMessage) -> dict:
    body = _plain_text(message)
    result = dict(classify(message.from_address or "", message.subject or "", body))
    reasons = list(result.get("reasons") or [])
    text = f"{message.subject or ''} {body}".lower()

    phishing_hits = [p for p in PHISHING_PATTERNS if p in text]
    if phishing_hits:
        result["classification"] = "Review"
        result["confidence"] = max(float(result.get("confidence") or 0), 0.94)
        result["protected"] = True
        reasons.extend(["phishing-language"] + phishing_hits[:3])

    blocked_urls = []
    for url in URL_RE.findall(f"{body}\n{message.html_body or ''}")[:40]:
        check = inspect_external_url(url.rstrip(").,;"))
        if not check.get("safe"):
            blocked_urls.append(check.get("reason") or "unsafe-url")
    if blocked_urls:
        result["classification"] = "Review"
        result["confidence"] = max(float(result.get("confidence") or 0), 0.99)
        result["protected"] = True
        reasons.extend(["shield-blocked-url"] + blocked_urls[:3])

    result["reasons"] = list(dict.fromkeys(str(x) for x in reasons if x))
    return result


def _action_for(result: dict) -> str:
    classification = str(result.get("classification") or "Review")
    if classification == "Spam" and not result.get("protected"):
        return "archive-recommended"
    if classification == "Review":
        return "flag-review"
    return "allow"


def protect_message(message_id: int) -> dict | None:
    with SessionLocal() as db:
        message = db.get(MailMessage, message_id)
        if not message or message.direction != "inbound":
            return None

        source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
        existing = db.scalar(select(ShieldEvent).where(ShieldEvent.source_message_id == source_id))
        if existing:
            return {
                "event_id": existing.id,
                "classification": existing.classification,
                "confidence": existing.confidence,
                "protected": existing.protected,
                "action_taken": existing.action_taken,
            }

        result = _shield_result(message)
        event = ShieldEvent(
            source_message_id=source_id,
            sender=message.from_address or "",
            subject=message.subject or "",
            fingerprint=fingerprint(message.subject or "", _plain_text(message)),
            classification=result["classification"],
            confidence=float(result["confidence"]),
            protected=bool(result["protected"]),
            reasons_json=json.dumps(result["reasons"], ensure_ascii=False),
            action_taken=_action_for(result),
            acknowledged=False,
            created_at=utcnow(),
        )
        db.add(event)

        # Persist the Shield verdict alongside the original Resend payload without
        # changing the mail schema or delivery behavior.
        try:
            payload = json.loads(message.provider_payload_json or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}
        payload["shield"] = {
            "classification": result["classification"],
            "confidence": float(result["confidence"]),
            "protected": bool(result["protected"]),
            "reasons": result["reasons"],
            "action": event.action_taken,
        }
        message.provider_payload_json = json.dumps(payload, ensure_ascii=False)[:200000]
        message.updated_at = utcnow()

        severity = "warning" if result["classification"] in {"Review", "Spam"} else "info"
        db.add(SecurityAuditEvent(
            event_type="pitmark_mail_scanned",
            severity=severity,
            actor=message.from_address or None,
            source="shield_mail",
            detail=f"Pitmark Mail #{message.id} classified {result['classification']} ({round(float(result['confidence']) * 100)}%).",
            created_at=utcnow(),
        ))
        db.commit()
        db.refresh(event)
        return {
            "event_id": event.id,
            "classification": event.classification,
            "confidence": event.confidence,
            "protected": event.protected,
            "action_taken": event.action_taken,
        }


def ingest_resend_event_protected(event: dict) -> dict:
    result = base_ingest_resend_event(event)
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if message_id:
        shield = protect_message(int(message_id))
        result["shield"] = shield
    return result


def sync_unprotected_mail(limit: int = 250) -> dict:
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(MailMessage)
            .where(MailMessage.direction == "inbound")
            .order_by(MailMessage.id.desc())
            .limit(max(1, min(limit, 500)))
        ).all())

    scanned = 0
    for message in rows:
        with SessionLocal() as db:
            source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
            exists = db.scalar(select(ShieldEvent.id).where(ShieldEvent.source_message_id == source_id))
        if exists:
            continue
        if protect_message(message.id):
            scanned += 1

    with SessionLocal() as db:
        total = len(db.scalars(select(ShieldEvent.id).where(ShieldEvent.source_message_id.like("pitmark-mail:%"))).all())
        review = len(db.scalars(select(ShieldEvent.id).where(
            ShieldEvent.source_message_id.like("pitmark-mail:%"),
            ShieldEvent.classification == "Review",
        )).all())
    return {"connected": True, "scanned_now": scanned, "protected_events": total, "review_count": review}


def shield_for_message(message: MailMessage) -> dict | None:
    try:
        payload = json.loads(message.provider_payload_json or "{}")
        value = payload.get("shield") if isinstance(payload, dict) else None
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def decorate_message_dict(row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    message_id = row.get("id")
    if not message_id:
        return row
    with SessionLocal() as db:
        message = db.get(MailMessage, int(message_id))
        if message:
            row = dict(row)
            row["shield"] = shield_for_message(message)
    return row


def decorate_threads(rows: list[dict]) -> list[dict]:
    return [decorate_message_dict(dict(row)) for row in rows]


def decorate_thread(result: dict | None) -> dict | None:
    if not result:
        return result
    output = dict(result)
    output["messages"] = [decorate_message_dict(dict(row)) for row in (result.get("messages") or [])]
    return output
