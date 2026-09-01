from __future__ import annotations

import json
import re
from email.utils import parseaddr
from html import unescape

from sqlalchemy import select

from services.control_center import SecurityAuditEvent, ShieldEvent, classify, fingerprint, utcnow
from services.database import SessionLocal
from services import google_gmail
from services.pitmark_mail import MailMessage, sync_gmail_inbox
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



def _sender_email(value: str) -> str:
    return parseaddr(value or "")[1].strip().lower()


def _provider_payload(message: MailMessage) -> dict:
    try:
        value = json.loads(message.provider_payload_json or "{}")
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _sync_gmail_verdict(message_id: int, provider_message_id: str, classification: str) -> bool:
    if not provider_message_id:
        return False
    try:
        response = google_gmail.apply_shield_verdict(provider_message_id, classification)
    except RuntimeError:
        return False
    with SessionLocal() as db:
        message = db.get(MailMessage, message_id)
        if not message:
            return False
        payload = _provider_payload(message)
        payload["gmail_shield_classification"] = classification
        if response.get("labelIds"):
            payload["label_ids"] = [str(value) for value in response.get("labelIds") or []]
        message.provider_payload_json = json.dumps(payload, ensure_ascii=False)[:200000]
        message.updated_at = utcnow()
        db.commit()
    return True


def _trained_spam(sender: str) -> bool:
    email = _sender_email(sender)
    if not email:
        return False
    domain = email.rsplit("@", 1)[-1] if "@" in email else ""
    with SessionLocal() as db:
        exact = db.scalar(select(SecurityAuditEvent.id).where(
            SecurityAuditEvent.event_type == "pitmark_mail_spam_training",
            SecurityAuditEvent.actor == email,
        ))
        domain_hit = db.scalar(select(SecurityAuditEvent.id).where(
            SecurityAuditEvent.event_type == "pitmark_mail_spam_domain_training",
            SecurityAuditEvent.actor == domain,
        )) if domain else None
    return bool(exact or domain_hit)


def mark_thread_spam(thread_id: int) -> dict:
    provider_message_ids: list[str] = []
    with SessionLocal() as db:
        messages = list(db.scalars(select(MailMessage).where(
            MailMessage.thread_id == thread_id, MailMessage.direction == "inbound"
        ).order_by(MailMessage.id.desc())).all())
        if not messages:
            raise ValueError("No inbound message found in this conversation.")
        sender = _sender_email(messages[0].from_address)
        for message in messages:
            provider = _provider_payload(message).get("provider")
            if provider == "google_workspace" and message.provider_message_id:
                provider_message_ids.append(str(message.provider_message_id))
            message.status = "spam"
            message.updated_at = utcnow()
        if not sender:
            raise ValueError("The sender address could not be identified.")
        domain = sender.rsplit("@", 1)[-1] if "@" in sender else ""
        now = utcnow()
        if not db.scalar(select(SecurityAuditEvent.id).where(SecurityAuditEvent.event_type=="pitmark_mail_spam_training", SecurityAuditEvent.actor==sender)):
            db.add(SecurityAuditEvent(event_type="pitmark_mail_spam_training", severity="info", actor=sender, source="shield_mail", detail=f"User marked Pitmark Mail thread {thread_id} as spam; future mail from this sender will be classified as Spam.", created_at=now))
        # Train domain only for obvious bulk/marketing-style domains, not consumer mailbox providers.
        consumer={"gmail.com","outlook.com","hotmail.com","yahoo.com","icloud.com","aol.com","proton.me","protonmail.com"}
        if domain and domain not in consumer and not db.scalar(select(SecurityAuditEvent.id).where(SecurityAuditEvent.event_type=="pitmark_mail_spam_domain_training", SecurityAuditEvent.actor==domain)):
            db.add(SecurityAuditEvent(event_type="pitmark_mail_spam_domain_training", severity="info", actor=domain, source="shield_mail", detail=f"Spam training learned sender domain from Pitmark Mail thread {thread_id}.", created_at=now))
        db.commit()
    for provider_message_id in provider_message_ids:
        try:
            google_gmail.mark_spam(provider_message_id)
        except RuntimeError:
            pass
    rescan_pitmark_mail()
    return {"ok": True, "thread_id": thread_id, "sender": sender, "domain_trained": bool(domain and domain not in consumer)}


def _shield_result(message: MailMessage) -> dict:
    body = _plain_text(message)
    if _trained_spam(message.from_address or ""):
        return {"classification":"Spam","confidence":0.99,"protected":False,"reasons":["user-trained-spam-sender"]}
    if "SPAM" in [str(value) for value in (_provider_payload(message).get("label_ids") or [])]:
        return {"classification":"Spam","confidence":0.98,"protected":False,"reasons":["gmail-spam-filter"]}
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

    # "Insufficient evidence" is neutral uncertainty, not an actual warning.
    # Keep Review only for concrete risk signals such as protected-topic,
    # suspicious-pattern, phishing-language, or blocked URLs.
    neutral_only = (
        result.get("classification") == "Review"
        and set(result["reasons"]) <= {"insufficient-evidence"}
        and not phishing_hits
        and not blocked_urls
    )
    if neutral_only:
        result["classification"] = "Unverified"
        result["confidence"] = 0.40
        result["protected"] = False
        result["reasons"] = ["no-risk-signals", "sender-not-yet-trusted"]

    return result


def _action_for(result: dict) -> str:
    classification = str(result.get("classification") or "Review")
    if classification == "Spam" and not result.get("protected"):
        return "move-spam"
    if classification == "Review":
        return "label-review"
    if classification == "Unverified":
        return "label-unverified"
    return "label-protected"


def protect_message(message_id: int) -> dict | None:
    provider_message_id = ""
    needs_gmail_sync = False
    output: dict | None = None
    with SessionLocal() as db:
        message = db.get(MailMessage, message_id)
        if not message or message.direction != "inbound":
            return None

        source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
        existing = db.scalar(select(ShieldEvent).where(ShieldEvent.source_message_id == source_id))
        if existing:
            payload = _provider_payload(message)
            provider_message_id = str(message.provider_message_id or "")
            needs_gmail_sync = payload.get("gmail_shield_classification") != existing.classification
            output = {
                "event_id": existing.id,
                "classification": existing.classification,
                "confidence": existing.confidence,
                "protected": existing.protected,
                "action_taken": existing.action_taken,
            }
        else:
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

            payload = _provider_payload(message)
            payload["shield"] = {
                "classification": result["classification"],
                "confidence": float(result["confidence"]),
                "protected": bool(result["protected"]),
                "reasons": result["reasons"],
                "action": event.action_taken,
            }
            message.provider_payload_json = json.dumps(payload, ensure_ascii=False)[:200000]
            message.status = "spam" if result["classification"] == "Spam" else message.status
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
            provider_message_id = str(message.provider_message_id or "")
            needs_gmail_sync = True
            output = {
                "event_id": event.id,
                "classification": event.classification,
                "confidence": event.confidence,
                "protected": event.protected,
                "action_taken": event.action_taken,
            }
    if output and needs_gmail_sync:
        _sync_gmail_verdict(message_id, provider_message_id, str(output["classification"]))
    return output


def sync_gmail_mail_protected(limit: int | None = None) -> dict:
    result = sync_gmail_inbox(limit=limit)
    protected = 0
    for message_id in result.get("new_message_ids") or []:
        if protect_message(int(message_id)):
            protected += 1
    result["shield_protected"] = protected
    from services.pitmark_mail_auto_reply import process_auto_replies

    result["auto_replies"] = process_auto_replies()
    return result



def rescan_pitmark_mail(limit: int = 500) -> dict:
    """Re-evaluate existing Pitmark Mail Shield events with the current rules."""
    with SessionLocal() as db:
        messages = list(db.scalars(
            select(MailMessage)
            .where(MailMessage.direction == "inbound")
            .order_by(MailMessage.id.desc())
            .limit(max(1, min(limit, 1000)))
        ).all())

    updated = 0
    gmail_labeled = 0
    counts: dict[str, int] = {}
    for message in messages:
        source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
        result = _shield_result(message)
        action = _action_for(result)
        provider_message_id = ""
        needs_gmail_sync = False
        with SessionLocal() as db:
            event = db.scalar(select(ShieldEvent).where(ShieldEvent.source_message_id == source_id))
            if not event:
                continue
            current = db.get(MailMessage, message.id)
            if not current:
                continue
            changed = (
                event.classification != result["classification"]
                or float(event.confidence or 0) != float(result["confidence"])
                or bool(event.protected) != bool(result["protected"])
                or event.action_taken != action
            )
            event.classification = result["classification"]
            event.confidence = float(result["confidence"])
            event.protected = bool(result["protected"])
            event.reasons_json = json.dumps(result["reasons"], ensure_ascii=False)
            event.action_taken = action

            payload = _provider_payload(current)
            payload["shield"] = {
                "classification": result["classification"],
                "confidence": float(result["confidence"]),
                "protected": bool(result["protected"]),
                "reasons": result["reasons"],
                "action": action,
            }
            provider_message_id = str(current.provider_message_id or "")
            needs_gmail_sync = payload.get("gmail_shield_classification") != result["classification"]
            current.provider_payload_json = json.dumps(payload, ensure_ascii=False)[:200000]
            current.status = "spam" if result["classification"] == "Spam" else current.status
            current.updated_at = utcnow()
            if changed:
                updated += 1
            counts[result["classification"]] = counts.get(result["classification"], 0) + 1
            db.commit()
        if needs_gmail_sync and _sync_gmail_verdict(message.id, provider_message_id, result["classification"]):
            gmail_labeled += 1
    return {
        "rescanned": len(messages),
        "updated": updated,
        "gmail_labeled": gmail_labeled,
        "counts": counts,
    }


def sync_unprotected_mail(limit: int = 250) -> dict:
    sync_result = sync_gmail_mail_protected(limit=min(limit, 500))
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
        def count(name: str) -> int:
            return len(db.scalars(select(ShieldEvent.id).where(
                ShieldEvent.source_message_id.like("pitmark-mail:%"),
                ShieldEvent.classification == name,
            )).all())
        summary = {
            "review": count("Review"),
            "unverified": count("Unverified"),
            "legit": count("Legit"),
            "system": count("System"),
            "spam": count("Spam"),
        }
    return {
        "connected": bool(sync_result.get("connected")),
        "provider": "google_workspace",
        "gmail_sync": sync_result,
        "scanned_now": scanned,
        "protected_events": total,
        "review_count": summary["review"],
        "classification_counts": summary,
    }


def shield_for_message(message: MailMessage) -> dict | None:
    """Return the authoritative ShieldEvent verdict for mail UI/API decoration.

    ShieldEvent is the source of truth. The Gmail metadata copy is retained for
    audit/debugging only and must never override a rescanned event.
    """
    source_id = f"pitmark-mail:{message.provider_message_id or message.id}"
    with SessionLocal() as db:
        event = db.scalar(select(ShieldEvent).where(ShieldEvent.source_message_id == source_id))
        if event:
            try:
                reasons = json.loads(event.reasons_json or "[]")
                if not isinstance(reasons, list):
                    reasons = []
            except Exception:
                reasons = []
            return {
                "classification": event.classification,
                "confidence": float(event.confidence or 0),
                "protected": bool(event.protected),
                "reasons": reasons,
                "action": event.action_taken,
                "action_taken": event.action_taken,
            }

    # Legacy fallback only for a message that somehow has no ShieldEvent yet.
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
