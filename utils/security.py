from __future__ import annotations

import html
import re
import secrets
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Iterable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
DISCORD_ID_RE = re.compile(r"^[0-9]{5,32}$")
MAX_REQUEST_BODY = 1024 * 1024


def validate_device_id(value: str) -> str:
    value = (value or "").strip()
    if not DEVICE_ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid device identifier.")
    return value


def validate_discord_id(value: str, field: str = "Discord identifier") -> str:
    value = (value or "").strip()
    if not DISCORD_ID_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field.lower()}.")
    return value


def safe_html(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY:
                    return JSONResponse({"detail": "Request body too large."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length header."}, status_code=400)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/api/discord/oauth/callback":
            # OAuth completion is a tiny server-rendered page. Permit only inline CSS on this
            # one route so branding survives CSP; scripts, frames, forms, images and network
            # resources remain blocked.
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'none'; img-src 'none'; script-src 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
            )
        response.headers["X-Pitmark-Request-Id"] = request.headers.get("X-Request-Id") or secrets.token_hex(8)
        return response


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


_rate_limiter = SlidingWindowRateLimiter()


def client_ip(request: Request) -> str:
    # Render sits behind a proxy. We intentionally use only the first forwarded value,
    # falling back to the ASGI peer. Rate limiting is defense-in-depth, not authentication.
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def enforce_rate_limit(request: Request, bucket: str, limit: int, window_seconds: int = 60) -> None:
    key = f"{bucket}:{client_ip(request)}"
    if not _rate_limiter.allow(key, limit, window_seconds):
        raise HTTPException(status_code=429, detail="Too many requests. Try again shortly.")


def security_summary(*, environment: str, signing_secret: str, admin_key: str, cors_origins: Iterable[str]) -> dict:
    production = environment.strip().lower() == "production"
    signing_ok = bool(signing_secret and signing_secret != "development-only" and len(signing_secret) >= 32)
    admin_ok = bool(admin_key and len(admin_key) >= 24)
    origins = list(cors_origins)
    wildcard_cors = "*" in origins
    return {
        "environment": environment,
        "production_mode": production,
        "signing_secret_hardened": signing_ok,
        "admin_key_hardened": admin_ok,
        "wildcard_cors": wildcard_cors,
        "max_request_body_bytes": MAX_REQUEST_BODY,
        "security_headers": True,
        "device_id_validation": True,
        "rate_limiting": True,
        "discord_signature_verification": True,
        "oauth_tokens_encrypted_at_rest": signing_ok,
        "ready": production and signing_ok and admin_ok and not wildcard_cors,
    }
