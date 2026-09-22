"""Dedicated Google analytics/search/YouTube OAuth for Pitmark Intelligence."""

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

from services.control_center import SecureSetting, utcnow
from services.database import SessionLocal
from utils.config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
ANALYTICS_REDIRECT_URI = "http://127.0.0.1:8766/"
ANALYTICS_SCOPES = " ".join([
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
])
_SECRET_KEY = "google_business_intelligence_refresh_token"
_OAUTH_TTL_SECONDS = 15 * 60

_lock = threading.Lock()
_access_token = ""
_access_token_expires_at = 0.0


class AnalyticsAuthorizationRequired(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _client_id() -> str:
    return _env("GOOGLE_WORKSPACE_CLIENT_ID") or _env("GOOGLE_GMAIL_CLIENT_ID")


def _client_secret() -> str:
    return _env("GOOGLE_WORKSPACE_CLIENT_SECRET") or _env("GOOGLE_GMAIL_CLIENT_SECRET")


def _signing_secret() -> bytes:
    raw = (settings.pitmark_signing_secret or settings.pitmark_admin_key or "").encode("utf-8")
    if len(raw) < 24:
        raise AnalyticsAuthorizationRequired("Pitmark signing secret is not configured strongly enough.")
    return hashlib.sha256(b"pitmark-google-business-intelligence\0" + raw).digest()


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
            row.updated_at = utcnow()
        db.commit()


def configured() -> bool:
    return bool(_client_id() and _client_secret() and _stored_refresh_token())


def clear_access_token_cache() -> None:
    global _access_token, _access_token_expires_at
    with _lock:
        _access_token = ""
        _access_token_expires_at = 0.0


def access_token() -> str:
    global _access_token, _access_token_expires_at
    if _access_token and time.time() < _access_token_expires_at - 60:
        return _access_token
    if not configured():
        raise AnalyticsAuthorizationRequired("Google Business Intelligence is not connected.")
    with _lock:
        if _access_token and time.time() < _access_token_expires_at - 60:
            return _access_token
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            timeout=20.0,
            data={
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "refresh_token": _stored_refresh_token(),
                "grant_type": "refresh_token",
            },
        )
        if response.status_code >= 400:
            raise AnalyticsAuthorizationRequired(
                "Google Business Intelligence token refresh failed (%s)." % response.status_code
            )
        payload = response.json()
        _access_token = str(payload.get("access_token") or "")
        if not _access_token:
            raise AnalyticsAuthorizationRequired("Google did not return an analytics access token.")
        _access_token_expires_at = time.time() + int(payload.get("expires_in") or 3600)
        return _access_token


def authorization_headers() -> dict[str, str]:
    return {"Authorization": "Bearer " + access_token()}


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
        "kind": "business_intelligence",
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64e(hmac.new(_signing_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + sig


def _verify_state(state: str, user_key: str) -> None:
    try:
        body, sig = state.split(".", 1)
        expected = _b64e(hmac.new(_signing_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise ValueError("signature")
        payload = json.loads(_b64d(body))
        if str(payload.get("usr") or "") != str(user_key):
            raise ValueError("user")
        if str(payload.get("kind") or "") != "business_intelligence":
            raise ValueError("kind")
        if int(payload.get("exp") or 0) < int(time.time()):
            raise ValueError("expired")
    except Exception as exc:
        raise AnalyticsAuthorizationRequired("Google analytics authorization session expired or is invalid.") from exc


def begin_authorization(user_key: str) -> dict[str, str]:
    if not _client_id() or not _client_secret():
        raise AnalyticsAuthorizationRequired("Google OAuth client credentials are not configured.")
    state = _oauth_state(user_key)
    url = GOOGLE_AUTH_URL + "?" + urlencode({
        "client_id": _client_id(),
        "redirect_uri": ANALYTICS_REDIRECT_URI,
        "response_type": "code",
        "scope": ANALYTICS_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })
    return {"authorization_url": url, "redirect_uri": ANALYTICS_REDIRECT_URI, "state": state}


def complete_authorization(callback_url: str, user_key: str) -> None:
    parsed = urlparse(callback_url.strip())
    params = parse_qs(parsed.query)
    error = (params.get("error") or [""])[0]
    if error:
        raise AnalyticsAuthorizationRequired("Google authorization failed: " + error)
    code = (params.get("code") or [""])[0]
    state = (params.get("state") or [""])[0]
    if not code or not state:
        raise AnalyticsAuthorizationRequired("Paste the full localhost callback URL from Google.")
    _verify_state(state, user_key)
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        timeout=30.0,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": ANALYTICS_REDIRECT_URI,
        },
    )
    if response.status_code >= 400:
        raise AnalyticsAuthorizationRequired(
            "Google analytics authorization exchange failed (%s)." % response.status_code
        )
    refresh_token = str((response.json() or {}).get("refresh_token") or "")
    if not refresh_token:
        raise AnalyticsAuthorizationRequired("Google did not return an analytics refresh token.")
    _save_refresh_token(refresh_token)
    clear_access_token_cache()
