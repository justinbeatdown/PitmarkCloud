from __future__ import annotations

import base64
import os
import threading
import time
from email.message import EmailMessage
from email.policy import SMTP
from typing import Any
from urllib.parse import quote

import httpx

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

_token_lock = threading.Lock()
_access_token = ""
_access_token_expires_at = 0.0


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def gmail_user() -> str:
    return _env("GOOGLE_GMAIL_USER", "me")


def credentials_configured() -> bool:
    return all(
        _env(name)
        for name in (
            "GOOGLE_GMAIL_CLIENT_ID",
            "GOOGLE_GMAIL_CLIENT_SECRET",
            "GOOGLE_GMAIL_REFRESH_TOKEN",
        )
    )


def _token() -> str:
    global _access_token, _access_token_expires_at
    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token
    if not credentials_configured():
        raise RuntimeError("Google Workspace Gmail credentials are not configured in Pitmark Cloud.")

    with _token_lock:
        if _access_token and time.time() < _access_token_expires_at - 60:
            return _access_token
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": _env("GOOGLE_GMAIL_CLIENT_ID"),
                    "client_secret": _env("GOOGLE_GMAIL_CLIENT_SECRET"),
                    "refresh_token": _env("GOOGLE_GMAIL_REFRESH_TOKEN"),
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Google Workspace token refresh failed ({response.status_code}): {response.text[:800]}"
            )
        payload = response.json()
        _access_token = str(payload.get("access_token") or "")
        if not _access_token:
            raise RuntimeError("Google Workspace did not return a Gmail access token.")
        _access_token_expires_at = time.time() + int(payload.get("expires_in") or 3600)
        return _access_token


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict:
    user = quote(gmail_user(), safe="")
    resolved = path.replace("{user}", user)
    url = resolved if resolved.startswith("https://") else f"{GMAIL_API}{resolved}"
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            url,
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {_token()}"},
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Gmail API request failed ({response.status_code}): {response.text[:1000]}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def connection_status() -> dict:
    configured = credentials_configured()
    result = {
        "configured": configured,
        "connected": False,
        "user": gmail_user(),
        "provider": "google_workspace",
        "provider_label": "Google Workspace / Gmail",
    }
    if not configured:
        return result
    try:
        profile = request("GET", "/users/{user}/profile")
        result.update(
            connected=True,
            email_address=profile.get("emailAddress") or gmail_user(),
            history_id=profile.get("historyId"),
            messages_total=profile.get("messagesTotal"),
            threads_total=profile.get("threadsTotal"),
        )
    except RuntimeError as exc:
        result["error"] = str(exc)
    return result


def list_send_as() -> list[dict]:
    if not credentials_configured():
        return []
    try:
        payload = request("GET", "/users/{user}/settings/sendAs")
    except RuntimeError:
        return []
    rows = payload.get("sendAs") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def inbox_sync_query() -> str:
    configured = _env("PITMARK_GMAIL_SYNC_QUERY")
    if configured:
        return configured

    business_domain = _env("PITMARK_GMAIL_BUSINESS_DOMAIN", "pitmarkracing.com").lower().lstrip("@")
    explicit = [
        value.strip().lower()
        for value in _env("PITMARK_GMAIL_BUSINESS_ADDRESSES").split(",")
        if value.strip()
    ]
    discovered = [
        str(row.get("sendAsEmail") or "").strip().lower()
        for row in list_send_as()
    ]
    account = gmail_user().lower()
    addresses = []
    for address in explicit + discovered + ([account] if account != "me" else []):
        if address.endswith(f"@{business_domain}") and address not in addresses:
            addresses.append(address)

    if not addresses:
        addresses = [f"justin@{business_domain}"]
    delivered_to = " ".join(f"deliveredto:{address}" for address in addresses)
    return f"in:inbox {{{delivered_to}}}"


def build_raw_message(
    *,
    sender: str,
    to: list[str],
    subject: str,
    text: str = "",
    html: str = "",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: list[str] | None = None,
    headers: dict[str, str] | None = None,
    attachments: list[dict] | None = None,
) -> str:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    if reply_to:
        message["Reply-To"] = ", ".join(reply_to)
    message["Subject"] = subject
    for name, value in (headers or {}).items():
        if value:
            message[name] = value

    message.set_content(text or "")
    if html:
        message.add_alternative(html, subtype="html")

    for item in attachments or []:
        filename = str(item.get("filename") or "attachment")[:255]
        content_type = str(item.get("content_type") or "application/octet-stream")
        try:
            maintype, subtype = content_type.split("/", 1)
        except ValueError:
            maintype, subtype = "application", "octet-stream"
        raw = base64.b64decode(str(item.get("content") or ""))
        message.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)

    encoded = base64.urlsafe_b64encode(message.as_bytes(policy=SMTP)).decode("ascii")
    return encoded.rstrip("=")


def send_message(*, raw: str, thread_id: str | None = None) -> dict:
    body: dict[str, Any] = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    return request("POST", "/users/{user}/messages/send", json_body=body, timeout=45.0)


def list_inbox_message_ids(limit: int = 100) -> list[str]:
    payload = request(
        "GET",
        "/users/{user}/messages",
        params={
            "q": inbox_sync_query(),
            "maxResults": max(1, min(int(limit), 500)),
        },
    )
    rows = payload.get("messages") if isinstance(payload, dict) else []
    return [str(row.get("id")) for row in (rows or []) if row.get("id")]


def get_message(message_id: str) -> dict:
    mid = quote(str(message_id), safe="")
    return request("GET", f"/users/{{user}}/messages/{mid}", params={"format": "full"})


def mark_read(message_id: str) -> None:
    mid = quote(str(message_id), safe="")
    request(
        "POST",
        f"/users/{{user}}/messages/{mid}/modify",
        json_body={"removeLabelIds": ["UNREAD"]},
    )


def trash_message(message_id: str) -> None:
    mid = quote(str(message_id), safe="")
    request("POST", f"/users/{{user}}/messages/{mid}/trash")


def mark_spam(message_id: str) -> None:
    mid = quote(str(message_id), safe="")
    request(
        "POST",
        f"/users/{{user}}/messages/{mid}/modify",
        json_body={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
    )


def get_attachment(message_id: str, attachment_id: str) -> dict:
    mid = quote(str(message_id), safe="")
    aid = quote(str(attachment_id), safe="")
    return request("GET", f"/users/{{user}}/messages/{mid}/attachments/{aid}")
