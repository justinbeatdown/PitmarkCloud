from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import Boolean, DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services.control_auth import ControlUser, hash_password, user_from_request

ALL_PERMISSIONS = [
    "dashboard",
    "autopilot",
    "shield",
    "campaigns",
    "outreach",
    "mail",
    "blog",
    "directory",
    "analytics",
    "settings",
    "users",
]

ROLE_DEFAULTS = {
    "owner": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS,
    "marketing": ["dashboard", "autopilot", "campaigns", "outreach", "mail", "blog", "directory", "analytics"],
    "support": ["dashboard", "shield", "outreach", "mail", "directory", "analytics"],
    "viewer": ["dashboard", "analytics"],
}


def utcnow():
    return datetime.now(timezone.utc)


class ControlAccessProfile(Base):
    __tablename__ = "control_center_access_profiles"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[str] = mapped_column(String(40), default="viewer", index=True)
    permissions_json: Mapped[str] = mapped_column(Text, default="[]")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@dataclass
class AccessUser:
    id: int
    username: str
    display_name: str
    role: str
    permissions: set[str]
    active: bool


def _permissions(role: str, raw: str | None) -> set[str]:
    role = (role or "viewer").lower()
    try:
        custom = {str(x) for x in json.loads(raw or "[]") if str(x) in ALL_PERMISSIONS}
    except Exception:
        custom = set()
    return custom or set(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["viewer"]))


def _owner_id(db) -> int | None:
    return db.scalar(select(ControlUser.id).order_by(ControlUser.id.asc()).limit(1))


def access_for_user_id(user_id: int) -> AccessUser | None:
    with SessionLocal() as db:
        user = db.get(ControlUser, user_id)
        if not user:
            return None
        profile = db.get(ControlAccessProfile, user.id)
        owner_id = _owner_id(db)

        if profile is None:
            role = "owner" if user.id == owner_id else "viewer"
            permissions = set(ROLE_DEFAULTS[role])
            return AccessUser(user.id, user.username, user.username, role, permissions, True)

        role = "owner" if user.id == owner_id else (profile.role or "viewer").lower()
        permissions = set(ALL_PERMISSIONS) if role == "owner" else _permissions(role, profile.permissions_json)
        return AccessUser(
            user.id,
            user.username,
            profile.display_name or user.username,
            role,
            permissions,
            bool(profile.active),
        )


def access_from_request(request: Request) -> AccessUser | None:
    auth_user = user_from_request(request)
    return access_for_user_id(auth_user.id) if auth_user else None


def require_permission(request: Request, permission: str) -> AccessUser:
    access = access_from_request(request)
    if not access or not access.active:
        raise HTTPException(status_code=401, detail="Control Center authentication required.")
    if access.role not in {"owner", "admin"} and permission not in access.permissions:
        raise HTTPException(status_code=403, detail=f"Your Control Center role does not include {permission} access.")
    return access


def serialize_access(access: AccessUser) -> dict:
    return {
        "id": access.id,
        "username": access.username,
        "display_name": access.display_name,
        "role": access.role,
        "permissions": sorted(access.permissions),
        "active": access.active,
        "is_owner": access.role == "owner",
    }


def current_access(request: Request) -> dict:
    access = access_from_request(request)
    if not access:
        raise HTTPException(status_code=401, detail="Control Center authentication required.")
    return serialize_access(access)


def list_users(request: Request) -> list[dict]:
    require_permission(request, "users")
    with SessionLocal() as db:
        users = list(db.scalars(select(ControlUser).order_by(ControlUser.id.asc())).all())
    out = []
    for user in users:
        access = access_for_user_id(user.id)
        if access:
            out.append(serialize_access(access))
    return out


def create_user(request: Request, *, username: str, password: str, role: str, display_name: str = "") -> dict:
    actor = require_permission(request, "users")
    if actor.role not in {"owner", "admin"}:
        raise HTTPException(403, "Only owners/admins can create Control Center users.")

    clean_username = (username or "").strip().lower()
    clean_role = (role or "viewer").strip().lower()
    if not clean_username or len(clean_username) > 80:
        raise ValueError("Enter a valid username.")
    if clean_role not in ROLE_DEFAULTS or clean_role == "owner":
        raise ValueError("New users can be admin, marketing, support, or viewer.")

    salt, password_hash = hash_password(password)
    with SessionLocal() as db:
        if db.scalar(select(ControlUser.id).where(ControlUser.username == clean_username)):
            raise ValueError("That username already exists.")
        user = ControlUser(
            username=clean_username,
            password_salt=salt,
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        profile = ControlAccessProfile(
            user_id=user.id,
            role=clean_role,
            permissions_json=json.dumps(ROLE_DEFAULTS[clean_role]),
            display_name=(display_name or clean_username).strip()[:120],
            active=True,
        )
        db.add(profile)
        db.commit()
        user_id = user.id
    return serialize_access(access_for_user_id(user_id))


def update_user_access(
    request: Request,
    *,
    user_id: int,
    role: str | None = None,
    permissions: list[str] | None = None,
    active: bool | None = None,
    display_name: str | None = None,
) -> dict:
    require_permission(request, "users")
    target = access_for_user_id(user_id)
    if not target:
        raise ValueError("Control Center user not found.")
    if target.role == "owner":
        raise ValueError("The Control Center owner account cannot be demoted or disabled.")

    clean_role = (role or target.role).strip().lower()
    if clean_role not in ROLE_DEFAULTS or clean_role == "owner":
        raise ValueError("Role must be admin, marketing, support, or viewer.")
    clean_permissions = sorted({
        p for p in (permissions if permissions is not None else ROLE_DEFAULTS[clean_role])
        if p in ALL_PERMISSIONS and p != "users"
    })
    if clean_role == "admin":
        clean_permissions = list(ALL_PERMISSIONS)

    with SessionLocal() as db:
        profile = db.get(ControlAccessProfile, user_id)
        if profile is None:
            profile = ControlAccessProfile(user_id=user_id)
            db.add(profile)
        profile.role = clean_role
        profile.permissions_json = json.dumps(clean_permissions)
        if active is not None:
            profile.active = bool(active)
        if display_name is not None:
            profile.display_name = display_name.strip()[:120]
        profile.updated_at = utcnow()

        user = db.get(ControlUser, user_id)
        if user:
            user.session_version += 1
            user.updated_at = utcnow()
        db.commit()
    return serialize_access(access_for_user_id(user_id))


def reset_user_password(request: Request, *, user_id: int, new_password: str) -> dict:
    require_permission(request, "users")
    target = access_for_user_id(user_id)
    if not target:
        raise ValueError("Control Center user not found.")
    salt, password_hash = hash_password(new_password)
    with SessionLocal() as db:
        user = db.get(ControlUser, user_id)
        user.password_salt = salt
        user.password_hash = password_hash
        user.session_version += 1
        user.updated_at = utcnow()
        db.commit()
    return {"ok": True, "user_id": user_id}


def delete_user(request: Request, *, user_id: int) -> dict:
    actor = require_permission(request, "users")
    target = access_for_user_id(user_id)
    if not target:
        return {"ok": True, "deleted_id": user_id}
    if target.role == "owner":
        raise ValueError("The Control Center owner account cannot be deleted.")
    if actor.id == user_id:
        raise ValueError("You cannot delete the account you are currently using.")

    with SessionLocal() as db:
        profile = db.get(ControlAccessProfile, user_id)
        user = db.get(ControlUser, user_id)
        if profile:
            db.delete(profile)
        if user:
            db.delete(user)
        db.commit()
    return {"ok": True, "deleted_id": user_id}


# API-level RBAC for non-owner Control Center accounts.
# Unknown /api/control routes default to dashboard-level access so new features do
# not accidentally become public, while explicit workspaces are mapped below.
PATH_PERMISSIONS = (
    ("/api/control/access", "users"),
    ("/api/control/prt-analytics", "analytics"),
    ("/api/control/autopilot", "autopilot"),
    ("/api/control/social", "autopilot"),
    ("/api/control/shield", "shield"),
    ("/api/control/campaign", "campaigns"),
    ("/api/control/rookie", "campaigns"),
    ("/api/control/community", "campaigns"),
    ("/api/control/outreach", "outreach"),
    ("/api/control/email", "mail"),
    ("/api/control/blog", "blog"),
    ("/api/control/content", "autopilot"),
    ("/api/control/planner", "autopilot"),
    ("/api/control/directory", "directory"),
    ("/api/control/autonomy", "settings"),
    ("/api/control/settings", "settings"),
)


def permission_for_path(path: str) -> str | None:
    if not path.startswith("/api/control"):
        return None
    if path.startswith("/api/control/auth"):
        return None
    if path in {"/api/control/access/me", "/api/control/access/roles"}:
        return None
    for prefix, permission in PATH_PERMISSIONS:
        if path.startswith(prefix):
            return permission
    return "dashboard"
