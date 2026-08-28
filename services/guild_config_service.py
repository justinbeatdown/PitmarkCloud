from __future__ import annotations

from typing import Any

from services import persistent_store


def configure(
    guild_id: str,
    guild_name: str,
    channel_id: str,
    channel_name: str,
    configured_by_user_id: str,
) -> dict[str, Any]:
    return persistent_store.upsert_guild_config({
        "guild_id": guild_id,
        "guild_name": guild_name or "Discord Server",
        "share_channel_id": channel_id,
        "share_channel_name": channel_name or channel_id,
        "enabled": True,
        "configured_by_user_id": configured_by_user_id,
    })


def get(guild_id: str) -> dict[str, Any] | None:
    return persistent_store.get_guild_config(guild_id)


def reset(guild_id: str) -> bool:
    return persistent_store.delete_guild_config(guild_id)


def all_enabled() -> list[dict[str, Any]]:
    return persistent_store.list_guild_configs()
