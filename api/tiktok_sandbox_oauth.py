"""Isolated TikTok sandbox OAuth: test-only credentials, tokens, and redirect."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services import persistent_store
from utils.config import settings

router = APIRouter()
log = logging.getLogger("pitmark.tiktok.oauth")
CALLBACK_URL = "https://pitmarkcloud.onrender.com/auth/tiktok/sandbox/callback"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
STATE_KEY = "pitmark_tiktok_sandbox_pending_v1"
TOKEN_KEY = "pitmark_tiktok_sandbox_tokens_v1"
SCOPES = "user.info.basic,video.list"


def _key() -> Fernet:
    secret = settings.pitmark_signing_secret
    if not secret or secret == "development-only":
        raise RuntimeError("Persistent production encryption secret is not configured")
    digest = hashlib.sha256(("pitmark:tiktok:sandbox:oauth:v1:" + secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _client_key() -> str:
    return os.environ.get("TIKTOK_SANDBOX_CLIENT_KEY", "").strip()


def _client_secret() -> str:
    return os.environ.get("TIKTOK_SANDBOX_CLIENT_SECRET", "").strip()


def _credentials_ready() -> bool:
    return bool(_client_key() and _client_secret())


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
            "client_key": _client_key(),
            "client_secret": _client_secret(),
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


@router.get("/auth/tiktok/sandbox/status")
def status(request: Request):
    _require_owner(request)
    return connection_status()


@router.get("/auth/tiktok/sandbox/connect")
def connect(request: Request):
    _require_owner(request)
    if not _credentials_ready():
        return _message("TikTok setup incomplete",
                        "Set TIKTOK_SANDBOX_CLIENT_KEY and TIKTOK_SANDBOX_CLIENT_SECRET in Render first.", 503)
    state = secrets.token_urlsafe(36)
    # Persist across Render instances/restarts; short-lived and single-use.
    persistent_store.set_runtime_state(
        STATE_KEY, json.dumps({"hash": hashlib.sha256(state.encode()).hexdigest(),
                               "expires_at": time.time() + 600}))
    url = AUTH_URL + "?" + urlencode({
        "client_key": _client_key(),
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": CALLBACK_URL,
        "state": state,
    })
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/auth/tiktok/sandbox/callback")
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
                "client_key": _client_key(),
                "client_secret": _client_secret(),
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
    return _message("Pitmark TikTok sandbox connected!",
                    "Sandbox authorization completed. This test connection will not send automatic Discord announcements.")

@router.get("/auth/tiktok/sandbox/videos")
def preview_videos(request: Request):
    """Owner-only test endpoint. Returns a tiny safe preview; never any tokens."""
    _require_owner(request)
    token = access_token()
    if not token:
        raise HTTPException(status_code=409, detail="TikTok sandbox not connected.")
    try:
        response = httpx.post(
            "https://open.tiktokapis.com/v2/video/list/",
            headers={"Authorization": "Bearer " + token},
            params={"fields": "id,create_time,title,video_description,share_url,cover_image_url"},
            json={"max_count": 5},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        if (payload.get("error") or {}).get("code") not in (None, "ok"):
            raise ValueError("TikTok rejected video access")
        videos = (payload.get("data") or {}).get("videos") or []
        return {"sandbox": True, "count": len(videos), "videos": [
            {"id": v.get("id"), "title": str(v.get("video_description") or v.get("title") or "")[:120],
             "share_url": v.get("share_url")} for v in videos if isinstance(v, dict)]}
    except (httpx.HTTPError, ValueError):
        log.warning("TikTok sandbox video preview failed")
        raise HTTPException(status_code=502, detail="TikTok sandbox video retrieval failed.") from None

def _sandbox_videos() -> list[dict]:
    token = access_token()
    if not token:
        raise HTTPException(status_code=409, detail="TikTok sandbox is not connected.")
    try:
        response = httpx.post(
            "https://open.tiktokapis.com/v2/video/list/",
            headers={"Authorization": "Bearer " + token},
            params={"fields": "id,create_time,title,video_description,share_url,cover_image_url"},
            json={"max_count": 12},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        if (payload.get("error") or {}).get("code") not in (None, "ok"):
            raise ValueError("TikTok rejected video retrieval")
        return [v for v in ((payload.get("data") or {}).get("videos") or []) if isinstance(v, dict)]
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("TikTok sandbox demo could not retrieve videos: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="TikTok video retrieval failed.") from None


@router.get("/auth/tiktok/sandbox/demo")
def demo_page(request: Request):
    """A visible review demo with an explicit, one-time Discord test action."""
    import html
    _require_owner(request)
    videos = _sandbox_videos()
    elements = []
    for video in videos:
        vid = str(video.get("id") or "")
        share = str(video.get("share_url") or "")
        parsed = urlparse(share)
        if not vid.isdigit() or parsed.scheme != "https" or parsed.hostname not in {"www.tiktok.com", "tiktok.com"}:
            continue
        caption = html.escape(str(video.get("video_description") or video.get("title") or "TikTok video")[:120])
        elements.append("<option value='" + html.escape(vid, quote=True) + "'>" + caption + "</option>")
    body = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>PitmarkCloud TikTok Sandbox Demo</title><style>body{background:#101114;color:#f4f4f4;font:16px system-ui;padding:32px;max-width:760px;margin:auto}"
            "h1{color:#ff5500}select,button{padding:14px;font:inherit;width:100%;margin:12px 0}button{background:#ff5500;border:0;color:white;cursor:pointer}"
            "p{line-height:1.5}.note{color:#ccc}</style></head><body>"
            "<h1>PitmarkCloud — TikTok Sandbox Demo</h1><p>Authorized TikTok account connected. Retrieved " + str(len(videos)) +
            " videos through the TikTok Display API.</p><p class='note'>Choose an existing public video, then explicitly send one test announcement to Discord #social-media.</p>"
            "<form method='post' action='/auth/tiktok/sandbox/demo/send'><label for='video'>Published video</label><select id='video' name='video_id'>" +
            "".join(elements) + "</select><button type='submit'>Send a test TikTok announcement to Discord</button></form>"
            "<p class='note'>This is a sandbox test. It does not publish to TikTok or enable automated Discord alerts.</p></body></html>")
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@router.post("/auth/tiktok/sandbox/demo/send")
async def send_demo(request: Request):
    """Send only a user-selected verified TikTok video, once per sandbox."""
    import html
    from datetime import datetime, timezone
    from services import discord_social_media_feed as feed
    from services.discord_hq_common import discord_request, DISCORD_API

    _require_owner(request)
    origin = request.headers.get("origin") or ""
    if origin != "https://pitmarkcloud.onrender.com":
        raise HTTPException(status_code=403, detail="Invalid request origin.")
    form = await request.form()
    vid = str(form.get("video_id") or "")
    if not vid.isdigit() or len(vid) > 30:
        raise HTTPException(status_code=400, detail="Invalid video selection.")
    videos = await __import__("asyncio").to_thread(_sandbox_videos)
    video = next((v for v in videos if str(v.get("id") or "") == vid), None)
    if not video:
        raise HTTPException(status_code=400, detail="Video is not in the authorized TikTok feed.")
    url = feed._permalink(video.get("share_url"), "tiktok")
    if not url or "/@pitmarkracing/video/" not in urlparse(url).path:
        raise HTTPException(status_code=400, detail="Unexpected TikTok video URL.")
    if not settings.discord_bot_token or not settings.discord_hq_guild_id:
        raise HTTPException(status_code=503, detail="Discord HQ bot is not configured.")
    guild_id = str(settings.discord_hq_guild_id)
    channel_id = await feed._ensure_channel(guild_id)
    history = await feed._recent_link_history(channel_id)
    flag = "pitmark_tiktok_sandbox_demo_sent_v1:" + vid
    if url in history or persistent_store.get_runtime_state(flag):
        return _message("TikTok demo already announced", "This video has already appeared in #social-media. Choose another video to test.")
    try:
        when = datetime.fromtimestamp(int(video.get("create_time")), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        when = datetime.now(timezone.utc)
    cover = str(video.get("cover_image_url") or "")
    post = {
        "platform": "tiktok", "url": url,
        "caption": feed._clean_caption(video.get("video_description") or video.get("title")),
        "image": cover if cover.startswith("https://") else "",
        "published_at": when,
    }
    payload = feed._payload(post)
    payload["content"] = "🧪 **TIKTOK SANDBOX DEMONSTRATION** — A verified Pitmark video retrieved through the TikTok API."
    response = await discord_request("POST", f"{DISCORD_API}/channels/{channel_id}/messages", json=payload)
    response.raise_for_status()
    persistent_store.set_runtime_state(flag, str(response.json().get("id") or "sent"))
    return _message("TikTok test announcement posted!",
                    "The authorized TikTok video was sent to Discord #social-media. Switch to Discord to verify the announcement.")
