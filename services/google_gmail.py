from __future__ import annotations

import base64
import os
import threading
import time
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import getaddresses
from typing import Any
from urllib.parse import quote

import httpx

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

_token_lock = threading.Lock()
_access_token = ""
_access_token_expires_at = 0.0

_setup_lock = threading.Lock()
_setup_checked_at = 0.0
_setup_state: dict[str, Any] = {
    "configured": False,
    "ready": False,
    "labels_ready": False,
    "filters_ready": False,
    "created_labels": [],
    "created_filters": [],
    "errors": [],
}

DEPARTMENT_LABELS = {
    "sales": "Pitmark/Sales",
    "support": "Pitmark/Support",
    "partnerships": "Pitmark/Partnerships",
    "prt": "Pitmark/PRT",
    "marketing": "Pitmark/Marketing",
    "outreach": "Pitmark/Outreach",
    "orders": "Pitmark/Orders",
    "hello": "Pitmark/Hello",
}

SHIELD_LABELS = {
    "shield_review": "Pitmark/Shield Review",
    "shield_protected": "Pitmark/Shield Protected",
    "shield_unverified": "Pitmark/Shield Unverified",
    "shield_spam": "Pitmark/Shield Spam",
}

MANAGED_LABELS = {**DEPARTMENT_LABELS, **SHIELD_LABELS}


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


def business_domain() -> str:
    return _env("PITMARK_GMAIL_BUSINESS_DOMAIN", "pitmarkracing.com").lower().lstrip("@")


def business_addresses() -> list[str]:
    domain = business_domain()
    explicit = [
        value.strip().lower()
        for value in _env("PITMARK_GMAIL_BUSINESS_ADDRESSES").split(",")
        if value.strip()
    ]
    discovered = [
        str(row.get("sendAsEmail") or "").strip().lower()
        for row in list_send_as()
    ]
    standard = [f"{local}@{domain}" for local in DEPARTMENT_LABELS]
    account = gmail_user().lower()
    addresses: list[str] = []
    for address in explicit + discovered + standard + ([account] if account != "me" else []):
        if address.endswith(f"@{domain}") and address not in addresses:
            addresses.append(address)
    return addresses or [f"justin@{domain}"]


def inbox_sync_query() -> str:
    configured = _env("PITMARK_GMAIL_SYNC_QUERY")
    if configured:
        return configured

    delivered_to = " ".join(f"deliveredto:{address}" for address in business_addresses())
    # Include Gmail Spam so Shield can audit provider-caught threats while still
    # excluding personal mail, sent messages, drafts and trash.
    return f"-in:sent -in:drafts -in:trash {{{delivered_to}}}"


def _list_labels() -> list[dict]:
    payload = request("GET", "/users/{user}/labels")
    rows = payload.get("labels") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _create_label(name: str) -> dict:
    return request(
        "POST",
        "/users/{user}/labels",
        json_body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    )


def _list_filters() -> list[dict]:
    payload = request("GET", "/users/{user}/settings/filters")
    rows = payload.get("filter") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _filter_matches(row: dict, address: str, label_id: str) -> bool:
    criteria = row.get("criteria") if isinstance(row, dict) else {}
    action = row.get("action") if isinstance(row, dict) else {}
    query = str((criteria or {}).get("query") or "").lower().replace(" ", "")
    to_value = str((criteria or {}).get("to") or "").lower().strip()
    labels = [str(value) for value in ((action or {}).get("addLabelIds") or [])]
    routes_address = to_value == address or f"deliveredto:{address}" in query
    return routes_address and label_id in labels


def workspace_setup_status() -> dict:
    return dict(_setup_state)


def ensure_workspace_setup(*, force: bool = False) -> dict:
    """Idempotently provision Pitmark labels and alias-routing Gmail filters."""
    global _setup_checked_at, _setup_state
    if not credentials_configured():
        _setup_state = {
            **_setup_state,
            "configured": False,
            "ready": False,
            "errors": ["gmail-not-configured"],
        }
        return workspace_setup_status()
    if not force and _setup_state.get("ready") and time.time() - _setup_checked_at < 900:
        return workspace_setup_status()

    with _setup_lock:
        if not force and _setup_state.get("ready") and time.time() - _setup_checked_at < 900:
            return workspace_setup_status()

        created_labels: list[str] = []
        created_filters: list[str] = []
        errors: list[str] = []
        label_ids: dict[str, str] = {}
        try:
            existing_labels = {
                str(row.get("name") or ""): str(row.get("id") or "")
                for row in _list_labels()
                if row.get("name") and row.get("id")
            }
            for key, name in MANAGED_LABELS.items():
                label_id = existing_labels.get(name)
                if not label_id:
                    created = _create_label(name)
                    label_id = str(created.get("id") or "")
                    if label_id:
                        created_labels.append(name)
                if label_id:
                    label_ids[key] = label_id
                else:
                    errors.append(f"label-missing:{name}")
        except RuntimeError as exc:
            errors.append(str(exc)[:500])

        existing_filters: list[dict] = []
        if label_ids:
            try:
                existing_filters = _list_filters()
            except RuntimeError as exc:
                errors.append(str(exc)[:500])

        domain = business_domain()
        for local, label_name in DEPARTMENT_LABELS.items():
            label_id = label_ids.get(local)
            if not label_id:
                continue
            address = f"{local}@{domain}"
            if any(_filter_matches(row, address, label_id) for row in existing_filters):
                continue
            try:
                filter_body = {
                    "criteria": {"query": f"deliveredto:{address}"},
                    "action": {"addLabelIds": [label_id]},
                }
                created = request(
                    "POST",
                    "/users/{user}/settings/filters",
                    json_body=filter_body,
                )
                created_filters.append(address)
                existing_filters.append({**filter_body, **created})
            except RuntimeError as exc:
                errors.append(f"{address}: {str(exc)[:400]}")

        expected_filter_count = len(DEPARTMENT_LABELS)
        matched_filter_count = sum(
            1
            for local in DEPARTMENT_LABELS
            if label_ids.get(local)
            and any(
                _filter_matches(row, f"{local}@{domain}", label_ids[local])
                for row in existing_filters
            )
        )
        labels_ready = len(label_ids) == len(MANAGED_LABELS)
        filters_ready = matched_filter_count == expected_filter_count
        _setup_checked_at = time.time()
        _setup_state = {
            "configured": True,
            "ready": labels_ready and filters_ready and not errors,
            "labels_ready": labels_ready,
            "filters_ready": filters_ready,
            "managed_label_count": len(label_ids),
            "managed_filter_count": matched_filter_count,
            "created_labels": created_labels,
            "created_filters": created_filters,
            "aliases": [f"{local}@{domain}" for local in DEPARTMENT_LABELS],
            "label_ids": label_ids,
            "errors": errors[:10],
        }
        return workspace_setup_status()


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


def modify_message_labels(
    message_id: str,
    *,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict:
    mid = quote(str(message_id), safe="")
    add = list(dict.fromkeys(str(value) for value in (add_label_ids or []) if value))
    remove = list(dict.fromkeys(str(value) for value in (remove_label_ids or []) if value))
    body: dict[str, list[str]] = {}
    if add:
        body["addLabelIds"] = add
    if remove:
        body["removeLabelIds"] = remove
    if not body:
        return {}
    return request(
        "POST",
        f"/users/{{user}}/messages/{mid}/modify",
        json_body=body,
    )


def apply_department_labels(message_id: str, recipients: list[str]) -> dict:
    setup = ensure_workspace_setup()
    label_ids = setup.get("label_ids") if isinstance(setup, dict) else {}
    parsed = {
        address.strip().lower()
        for _, address in getaddresses([str(value) for value in recipients])
        if address.strip()
    }
    domain = business_domain()
    add = [
        str(label_ids.get(local) or "")
        for local in DEPARTMENT_LABELS
        if f"{local}@{domain}" in parsed and label_ids.get(local)
    ]
    return modify_message_labels(message_id, add_label_ids=add) if add else {}


def apply_shield_verdict(message_id: str, classification: str) -> dict:
    setup = ensure_workspace_setup()
    label_ids = setup.get("label_ids") if isinstance(setup, dict) else {}
    managed_shield_ids = [
        str(label_ids.get(key) or "")
        for key in SHIELD_LABELS
        if label_ids.get(key)
    ]
    value = (classification or "Unverified").strip().lower()
    if value == "review":
        target = "shield_review"
    elif value == "spam":
        target = "shield_spam"
    elif value == "unverified":
        target = "shield_unverified"
    else:
        target = "shield_protected"
    target_id = str(label_ids.get(target) or "")
    add = [target_id] if target_id else []
    remove = [value for value in managed_shield_ids if value != target_id]
    if value == "spam":
        add.append("SPAM")
        remove.append("INBOX")
    return modify_message_labels(
        message_id,
        add_label_ids=add,
        remove_label_ids=remove,
    )


def trash_message(message_id: str) -> None:
    mid = quote(str(message_id), safe="")
    request("POST", f"/users/{{user}}/messages/{mid}/trash")


def mark_spam(message_id: str) -> None:
    apply_shield_verdict(message_id, "Spam")


def get_attachment(message_id: str, attachment_id: str) -> dict:
    mid = quote(str(message_id), safe="")
    aid = quote(str(attachment_id), safe="")
    return request("GET", f"/users/{{user}}/messages/{mid}/attachments/{aid}")
