from __future__ import annotations

import json
import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.discord_hq_common import DISCORD_API, headers

log = logging.getLogger("pitmark.discord.motorsports")

CATEGORY = "🏁 PITMARK MOTORSPORTS"
ROLES = (
    "Pitmark Motorsports • Team Principal",
    "Pitmark Motorsports • Staff",
    "Pitmark Motorsports • Driver",
)
CHANNELS = (
    ("motorsports-announcements", "Official Pitmark Motorsports team announcements."),
    ("motorsports-general", "Conversation with the Pitmark Motorsports team."),
    ("driver-paddock", "Pitmark Motorsports driver discussion."),
    ("race-operations", "Team operations and race preparation."),
    ("team-schedule", "Team schedule and event coordination."),
    ("team-media", "Approved team photos and race media."),
)


class MotorsportsDiscordSnapshot(Base):
    __tablename__ = "discord_motorsports_structure_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), index=True)
    captured_at: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)


async def _api(client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
    for attempt in range(7):
        response = await client.request(method, f"{DISCORD_API}{path}", **kwargs)
        if response.status_code == 429:
            try:
                info = response.json()
                delay = float(info.get("retry_after", 1.0))
            except (ValueError, TypeError):
                delay = 1.0
            delay = max(delay, float(response.headers.get("Retry-After", 0) or 0))
            if attempt == 6:
                raise RuntimeError("Discord rate limit persisted after safe retries")
            await asyncio.sleep(min(90.0, max(0.5, delay) + random.uniform(0.1, 0.4)))
            continue
        response.raise_for_status()
        return response.json() if response.content else {}
    raise RuntimeError("Discord request could not complete")


def _persist_snapshot(guild_id: str, payload: dict[str, Any]) -> int:
    with SessionLocal() as db:
        row = MotorsportsDiscordSnapshot(
            guild_id=guild_id,
            captured_at=datetime.now(timezone.utc).isoformat(),
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def _normalized_channel_field(channel: dict[str, Any], field: str) -> Any:
    """Compare semantics, not Discord's optional/ordering representation."""
    value = channel.get(field)
    if field == "permission_overwrites":
        entries = value or []
        return sorted(
            (str(item.get("id")), str(item.get("type")),
             str(item.get("allow") or "0"), str(item.get("deny") or "0"))
            for item in entries
        )
    if field == "rate_limit_per_user":
        return int(value or 0)
    if field == "nsfw":
        return bool(value)
    if field == "parent_id":
        return str(value) if value is not None else None
    if field == "topic":
        return value or ""
    return value


async def setup(guild_id: str) -> str:
    """Backup first; only create absent roles/category/channels. Never edit existing objects."""
    async with httpx.AsyncClient(headers=headers(), timeout=30) as client:
        guild = await _api(client, "GET", f"/guilds/{guild_id}")
        if str(guild.get("id")) != guild_id:
            raise RuntimeError("Configured guild mismatch. No changes made.")
        roles = await _api(client, "GET", f"/guilds/{guild_id}/roles")
        channels = await _api(client, "GET", f"/guilds/{guild_id}/channels")
        snapshot_id = _persist_snapshot(guild_id, {
            "guild": guild, "roles": roles, "channels": channels
        })
        created = []
        try:
            role_names = {r["name"] for r in roles}
            for name in ROLES:
                if name not in role_names:
                    await _api(client, "POST", f"/guilds/{guild_id}/roles",
                        json={"name": name, "permissions": "0", "mentionable": False},
                        headers={**headers(), "X-Audit-Log-Reason": "Pitmark Motorsports add-only setup"})
                    created.append(f"role: {name}")
            categories = [c for c in channels if c.get("type") == 4 and c.get("name") == CATEGORY]
            if len(categories) > 1:
                raise RuntimeError("Duplicate Motorsports categories detected; refusing ambiguous changes.")
            if categories:
                category_id = categories[0]["id"]
            else:
                category = await _api(client, "POST", f"/guilds/{guild_id}/channels",
                    json={"name": CATEGORY, "type": 4},
                    headers={**headers(), "X-Audit-Log-Reason": "Pitmark Motorsports add-only setup"})
                category_id = category["id"]
                created.append(f"category: {CATEGORY}")
            channels = await _api(client, "GET", f"/guilds/{guild_id}/channels")
            existing = {c["name"] for c in channels if str(c.get("parent_id")) == str(category_id)}
            for name, topic in CHANNELS:
                if name in existing:
                    continue
                await _api(client, "POST", f"/guilds/{guild_id}/channels",
                    json={"name": name, "type": 0, "parent_id": category_id, "topic": topic},
                    headers={**headers(), "X-Audit-Log-Reason": "Pitmark Motorsports add-only setup"})
                created.append(f"channel: #{name}")
            after_roles = await _api(client, "GET", f"/guilds/{guild_id}/roles")
            after_channels = await _api(client, "GET", f"/guilds/{guild_id}/channels")
            old_roles = {r["id"]: r for r in roles}
            old_channels = {c["id"]: c for c in snapshot_channels(snapshot_id)}
            new_roles = {r["id"]: r for r in after_roles}
            new_channels = {c["id"]: c for c in after_channels}
            # Discord may update read-only/transient fields or channel positions
            # after new categories/channels are added. Only compare stable,
            # user-configurable fields, and distinguish external drift from actions
            # performed by this add-only command.
            role_fields = ("name", "permissions", "color", "hoist", "mentionable")
            channel_fields = ("name", "type", "parent_id", "permission_overwrites",
                              "topic", "nsfw", "rate_limit_per_user")
            drift = []
            for role_id, before in old_roles.items():
                after = new_roles.get(role_id)
                if after is None:
                    drift.append(f"missing pre-existing role {role_id}")
                elif any(before.get(field) != after.get(field) for field in role_fields):
                    drift.append(f"role {role_id} settings changed")
            for channel_id, before in old_channels.items():
                after = new_channels.get(channel_id)
                if after is None:
                    drift.append(f"missing pre-existing channel {channel_id}")
                else:
                    changed_fields = [
                        field for field in channel_fields
                        if _normalized_channel_field(before, field)
                        != _normalized_channel_field(after, field)
                    ]
                    if changed_fields:
                        drift.append(
                            f"channel {channel_id} changed fields: "
                            + ", ".join(changed_fields)
                        )
            if drift:
                log.warning("Discord structure drift during Motorsports setup (snapshot=%s): %s",
                            snapshot_id, drift)
                return (f"⚠️ Motorsports inventory checked. Snapshot #{snapshot_id} saved; "
                        f"{len(created)} additions. Existing settings differ from the "
                        f"pre-run snapshot: {', '.join(drift[:5])}. "
                        "The setup command only creates objects and did not edit them.")
            return (f"✅ Motorsports setup verified. Snapshot #{snapshot_id} saved; "
                    f"{len(created)} additions. Existing role/channel settings preserved.")
        except Exception as exc:
            log.exception("Motorsports Discord setup partial failure; snapshot=%s", snapshot_id)
            return f"⚠️ Setup stopped. Snapshot #{snapshot_id} saved; created {len(created)} objects before error: {str(exc)[:350]}. Re-running safely skips existing items."


def snapshot_channels(snapshot_id: int) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        row = db.get(MotorsportsDiscordSnapshot, snapshot_id)
        return json.loads(row.payload_json)["channels"] if row else []
