from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from services import pitmark_mail as base

MAX_ATTACHMENTS = 8
MAX_TOTAL_ATTACHMENT_BYTES = 12 * 1024 * 1024


def normalize_attachments(items: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Return (Resend payload attachments, serializable stored metadata/content)."""
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
    except Exception:
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


def list_resend_attachments(provider_message_id: str, *, inbound: bool) -> list[dict]:
    key = base.inbound_api_key() if inbound else base.send_api_key()
    if not key or not provider_message_id:
        return []

    path = (
        f"{base.RESEND_API}/emails/receiving/{provider_message_id}/attachments"
        if inbound
        else f"{base.RESEND_API}/emails/{provider_message_id}/attachments"
    )
    with httpx.Client(timeout=20.0) as client:
        response = client.get(path, headers=base._resend_headers(key))
        if response.status_code >= 400:
            return []
        payload = response.json()

    rows = payload.get("data") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []
