from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services import discord_service, persistent_store


def publish_result(device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise PermissionError("This device is not linked to Discord.")

    discord_user_id = str(link.get("discord_user_id") or "")
    if not discord_user_id:
        raise PermissionError("Linked Discord identity is missing.")

    def _s(name: str, default: str = "") -> str:
        return str(payload.get(name, default) or default)[:180]
    def _i(name: str, default: int = 0) -> int:
        try: return int(payload.get(name, default))
        except (TypeError, ValueError): return default
    def _f(name: str, default: float = 0.0) -> float:
        try: return float(payload.get(name, default))
        except (TypeError, ValueError): return default

    return persistent_store.publish_result({
        "device_id": device_id,
        "discord_user_id": discord_user_id,
        "session_id": _s("session_id"),
        "date": _s("date", datetime.now(timezone.utc).isoformat()),
        "track_name": _s("track_name", "Unknown Track"),
        "car_name": _s("car_name", "Unknown Car"),
        "session_type": _s("session_type", "iRacing Session"),
        "laps": max(0, _i("laps")),
        "best_lap_time": max(0.0, _f("best_lap_time")),
        "average_lap_time": max(0.0, _f("average_lap_time")),
        "starting_position": max(0, _i("starting_position")),
        "finishing_position": max(0, _i("finishing_position")),
        "incidents": max(0, _i("incidents")),
        "consistency": max(0.0, min(100.0, _f("consistency"))),
        "average_fuel_per_lap": max(0.0, _f("average_fuel_per_lap")),
    })


def get_latest_for_discord_user(discord_user_id: str) -> dict[str, Any] | None:
    items = persistent_store.recent_results(discord_user_id, 1) if discord_user_id else []
    return items[0] if items else None


def get_recent_for_discord_user(discord_user_id: str, limit: int = 5) -> list[dict[str, Any]]:
    if not discord_user_id: return []
    return persistent_store.recent_results(discord_user_id, max(1, min(10, int(limit))))


def get_driver_summary(discord_user_id: str) -> dict[str, Any]:
    recent = get_recent_for_discord_user(discord_user_id, 10)
    if not recent:
        return {"sessions": 0, "laps": 0, "best_lap_time": 0.0, "avg_finish": 0.0, "incidents": 0}
    finishes = [int(r.get("finishing_position") or 0) for r in recent if int(r.get("finishing_position") or 0) > 0]
    bests = [float(r.get("best_lap_time") or 0.0) for r in recent if float(r.get("best_lap_time") or 0.0) > 0]
    return {
        "sessions": len(recent),
        "laps": sum(int(r.get("laps") or 0) for r in recent),
        "best_lap_time": min(bests) if bests else 0.0,
        "avg_finish": (sum(finishes) / len(finishes)) if finishes else 0.0,
        "incidents": sum(int(r.get("incidents") or 0) for r in recent),
    }
