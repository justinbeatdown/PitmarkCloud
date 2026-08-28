from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Float, Integer, String, Text, select, delete
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiscordLinkRow(Base):
    __tablename__ = "discord_links"

    device_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    discord_user_id: Mapped[str] = mapped_column(String(32), index=True, default="")
    username: Mapped[str] = mapped_column(String(120), default="")
    global_name: Mapped[str] = mapped_column(String(120), default="")
    avatar: Mapped[str] = mapped_column(String(180), default="")
    access_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, default="")
    token_expires_at: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[float] = mapped_column(Float, default=0.0)


class GuildConfigRow(Base):
    __tablename__ = "discord_guild_configs"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    guild_name: Mapped[str] = mapped_column(String(180), default="Discord Server")
    share_channel_id: Mapped[str] = mapped_column(String(32), default="")
    share_channel_name: Mapped[str] = mapped_column(String(180), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configured_by_user_id: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


class RaceResultRow(Base):
    __tablename__ = "race_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discord_user_id: Mapped[str] = mapped_column(String(32), index=True)
    device_id: Mapped[str] = mapped_column(String(200), default="")
    session_id: Mapped[str] = mapped_column(String(180), default="", index=True)
    date: Mapped[str] = mapped_column(String(180), default="")
    track_name: Mapped[str] = mapped_column(String(180), default="Unknown Track")
    car_name: Mapped[str] = mapped_column(String(180), default="Unknown Car")
    session_type: Mapped[str] = mapped_column(String(180), default="iRacing Session")
    laps: Mapped[int] = mapped_column(Integer, default=0)
    best_lap_time: Mapped[float] = mapped_column(Float, default=0.0)
    average_lap_time: Mapped[float] = mapped_column(Float, default=0.0)
    starting_position: Mapped[int] = mapped_column(Integer, default=0)
    finishing_position: Mapped[int] = mapped_column(Integer, default=0)
    incidents: Mapped[int] = mapped_column(Integer, default=0)
    consistency: Mapped[float] = mapped_column(Float, default=0.0)
    average_fuel_per_lap: Mapped[float] = mapped_column(Float, default=0.0)
    published_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


def upsert_link(values: dict[str, Any]) -> None:
    with SessionLocal() as db:
        row = db.get(DiscordLinkRow, values["device_id"])
        if row is None:
            row = DiscordLinkRow(device_id=values["device_id"])
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key):
                setattr(row, key, value)
        db.commit()


def get_link(device_id: str) -> DiscordLinkRow | None:
    with SessionLocal() as db:
        return db.get(DiscordLinkRow, device_id)


def delete_link(device_id: str) -> bool:
    with SessionLocal() as db:
        result = db.execute(delete(DiscordLinkRow).where(DiscordLinkRow.device_id == device_id))
        db.commit()
        return bool(result.rowcount)


def find_link_by_user(discord_user_id: str) -> DiscordLinkRow | None:
    with SessionLocal() as db:
        return db.scalar(
            select(DiscordLinkRow)
            .where(DiscordLinkRow.discord_user_id == discord_user_id, DiscordLinkRow.status == "connected")
            .order_by(DiscordLinkRow.updated_at.desc())
        )


def upsert_guild_config(values: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.get(GuildConfigRow, values["guild_id"])
        if row is None:
            row = GuildConfigRow(guild_id=values["guild_id"])
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
        return guild_config_dict(row)


def get_guild_config(guild_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.get(GuildConfigRow, guild_id)
        return guild_config_dict(row) if row else None


def list_guild_configs() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.scalars(select(GuildConfigRow).where(GuildConfigRow.enabled.is_(True))).all()
        return [guild_config_dict(row) for row in rows]


def delete_guild_config(guild_id: str) -> bool:
    with SessionLocal() as db:
        result = db.execute(delete(GuildConfigRow).where(GuildConfigRow.guild_id == guild_id))
        db.commit()
        return bool(result.rowcount)


def guild_config_dict(row: GuildConfigRow) -> dict[str, Any]:
    return {
        "guild_id": row.guild_id,
        "guild_name": row.guild_name,
        "share_channel_id": row.share_channel_id,
        "share_channel_name": row.share_channel_name,
        "enabled": row.enabled,
        "configured_by_user_id": row.configured_by_user_id,
        "updated_at": row.updated_at,
    }


def publish_result(values: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        discord_user_id = values["discord_user_id"]
        session_id = values.get("session_id") or ""
        row = None
        if session_id:
            row = db.scalar(
                select(RaceResultRow).where(
                    RaceResultRow.discord_user_id == discord_user_id,
                    RaceResultRow.session_id == session_id,
                )
            )
        if row is None:
            row = RaceResultRow(discord_user_id=discord_user_id)
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.published_at = _now_iso()
        db.commit()
        db.refresh(row)
        return result_dict(row)


def recent_results(discord_user_id: str, limit: int) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(RaceResultRow)
            .where(RaceResultRow.discord_user_id == discord_user_id)
            .order_by(RaceResultRow.id.desc())
            .limit(limit)
        ).all()
        return [result_dict(row) for row in rows]


def result_dict(row: RaceResultRow) -> dict[str, Any]:
    return {
        "device_id": row.device_id,
        "discord_user_id": row.discord_user_id,
        "session_id": row.session_id,
        "date": row.date,
        "track_name": row.track_name,
        "car_name": row.car_name,
        "session_type": row.session_type,
        "laps": row.laps,
        "best_lap_time": row.best_lap_time,
        "average_lap_time": row.average_lap_time,
        "starting_position": row.starting_position,
        "finishing_position": row.finishing_position,
        "incidents": row.incidents,
        "consistency": row.consistency,
        "average_fuel_per_lap": row.average_fuel_per_lap,
        "published_at": row.published_at,
    }
