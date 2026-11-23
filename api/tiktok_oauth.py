"""Owner-only TikTok OAuth for the Pitmark Discord video announcement feed."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services import persistent_store
from utils.config import settings

router = APIRouter()
log = logging.getLogger("pitmark.tiktok.oauth")
CALLBACK_URL = "https://pitmarkcloud.onrender.com/auth/tiktok/callback"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
STATE_KEY = "pitmark_tiktok_oauth_pending_v1"
TOKEN_KEY = "pitmark_tiktok_oauth_tokens_v1"
SCOPES = "user.info.basic,video.list"


def _key() -> Fernet:
    secret = settings.pitmark_signing_secret
    if not secret or secret == "development-only":
        raise RuntimeError("Persistent production encryption secret is not configured")
    digest = hashlib.sha256(("pitmark:tiktok:oauth:v1:" + secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _credentials_ready() -> bool:
    return bool(settings.tiktok_client_key and settings.tiktok_client_secret)


def _require_owner(request: Request) -> None:
    # HTTP Basic allows a browser to prompt for the server's existing private
    # owner admin key. Never use a key in a URL or expose it in a page.
    authorization = request.headers.get("authorization", "")
    valid = False
    if authorization.startswith("Basic ") and settings.pitmark_admin_key:
        try:
            decoded = base64.b64decode(authorization[6:], validate=True).decode()
            username, password = decoded.split(":", 1)
            valid = hmac.compare_digest(username, "pitmark") and hmac.compare_digest(
                password, settings.pitmark_admin_key
            )
        except (ValueError, UnicodeDecodeError):
            pass
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Owner authentication required",
            headers={"WWW-Authenticate": 'Basic realm="PitmarkCloud TikTok owner"'},
        )


def _message(title: str, detail: str, status: int = 200) -> HTMLResponse:
    import html
    body = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>PitmarkCloud TikTok</title></head><body><main>"
            "<h1>" + html.escape(title) + "</h1><p>" + html.escape(detail) +
            "</p></main></body></html>")
    return HTMLResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def _save_tokens(data: dict) -> None:
    required = ("access_token", "refresh_token", "open_id")
    if not all(data.get(key) for key in required):
        raise ValueError("TikTok token response missing required fields")
    current = {
        "access_token": str(data["access_token"]),
        "refresh_token": str(data["refresh_token"]),
        "open_id": str(data["open_id"]),
        "scope": str(data.get("scope") or ""),
        "expires_at": time.time() + int(data.get("expires_in") or 0),
        "refresh_expires_at": time.time() + int(data.get("refresh_expires_in") or 0),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    encrypted = _key().encrypt(json.dumps(current).encode()).decode()
    persistent_store.set_runtime_state(TOKEN_KEY, encrypted)


def _read_tokens() -> dict | None:
    raw = persistent_store.get_runtime_state(TOKEN_KEY)
    if not raw:
        return None
    try:
        return json.loads(_key().decrypt(raw.encode()).decode())
    except (InvalidToken, ValueError, json.JSONDecodeError):
        log.error("TikTok token storage unavailable; reauthorization required")
        return None


def connection_status() -> dict:
    tokens = _read_tokens()
    return {
        "client_configured": _credentials_ready(),
        "connected": bool(tokens),
        "scope": tokens.get("scope") if tokens else None,
        "expires_at": tokens.get("expires_at") if tokens else None,
        "redirect_uri": CALLBACK_URL,
        "required_scopes": SCOPES,
    }


def access_token() -> str:
    """For server-side workers only. Refresh and rotate tokens when necessary."""
    tokens = _read_tokens()
    if not tokens:
        return ""
    if tokens.get("expires_at", 0) > time.time() + 300:
        return str(tokens["access_token"])
    if not _credentials_ready():
        return ""
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("error") not in (None, "ok"):
        raise RuntimeError("TikTok token refresh rejected")
    if not result.get("refresh_token"):
        raise RuntimeError("TikTok refresh returned no replacement token")
    # Refresh tokens may rotate. Persist both replacement tokens together.
    _save_tokens(result)
    return str(result["access_token"])


@router.get("/auth/tiktok/status")
def status(request: Request):
    _require_owner(request)
    return connection_status()


@router.get("/auth/tiktok/connect")
def connect(request: Request):
    _require_owner(request)
    if not _credentials_ready():
        return _message("TikTok setup incomplete",
                        "Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in Render first.", 503)
    state = secrets.token_urlsafe(36)
    # Persist across Render instances/restarts; short-lived and single-use.
    persistent_store.set_runtime_state(
        STATE_KEY, json.dumps({"hash": hashlib.sha256(state.encode()).hexdigest(),
                               "expires_at": time.time() + 600}))
    url = AUTH_URL + "?" + urlencode({
        "client_key": settings.tiktok_client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": CALLBACK_URL,
        "state": state,
    })
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/auth/tiktok/callback")
async def callback(code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        return _message("TikTok authorization declined",
                        "TikTok did not authorize this request. Please try again.", 400)
    if not code or not state or len(code) > 4096 or len(state) > 256:
        return _message("TikTok authorization failed", "Missing authorization data.", 400)
    raw = persistent_store.get_runtime_state(STATE_KEY)
    try:
        expected = json.loads(raw or "{}")
        valid = (expected.get("expires_at", 0) > time.time()
                 and hmac.compare_digest(
                     str(expected.get("hash") or ""),
                     hashlib.sha256(state.encode()).hexdigest()))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        return _message("TikTok authorization failed",
                        "The login session was invalid or expired. Start again.", 400)
    # Invalidate immediately so that the same OAuth response cannot be replayed.
    persistent_store.set_runtime_state(STATE_KEY, "{}")
    if not _credentials_ready():
        return _message("TikTok setup incomplete", "Server credentials are missing.", 503)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(TOKEN_URL, data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": CALLBACK_URL,
            })
            response.raise_for_status()
            data = response.json()
        if data.get("error") not in (None, "ok"):
            raise ValueError("Token exchange rejected")
        scopes = set(str(data.get("scope") or "").split(","))
        if "video.list" not in scopes:
            return _message("TikTok permission missing",
                            "TikTok did not grant video.list. Enable it in the developer app.", 403)
        _save_tokens(data)
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
        log.exception("TikTok OAuth exchange failed (secrets omitted)")
        return _message("TikTok connection failed",
                        "The token exchange was unsuccessful. Check app access and try again.", 502)
    return _message("Pitmark TikTok connected!",
                    "Authorization completed. The Discord video feed can now read your public TikTok videos.")
