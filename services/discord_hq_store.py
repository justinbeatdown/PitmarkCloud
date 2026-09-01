from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiscordHQStateRow(Base):
    __tablename__ = "discord_hq_state"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    bootstrapped: Mapped[bool] = mapped_column(Boolean, default=False)
    bootstrapped_by_user_id: Mapped[str] = mapped_column(String(32), default="")
    bootstrapped_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


class DiscordSupportTicketRow(Base):
    __tablename__ = "discord_support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), index=True)
    channel_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    opened_by_user_id: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(60), default="other")
    subject: Mapped[str] = mapped_column(String(180), default="Support Request")
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    claimed_by_user_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    closed_at: Mapped[str] = mapped_column(String(64), default="")


class DiscordChannelLockRow(Base):
    __tablename__ = "discord_channel_locks"

    channel_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    guild_id: Mapped[str] = mapped_column(String(32), index=True)
    previous_allow: Mapped[str] = mapped_column(Text, default="0")
    previous_deny: Mapped[str] = mapped_column(Text, default="0")
    locked_by_user_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


class DiscordModerationCaseRow(Base):
    __tablename__ = "discord_moderation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[str] = mapped_column(String(32), index=True)
    target_user_id: Mapped[str] = mapped_column(String(32), index=True)
    moderator_user_id: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


def get_hq_state(guild_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.get(DiscordHQStateRow, guild_id)
        if not row:
            return None
        return {
            "guild_id": row.guild_id,
            "bootstrapped": row.bootstrapped,
            "bootstrapped_by_user_id": row.bootstrapped_by_user_id,
            "bootstrapped_at": row.bootstrapped_at,
            "updated_at": row.updated_at,
        }


def mark_bootstrapped(guild_id: str, user_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.get(DiscordHQStateRow, guild_id)
        if row is None:
            row = DiscordHQStateRow(guild_id=guild_id)
            db.add(row)
        row.bootstrapped = True
        row.bootstrapped_by_user_id = user_id
        if not row.bootstrapped_at:
            row.bootstrapped_at = _now_iso()
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
        return {
            "guild_id": row.guild_id,
            "bootstrapped": row.bootstrapped,
            "bootstrapped_by_user_id": row.bootstrapped_by_user_id,
            "bootstrapped_at": row.bootstrapped_at,
            "updated_at": row.updated_at,
        }


def open_ticket_for_user(guild_id: str, user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.scalar(
            select(DiscordSupportTicketRow)
            .where(
                DiscordSupportTicketRow.guild_id == guild_id,
                DiscordSupportTicketRow.opened_by_user_id == user_id,
                DiscordSupportTicketRow.status.in_(["open", "claimed"]),
            )
            .order_by(DiscordSupportTicketRow.id.desc())
        )
        return ticket_dict(row) if row else None


def create_ticket(values: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        row = DiscordSupportTicketRow(**values)
        db.add(row)
        db.commit()
        db.refresh(row)
        return ticket_dict(row)


def ticket_by_channel(channel_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.scalar(select(DiscordSupportTicketRow).where(DiscordSupportTicketRow.channel_id == channel_id))
        return ticket_dict(row) if row else None


def claim_ticket(channel_id: str, staff_user_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.scalar(select(DiscordSupportTicketRow).where(DiscordSupportTicketRow.channel_id == channel_id))
        if row is None:
            return None
        row.status = "claimed"
        row.claimed_by_user_id = staff_user_id
        db.commit()
        db.refresh(row)
        return ticket_dict(row)


def close_ticket(channel_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.scalar(select(DiscordSupportTicketRow).where(DiscordSupportTicketRow.channel_id == channel_id))
        if row is None:
            return None
        row.status = "closed"
        row.closed_at = _now_iso()
        db.commit()
        db.refresh(row)
        return ticket_dict(row)


def ticket_dict(row: DiscordSupportTicketRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "guild_id": row.guild_id,
        "channel_id": row.channel_id,
        "opened_by_user_id": row.opened_by_user_id,
        "category": row.category,
        "subject": row.subject,
        "details": row.details,
        "status": row.status,
        "claimed_by_user_id": row.claimed_by_user_id,
        "created_at": row.created_at,
        "closed_at": row.closed_at,
    }


def add_moderation_case(
    guild_id: str,
    target_user_id: str,
    moderator_user_id: str,
    action: str,
    reason: str,
    duration_minutes: int = 0,
) -> dict[str, Any]:
    with SessionLocal() as db:
        row = DiscordModerationCaseRow(
            guild_id=guild_id,
            target_user_id=target_user_id,
            moderator_user_id=moderator_user_id,
            action=action,
            reason=reason,
            duration_minutes=duration_minutes,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return moderation_case_dict(row)


def moderation_history(guild_id: str, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(DiscordModerationCaseRow)
            .where(
                DiscordModerationCaseRow.guild_id == guild_id,
                DiscordModerationCaseRow.target_user_id == user_id,
            )
            .order_by(DiscordModerationCaseRow.id.desc())
            .limit(max(1, min(limit, 25)))
        ).all()
        return [moderation_case_dict(row) for row in rows]


def moderation_case_dict(row: DiscordModerationCaseRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "guild_id": row.guild_id,
        "target_user_id": row.target_user_id,
        "moderator_user_id": row.moderator_user_id,
        "action": row.action,
        "reason": row.reason,
        "duration_minutes": row.duration_minutes,
        "created_at": row.created_at,
    }


def save_channel_lock(guild_id: str, channel_id: str, previous_allow: int, previous_deny: int, user_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(DiscordChannelLockRow, channel_id)
        if row is None:
            row = DiscordChannelLockRow(
                channel_id=channel_id,
                guild_id=guild_id,
                previous_allow=str(previous_allow),
                previous_deny=str(previous_deny),
                locked_by_user_id=user_id,
            )
            db.add(row)
            db.commit()


def get_channel_lock(channel_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.get(DiscordChannelLockRow, channel_id)
        if row is None:
            return None
        return {
            "channel_id": row.channel_id,
            "guild_id": row.guild_id,
            "previous_allow": int(row.previous_allow or 0),
            "previous_deny": int(row.previous_deny or 0),
            "locked_by_user_id": row.locked_by_user_id,
            "created_at": row.created_at,
        }


def delete_channel_lock(channel_id: str) -> bool:
    with SessionLocal() as db:
        result = db.execute(delete(DiscordChannelLockRow).where(DiscordChannelLockRow.channel_id == channel_id))
        db.commit()
        return bool(result.rowcount)
