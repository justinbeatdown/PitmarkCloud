"""Google Workspace authentication for Control Center Sheets access.

Pitmark uses a dedicated Sheets-capable refresh token. The token may come from a
Render environment variable or from the encrypted Control Center secret store.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from services.control_center import SecureSetting
from services.database import SessionLocal
from utils.config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
WORKSPACE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
WORKSPACE_REDIRECT_URI = "http://127.0.0.1:8765/"
_SECRET_KEY = "google_workspace_refresh_token"
_OAUTH_TTL_SECONDS = 15 * 60

_token_lock = threading.Lock()
_access_token = ""
_access_token_expires_at = 0.0


class WorkspaceAuthorizationRequired(RuntimeError):
    """Raised when Pitmark Cloud has no Sheets-capable Workspace credential."""


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _client_id() -> str:
    return _env("GOOGLE_WORKSPACE_CLIENT_ID") or _env("GOOGLE_GMAIL_CLIENT_ID")


def _client_secret() -> str:
    return _env("GOOGLE_WORKSPACE_CLIENT_SECRET") or _env("GOOGLE_GMAIL_CLIENT_SECRET")


def _signing_secret() -> bytes:
    raw = (settings.pitmark_signing_secret or settings.pitmark_admin_key or "").encode("utf-8")
    if len(raw) < 24:
        raise WorkspaceAuthorizationRequired("Pitmark signing secret is not configured strongly enough.")
    return hashlib.sha256(b"pitmark-google-workspace\0" + raw).digest()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_signing_secret()))


def _stored_refresh_token() -> str:
    try:
        with SessionLocal() as db:
            row = db.get(SecureSetting, _SECRET_KEY)
            if not row or not row.value_encrypted:
                return ""
            return _fernet().decrypt(row.value_encrypted.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, RuntimeError):
        return ""


def _save_refresh_token(refresh_token: str) -> None:
    encrypted = _fernet().encrypt(refresh_token.encode("utf-8")).decode("utf-8")
    with SessionLocal() as db:
        row = db.get(SecureSetting, _SECRET_KEY)
        if row is None:
            row = SecureSetting(key=_SECRET_KEY, value_encrypted=encrypted)
            db.add(row)
        else:
            row.value_encrypted = encrypted
            from services.control_center import utcnow
            row.updated_at = utcnow()
        db.commit()


def _refresh_token() -> str:
    return _stored_refresh_token() or _env("GOOGLE_WORKSPACE_REFRESH_TOKEN")


def workspace_credentials_configured() -> bool:
    """Whether a dedicated Sheets-capable Workspace refresh token is present."""
    return bool(_client_id() and _client_secret() and _refresh_token())


def credential_source() -> str:
    if _stored_refresh_token():
        return "control_center"
    if _env("GOOGLE_WORKSPACE_REFRESH_TOKEN"):
        return "environment"
    return "none"


def clear_access_token_cache() -> None:
    global _access_token, _access_token_expires_at
    with _token_lock:
        _access_token = ""
        _access_token_expires_at = 0.0


def access_token() -> str:
    """Return a Sheets-capable Google Workspace OAuth access token."""
    global _access_token, _access_token_expires_at

    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token
    if not workspace_credentials_configured():
        raise WorkspaceAuthorizationRequired(
            "Google Sheets authorization is not connected to Pitmark Cloud."
        )

    with _token_lock:
        if _access_token and time.time() < _access_token_expires_at - 60:
            return _access_token
        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "refresh_token": _refresh_token(),
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise WorkspaceAuthorizationRequired(
                f"Google Sheets authorization refresh failed ({response.status_code})."
            )
        payload = response.json()
        _access_token = str(payload.get("access_token") or "")
        if not _access_token:
            raise WorkspaceAuthorizationRequired(
                "Google Sheets authorization did not return an access token."
            )
        _access_token_expires_at = time.time() + int(payload.get("expires_in") or 3600)
        return _access_token


def authorization_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token()}"}


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _oauth_state(user_key: str) -> str:
    payload = {
        "usr": user_key,
        "iat": int(time.time()),
        "exp": int(time.time()) + _OAUTH_TTL_SECONDS,
        "nonce": secrets.token_hex(10),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(_signing_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _verify_state(state: str, user_key: str) -> None:
    try:
        body, sig = state.split(".", 1)
        expected = _b64e(hmac.new(_signing_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("signature")
        payload = json.loads(_b64d(body))
        if str(payload.get("usr") or "") != str(user_key):
            raise ValueError("user")
        if int(payload.get("exp") or 0) < int(time.time()):
            raise ValueError("expired")
    except Exception as exc:
        raise WorkspaceAuthorizationRequired("Google Sheets authorization session expired or is invalid.") from exc


def begin_authorization(user_key: str) -> dict[str, str]:
    if not _client_id() or not _client_secret():
        raise WorkspaceAuthorizationRequired(
            "Google OAuth client credentials are not configured in Pitmark Cloud."
        )
    state = _oauth_state(user_key)
    url = GOOGLE_AUTH_URL + "?" + urlencode(
        {
            "client_id": _client_id(),
            "redirect_uri": WORKSPACE_REDIRECT_URI,
            "response_type": "code",
            "scope": WORKSPACE_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return {
        "authorization_url": url,
        "redirect_uri": WORKSPACE_REDIRECT_URI,
        "state": state,
    }


def complete_authorization(callback_url: str, user_key: str) -> None:
    parsed = urlparse(callback_url.strip())
    params = parse_qs(parsed.query)
    error = (params.get("error") or [""])[0]
    if error:
        raise WorkspaceAuthorizationRequired(f"Google authorization failed: {error}")
    code = (params.get("code") or [""])[0]
    state = (params.get("state") or [""])[0]
    if not code or not state:
        raise WorkspaceAuthorizationRequired(
            "Paste the full localhost callback URL from the Google authorization tab."
        )
    _verify_state(state, user_key)

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": WORKSPACE_REDIRECT_URI,
            },
        )
    if response.status_code >= 400:
        raise WorkspaceAuthorizationRequired(
            f"Google authorization code exchange failed ({response.status_code})."
        )
    payload = response.json()
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        raise WorkspaceAuthorizationRequired(
            "Google did not return a refresh token. Re-run the connection and approve access again."
        )
    _save_refresh_token(refresh_token)
    clear_access_token_cache()
