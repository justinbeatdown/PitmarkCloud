from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

from sqlalchemy import Boolean, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal

BAN_ENV_VAR = "PRT_PERMANENTLY_BANNED_DISCORD_IDS"
DENIED_MESSAGE = "Access to Pitmark Racing Tools is not available for this account."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_discord_user_id(value: str | int | None) -> str:
    text = str(value or "").strip()
    if not text.isdigit() or len(text) > 32:
        return ""
    return text


class PrtAccessBanRow(Base):
    __tablename__ = "prt_access_bans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    permanent: Mapped[bool] = mapped_column(Boolean, default=True)
    banned_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    revoked_at: Mapped[str] = mapped_column(String(64), default="")


def ban_discord_user(
    discord_user_id: str | int,
    *,
    reason: str = "Permanent PRT access ban",
    permanent: bool = True,
) -> dict:
    normalized = _normalize_discord_user_id(discord_user_id)
    if not normalized:
        raise ValueError("Invalid Discord user ID.")

    with SessionLocal() as db:
        row = db.scalar(
            select(PrtAccessBanRow).where(PrtAccessBanRow.discord_user_id == normalized)
        )
        if row is None:
            row = PrtAccessBanRow(discord_user_id=normalized)
            db.add(row)
        row.reason = (reason or "Permanent PRT access ban").strip()[:500]
        row.permanent = bool(permanent)
        row.banned_at = _now_iso()
        row.revoked_at = ""
        db.commit()
        db.refresh(row)

    block_known_devices_for_discord(normalized)
    return {
        "discord_user_id": row.discord_user_id,
        "reason": row.reason,
        "permanent": row.permanent,
        "banned_at": row.banned_at,
        "revoked_at": row.revoked_at,
    }


def active_ban(discord_user_id: str | int | None) -> dict | None:
    normalized = _normalize_discord_user_id(discord_user_id)
    if not normalized:
        return None
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtAccessBanRow).where(
                PrtAccessBanRow.discord_user_id == normalized,
                PrtAccessBanRow.revoked_at == "",
            )
        )
        if row is None:
            return None
        return {
            "discord_user_id": row.discord_user_id,
            "reason": row.reason,
            "permanent": row.permanent,
            "banned_at": row.banned_at,
        }


def is_discord_banned(discord_user_id: str | int | None) -> bool:
    return active_ban(discord_user_id) is not None


def revoke_discord_ban(discord_user_id: str | int) -> bool:
    normalized = _normalize_discord_user_id(discord_user_id)
    if not normalized:
        return False
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtAccessBanRow).where(PrtAccessBanRow.discord_user_id == normalized)
        )
        if row is None:
            return False
        row.revoked_at = _now_iso()
        db.commit()
        return True


def enforce_device_ban_if_linked(device_id: str | None) -> bool:
    device_id = str(device_id or "").strip()
    if not device_id:
        return False

    from services import persistent_store

    link = persistent_store.get_link(device_id)
    if link is None or not is_discord_banned(link.discord_user_id):
        return False

    persistent_store.upsert_link({
        "device_id": device_id,
        "status": "blocked",
        "discord_user_id": link.discord_user_id,
        "username": link.username,
        "global_name": link.global_name,
        "avatar": link.avatar,
        "access_token_encrypted": "",
        "refresh_token_encrypted": "",
        "token_expires_at": 0.0,
        "error": DENIED_MESSAGE,
        "updated_at": time.time(),
    })

    # If the device already has an entitlement, kill it immediately and remove
    # offline grace so a cached paid/Early Access grant cannot outlive the ban.
    from services.prt_licensing_store import PrtEntitlementRow

    with SessionLocal() as db:
        entitlement = db.get(PrtEntitlementRow, device_id)
        if entitlement is not None:
            entitlement.status = "banned"
            entitlement.offline_grace_until = _now_iso()
            entitlement.updated_at = _now_iso()
            db.commit()
    return True


def block_known_devices_for_discord(discord_user_id: str | int) -> int:
    normalized = _normalize_discord_user_id(discord_user_id)
    if not normalized:
        return 0

    from services.persistent_store import DiscordLinkRow

    with SessionLocal() as db:
        device_ids = list(
            db.scalars(
                select(DiscordLinkRow.device_id).where(
                    DiscordLinkRow.discord_user_id == normalized
                )
            ).all()
        )

    blocked = 0
    for device_id in device_ids:
        if enforce_device_ban_if_linked(device_id):
            blocked += 1
    return blocked


def seed_from_environment() -> int:
    raw = (os.getenv(BAN_ENV_VAR) or "").strip()
    if not raw:
        return 0

    seeded = 0
    for candidate in re.split(r"[\s,;]+", raw):
        normalized = _normalize_discord_user_id(candidate)
        if not normalized:
            continue
        ban_discord_user(
            normalized,
            reason="Permanent PRT ban seeded from server configuration",
            permanent=True,
        )
        seeded += 1
    return seeded


def interaction_discord_user_id(payload: dict) -> str:
    member = payload.get("member") if isinstance(payload, dict) else None
    member_user = member.get("user") if isinstance(member, dict) else None
    direct_user = payload.get("user") if isinstance(payload, dict) else None
    candidate = ""
    if isinstance(member_user, dict):
        candidate = str(member_user.get("id") or "")
    elif isinstance(direct_user, dict):
        candidate = str(direct_user.get("id") or "")
    return _normalize_discord_user_id(candidate)
