from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import SystemRandom
import hashlib

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


_rng = SystemRandom()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class PrtMobilePairingRow(Base):
    __tablename__ = "prt_mobile_pairings"

    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    desktop_device_id: Mapped[str] = mapped_column(String(64), index=True)
    discord_user_id: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[str] = mapped_column(String(64))
    claimed_at: Mapped[str] = mapped_column(String(64), default="")
    mobile_device_id: Mapped[str] = mapped_column(String(64), default="")


def issue(desktop_device_id: str, discord_user_id: str) -> dict:
    expires = _now() + timedelta(minutes=10)
    with SessionLocal() as db:
        for _ in range(50):
            code = f"{_rng.randrange(0, 1_000_000):06d}"
            key = _digest(code)
            if db.get(PrtMobilePairingRow, key) is None:
                row = PrtMobilePairingRow(
                    code_hash=key,
                    desktop_device_id=desktop_device_id,
                    discord_user_id=discord_user_id,
                    expires_at=expires.isoformat(),
                )
                db.add(row)
                db.commit()
                return {
                    "code": code,
                    "pair_uri": f"pitmarkprt://pair?code={code}",
                    "expires_at": expires.isoformat(),
                    "expires_in_seconds": 600,
                }
    raise RuntimeError("Could not create pairing code.")


def consume(code: str, mobile_device_id: str) -> dict:
    clean = "".join(ch for ch in code if ch.isdigit())
    if len(clean) != 6:
        raise LookupError("Pairing code not found.")
    with SessionLocal() as db:
        row = db.get(PrtMobilePairingRow, _digest(clean))
        if row is None:
            raise LookupError("Pairing code not found.")
        if row.claimed_at:
            raise PermissionError("Pairing code already used.")
        expiry = datetime.fromisoformat(row.expires_at.replace("Z", "+00:00"))
        if expiry < _now():
            raise TimeoutError("Pairing code expired.")
        row.claimed_at = _now().isoformat()
        row.mobile_device_id = mobile_device_id
        db.commit()
        return {
            "desktop_device_id": row.desktop_device_id,
            "discord_user_id": row.discord_user_id,
        }
