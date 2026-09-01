from __future__ import annotations

import base64
import json

from services import google_gmail

MAX_ATTACHMENTS = 8
MAX_TOTAL_ATTACHMENT_BYTES = 12 * 1024 * 1024


def normalize_attachments(items: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Return Gmail MIME attachments plus serializable stored metadata/content."""
    outbound: list[dict] = []
    stored: list[dict] = []
    total = 0

    for item in list(items or [])[:MAX_ATTACHMENTS]:
        filename = str(item.get("filename") or "attachment").strip()[:255]
        content = str(item.get("content") or "").strip()
        content_type = str(item.get("content_type") or "application/octet-stream").strip()[:160]

        if not content:
            continue

        try:
            raw = base64.b64decode(content, validate=True)
        except Exception as exc:
            raise ValueError(f"Attachment {filename} is not valid Base64.") from exc

        total += len(raw)
        if total > MAX_TOTAL_ATTACHMENT_BYTES:
            raise ValueError("Attachments are too large. Keep the total under 12 MB.")

        outbound.append(
            {
                "filename": filename,
                "content": content,
                "content_type": content_type,
            }
        )
        stored.append(
            {
                "filename": filename,
                "content": content,
                "content_type": content_type,
                "size": len(raw),
            }
        )

    return outbound, stored


def stored_attachments(message) -> list[dict]:
    try:
        payload = json.loads(message.provider_payload_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return []
    rows = payload.get("draft_attachments") or payload.get("attachments") or []
    return rows if isinstance(rows, list) else []


def decorate_message_attachments(message_dict: dict, message_obj=None) -> dict:
    row = dict(message_dict or {})
    if message_obj is not None:
        row["attachments"] = [
            {
                "filename": x.get("filename"),
                "content_type": x.get("content_type"),
                "size": x.get("size"),
            }
            for x in stored_attachments(message_obj)
        ]
    return row


def list_google_attachments(message) -> list[dict]:
    rows = []
    for item in stored_attachments(message):
        row = {
            "filename": item.get("filename"),
            "content_type": item.get("content_type"),
            "size": item.get("size"),
        }
        attachment_id = str(item.get("gmail_attachment_id") or "")
        if attachment_id and message.provider_message_id:
            row["download_url"] = (
                f"/api/control/email/messages/{message.id}/attachments/{attachment_id}"
            )
        rows.append(row)
    return rows


def download_google_attachment(message, attachment_id: str) -> tuple[bytes, dict]:
    match = next(
        (
            item for item in stored_attachments(message)
            if str(item.get("gmail_attachment_id") or "") == str(attachment_id)
        ),
        None,
    )
    if not match or not message.provider_message_id:
        raise ValueError("Gmail attachment not found.")
    payload = google_gmail.get_attachment(message.provider_message_id, attachment_id)
    encoded = str(payload.get("data") or "")
    if not encoded:
        raise ValueError("Gmail attachment has no downloadable content.")
    padded = encoded + "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(padded), match
