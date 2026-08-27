from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from utils.config import settings

DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN = "https://discord.com/api/oauth2/token"


@dataclass
class DiscordLink:
    device_id: str
    status: str = "pending"
    discord_user_id: str = ""
    username: str = ""
    global_name: str = ""
    avatar: str = ""
    error: str = ""
    updated_at: float = 0.0


_links: dict[str, DiscordLink] = {}


def configured() -> bool:
    return bool(
        settings.discord_client_id
        and settings.discord_client_secret
        and settings.discord_redirect_uri
        and settings.pitmark_signing_secret
        and settings.pitmark_signing_secret != "development-only"
    )


def status() -> dict:
    return {
        "configured": configured(),
        "connected": False,
        "message": (
            "Discord OAuth is configured on Pitmark Cloud."
            if configured()
            else "Discord OAuth is scaffolded but Render credentials are not configured yet."
        ),
    }


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_state(device_id: str) -> str:
    payload = {
        "device_id": device_id,
        "nonce": secrets.token_urlsafe(12),
        "iat": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(
        settings.pitmark_signing_secret.encode(), raw, hashlib.sha256
    ).digest()
    return f"{_b64(raw)}.{_b64(signature)}"


def read_state(state: str) -> dict:
    try:
        raw_part, sig_part = state.split(".", 1)
        raw = _unb64(raw_part)
        supplied = _unb64(sig_part)
        expected = hmac.new(
            settings.pitmark_signing_secret.encode(), raw, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("Invalid OAuth state signature.")
        payload = json.loads(raw)
        if int(time.time()) - int(payload["iat"]) > 600:
            raise ValueError("OAuth state expired.")
        return payload
    except Exception as exc:
        raise ValueError("Invalid OAuth state.") from exc


def create_link(device_id: str) -> dict:
    if not configured():
        raise RuntimeError("Discord OAuth is not configured on Pitmark Cloud.")
    device_id = device_id.strip()
    if not device_id or len(device_id) > 200:
        raise ValueError("Invalid device id.")

    _links[device_id] = DiscordLink(
        device_id=device_id, status="pending", updated_at=time.time()
    )
    state = make_state(device_id)
    query = urlencode({
        "response_type": "code",
        "client_id": settings.discord_client_id,
        "scope": "identify",
        "state": state,
        "redirect_uri": settings.discord_redirect_uri,
        "prompt": "consent",
    })
    return {
        "device_id": device_id,
        "status": "pending",
        "authorization_url": f"{DISCORD_AUTHORIZE}?{query}",
    }


async def complete_link(code: str, state: str) -> DiscordLink:
    payload = read_state(state)
    device_id = payload["device_id"]
    link = _links.get(device_id) or DiscordLink(device_id=device_id)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                DISCORD_TOKEN,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.discord_redirect_uri,
                },
                auth=(settings.discord_client_id, settings.discord_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
            token = token_response.json()["access_token"]

            user_response = await client.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"Bearer {token}"},
            )
            user_response.raise_for_status()
            user = user_response.json()

        link.status = "connected"
        link.discord_user_id = str(user.get("id", ""))
        link.username = str(user.get("username", ""))
        link.global_name = str(user.get("global_name") or "")
        link.avatar = str(user.get("avatar") or "")
        link.error = ""
        link.updated_at = time.time()
    except Exception as exc:
        link.status = "error"
        link.error = str(exc)
        link.updated_at = time.time()
    _links[device_id] = link
    return link


def link_status(device_id: str) -> dict:
    link = _links.get(device_id)
    if not link:
        return {
            "device_id": device_id,
            "status": "not_found",
            "connected": False,
        }
    return {
        "device_id": device_id,
        "status": link.status,
        "connected": link.status == "connected",
        "discord_user_id": link.discord_user_id,
        "username": link.username,
        "global_name": link.global_name,
        "avatar": link.avatar,
        "error": link.error,
    }


def disconnect(device_id: str) -> dict:
    existed = _links.pop(device_id, None) is not None
    return {"device_id": device_id, "disconnected": existed}


def find_link_by_discord_user_id(discord_user_id: str) -> dict | None:
    if not discord_user_id:
        return None
    for link in _links.values():
        if link.status == "connected" and link.discord_user_id == discord_user_id:
            return {
                "device_id": link.device_id,
                "discord_user_id": link.discord_user_id,
                "username": link.username,
                "global_name": link.global_name,
                "avatar": link.avatar,
            }
    return None
