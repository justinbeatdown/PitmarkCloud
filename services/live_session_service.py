from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from services import discord_service


@dataclass
class LiveSession:
    device_id: str
    discord_user_id: str
    track_name: str = "iRacing Session"
    car_name: str = "Player Car"
    lap: int = 0
    position: int = 0
    current_lap_time: float = 0.0
    best_lap_time: float = 0.0
    delta: float = 0.0
    speed_mph: float = 0.0
    gear: int = 0
    rpm: int = 0
    fuel_gallons: float = 0.0
    fuel_laps_remaining: float = 0.0
    incident_count: int = 0
    flag_text: str = "GREEN"
    track_temp_f: float = 0.0
    session_laps_remaining: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_sessions: dict[str, LiveSession] = {}
_lock = Lock()


def update_session(device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    link = discord_service.link_status(device_id)
    if not link.get("connected"):
        raise PermissionError("This device is not linked to Discord.")

    discord_user_id = str(link.get("discord_user_id") or "")
    if not discord_user_id:
        raise PermissionError("Linked Discord identity is missing.")

    def _s(name: str, default: str = "") -> str:
        value = payload.get(name, default)
        return str(value)[:160]

    def _i(name: str, default: int = 0) -> int:
        try:
            return int(payload.get(name, default))
        except (TypeError, ValueError):
            return default

    def _f(name: str, default: float = 0.0) -> float:
        try:
            return float(payload.get(name, default))
        except (TypeError, ValueError):
            return default

    session = LiveSession(
        device_id=device_id,
        discord_user_id=discord_user_id,
        track_name=_s("track_name", "iRacing Session"),
        car_name=_s("car_name", "Player Car"),
        lap=max(0, _i("lap")),
        position=max(0, _i("position")),
        current_lap_time=max(0.0, _f("current_lap_time")),
        best_lap_time=max(0.0, _f("best_lap_time")),
        delta=_f("delta"),
        speed_mph=max(0.0, _f("speed_mph")),
        gear=_i("gear"),
        rpm=max(0, _i("rpm")),
        fuel_gallons=max(0.0, _f("fuel_gallons")),
        fuel_laps_remaining=max(0.0, _f("fuel_laps_remaining")),
        incident_count=max(0, _i("incident_count")),
        flag_text=_s("flag_text", "GREEN").upper(),
        track_temp_f=_f("track_temp_f"),
        session_laps_remaining=max(0, _i("session_laps_remaining")),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    with _lock:
        _sessions[discord_user_id] = session

    return session.to_dict()


def clear_session(device_id: str) -> bool:
    link = discord_service.link_status(device_id)
    discord_user_id = str(link.get("discord_user_id") or "")
    if not discord_user_id:
        return False
    with _lock:
        return _sessions.pop(discord_user_id, None) is not None


def get_for_device(device_id: str) -> dict[str, Any] | None:
    if not device_id:
        return None
    link = discord_service.link_status(device_id)
    discord_user_id = str(link.get("discord_user_id") or "")
    if not discord_user_id:
        return None
    return get_for_discord_user(discord_user_id)


def get_for_discord_user(discord_user_id: str) -> dict[str, Any] | None:
    if not discord_user_id:
        return None
    with _lock:
        session = _sessions.get(discord_user_id)
        return session.to_dict() if session else None


def is_fresh(session: dict[str, Any], max_age_seconds: int = 20) -> bool:
    try:
        updated = datetime.fromisoformat(str(session["updated_at"]).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - updated).total_seconds() <= max_age_seconds
    except Exception:
        return False
