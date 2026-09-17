"""Google Workspace authentication for non-Gmail services.

Sheets access must never reuse the Gmail-only refresh token. A Google refresh
token cannot gain additional OAuth scopes during refresh, so Control Center
Sheets access uses its own refresh token and token cache.
"""

from __future__ import annotations

import os
import threading
import time

import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

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


def workspace_credentials_configured() -> bool:
    """Whether a dedicated Sheets-capable Workspace refresh token is present."""
    return bool(_client_id() and _client_secret() and _env("GOOGLE_WORKSPACE_REFRESH_TOKEN"))


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
                    "refresh_token": _env("GOOGLE_WORKSPACE_REFRESH_TOKEN"),
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
