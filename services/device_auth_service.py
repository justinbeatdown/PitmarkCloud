from __future__ import annotations

import hashlib
import hmac

from services import persistent_store
from utils.security import DEVICE_ID_RE

MIN_SECRET_LENGTH = 32
MAX_SECRET_LENGTH = 128


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def register(device_id: str, secret: str) -> dict:
    device_id = (device_id or "").strip()
    secret = (secret or "").strip()
    if not DEVICE_ID_RE.fullmatch(device_id):
        raise ValueError("Invalid device identifier.")
    if len(secret) < MIN_SECRET_LENGTH or len(secret) > MAX_SECRET_LENGTH:
        raise ValueError("Invalid device credential.")
    outcome = persistent_store.register_device_credential(device_id, _hash_secret(secret))
    if outcome == "conflict":
        raise PermissionError("This device identifier is already registered with a different credential.")
    return {"registered": True, "device_id": device_id, "existing": outcome == "existing"}


def authenticate(device_id: str, supplied_secret: str | None) -> bool:
    if not DEVICE_ID_RE.fullmatch((device_id or "").strip()):
        return False
    if not supplied_secret or len(supplied_secret) > MAX_SECRET_LENGTH:
        return False
    row = persistent_store.get_device_credential(device_id)
    if row is None or not row.secret_hash:
        return False
    ok = hmac.compare_digest(row.secret_hash, _hash_secret(supplied_secret))
    if ok:
        persistent_store.touch_device_credential(device_id)
    return ok
