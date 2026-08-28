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
from cryptography.fernet import Fernet, InvalidToken

from services import persistent_store
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


def configured() -> bool:
    return bool(
        settings.discord_client_id
        and settings.discord_client_secret
        and settings.discord_redirect_uri
        and settings.pitmark_signing_secret
        and settings.pitmark_signing_secret != "development-only"
    )



def install_url() -> str:
    if not settings.discord_client_id:
        return ""
    query = urlencode({
        "client_id": settings.discord_client_id,
        "scope": "bot applications.commands",
        "permissions": str(settings.discord_install_permissions),
    })
    return f"{DISCORD_AUTHORIZE}?{query}"


def status() -> dict:
    return {
        "configured": configured(),
        "connected": False,
        "oauth_scopes": ["identify", "guilds"],
        "install_url": install_url(),
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


def _fernet() -> Fernet:
    # Derive a stable Fernet key from the existing server-side signing secret.
    digest = hashlib.sha256(settings.pitmark_signing_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii") if value else ""


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def make_state(device_id: str) -> str:
    payload = {"device_id": device_id, "nonce": secrets.token_urlsafe(12), "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(settings.pitmark_signing_secret.encode(), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(signature)}"


def read_state(state: str) -> dict:
    try:
        raw_part, sig_part = state.split(".", 1)
        raw = _unb64(raw_part)
        supplied = _unb64(sig_part)
        expected = hmac.new(settings.pitmark_signing_secret.encode(), raw, hashlib.sha256).digest()
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

    persistent_store.upsert_link({
        "device_id": device_id,
        "status": "pending",
        "error": "",
        "updated_at": time.time(),
    })
    state = make_state(device_id)
    query = urlencode({
        "response_type": "code",
        "client_id": settings.discord_client_id,
        "scope": "identify guilds",
        "state": state,
        "redirect_uri": settings.discord_redirect_uri,
        "prompt": "consent",
    })
    return {"device_id": device_id, "status": "pending", "authorization_url": f"{DISCORD_AUTHORIZE}?{query}"}


async def complete_link(code: str, state: str) -> DiscordLink:
    payload = read_state(state)
    device_id = payload["device_id"]
    link = DiscordLink(device_id=device_id)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                DISCORD_TOKEN,
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.discord_redirect_uri},
                auth=(settings.discord_client_id, settings.discord_client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = str(token_data["access_token"])
            refresh_token = str(token_data.get("refresh_token") or "")
            expires_in = float(token_data.get("expires_in") or 0)

            user_response = await client.get(f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {access_token}"})
            user_response.raise_for_status()
            user = user_response.json()

        link.status = "connected"
        link.discord_user_id = str(user.get("id", ""))
        link.username = str(user.get("username", ""))
        link.global_name = str(user.get("global_name") or "")
        link.avatar = str(user.get("avatar") or "")
        link.updated_at = time.time()
        persistent_store.upsert_link({
            "device_id": device_id,
            "status": link.status,
            "discord_user_id": link.discord_user_id,
            "username": link.username,
            "global_name": link.global_name,
            "avatar": link.avatar,
            "access_token_encrypted": _encrypt(access_token),
            "refresh_token_encrypted": _encrypt(refresh_token),
            "token_expires_at": time.time() + max(0, expires_in - 60),
            "error": "",
            "updated_at": link.updated_at,
        })
    except Exception as exc:
        link.status = "error"
        link.error = str(exc)
        link.updated_at = time.time()
        persistent_store.upsert_link({
            "device_id": device_id,
            "status": "error",
            "error": link.error[:1000],
            "updated_at": link.updated_at,
        })
    return link


def _row_to_status(row) -> dict:
    if row is None:
        return {"status": "not_found", "connected": False}
    return {
        "device_id": row.device_id,
        "status": row.status,
        "connected": row.status == "connected",
        "discord_user_id": row.discord_user_id,
        "username": row.username,
        "global_name": row.global_name,
        "avatar": row.avatar,
        "error": row.error,
    }


def link_status(device_id: str) -> dict:
    result = _row_to_status(persistent_store.get_link(device_id))
    result.setdefault("device_id", device_id)
    return result


def disconnect(device_id: str) -> dict:
    existed = persistent_store.delete_link(device_id)
    return {"device_id": device_id, "disconnected": existed}


def find_link_by_discord_user_id(discord_user_id: str) -> dict | None:
    if not discord_user_id:
        return None
    row = persistent_store.find_link_by_user(discord_user_id)
    if not row:
        return None
    return {
        "device_id": row.device_id,
        "discord_user_id": row.discord_user_id,
        "username": row.username,
        "global_name": row.global_name,
        "avatar": row.avatar,
    }


async def _refresh_access_token(row) -> tuple[str, object]:
    access_token = _decrypt(row.access_token_encrypted)
    if access_token and row.token_expires_at > time.time():
        return access_token, row

    refresh_token = _decrypt(row.refresh_token_encrypted)
    if not refresh_token:
        raise PermissionError("Discord authorization expired. Reconnect Discord in Pitmark Racing Tools.")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            DISCORD_TOKEN,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(settings.discord_client_id, settings.discord_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()

    access_token = str(token_data["access_token"])
    new_refresh = str(token_data.get("refresh_token") or refresh_token)
    persistent_store.upsert_link({
        "device_id": row.device_id,
        "access_token_encrypted": _encrypt(access_token),
        "refresh_token_encrypted": _encrypt(new_refresh),
        "token_expires_at": time.time() + max(0, float(token_data.get("expires_in") or 0) - 60),
        "updated_at": time.time(),
    })
    return access_token, persistent_store.get_link(row.device_id)


async def user_guilds(device_id: str) -> list[dict]:
    row = persistent_store.get_link(device_id)
    if not row or row.status != "connected":
        raise PermissionError("Connect Discord in Pitmark Racing Tools first.")
    access_token, _ = await _refresh_access_token(row)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{DISCORD_API}/users/@me/guilds", params={"limit": 200}, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        guilds = response.json()
    return guilds if isinstance(guilds, list) else []
