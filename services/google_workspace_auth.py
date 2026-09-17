"""Shared Google Workspace authentication surface.

Pitmark Cloud already has one refresh-token implementation in google_gmail.
This module deliberately reuses that canonical token source so new Workspace
integrations do not create a second OAuth cache/refresh implementation.
"""

from __future__ import annotations

from services.google_gmail import _token, credentials_configured


def access_token() -> str:
    """Return the current Google Workspace OAuth access token."""
    return _token()


def workspace_credentials_configured() -> bool:
    """Whether the canonical Pitmark Workspace OAuth credentials are present."""
    return credentials_configured()


def authorization_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token()}"}
