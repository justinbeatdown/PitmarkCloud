from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.control_access import (
    ALL_PERMISSIONS,
    ROLE_DEFAULTS,
    create_user,
    current_access,
    delete_user,
    list_users,
    reset_user_password,
    update_user_access,
)

router = APIRouter()


class CreateControlUser(BaseModel):
    # Keep request parsing permissive enough that validation errors can be
    # returned as simple human-readable strings instead of FastAPI's list of
    # validation objects (which the Control Center previously rendered as
    # "[object Object]"). The actual constraints are enforced in the route.
    username: str = ""
    password: str = ""
    role: str = "viewer"
    display_name: str = ""


class UpdateControlUser(BaseModel):
    role: str | None = None
    permissions: list[str] | None = None
    active: bool | None = None
    display_name: str | None = None


class ResetPassword(BaseModel):
    password: str = ""


def _validate_username(username: str) -> None:
    length = len((username or "").strip())
    if length < 2 or length > 80:
        raise HTTPException(400, "Username must be between 2 and 80 characters.")


def _validate_password(password: str) -> None:
    length = len(password or "")
    if length < 12:
        raise HTTPException(400, "Password must be at least 12 characters.")
    if length > 200:
        raise HTTPException(400, "Password must be 200 characters or fewer.")


@router.get("/access/me")
def me(request: Request):
    return current_access(request)


@router.get("/access/roles")
def roles(request: Request):
    current_access(request)
    return {
        "roles": {k: v for k, v in ROLE_DEFAULTS.items() if k != "owner"},
        "permissions": ALL_PERMISSIONS,
    }


@router.get("/access/users")
def users(request: Request):
    return list_users(request)


@router.post("/access/users")
def add_user(req: CreateControlUser, request: Request):
    _validate_username(req.username)
    _validate_password(req.password)
    try:
        return create_user(
            request,
            username=req.username,
            password=req.password,
            role=req.role,
            display_name=req.display_name,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/access/users/{user_id}")
def change_user(user_id: int, req: UpdateControlUser, request: Request):
    try:
        return update_user_access(
            request,
            user_id=user_id,
            role=req.role,
            permissions=req.permissions,
            active=req.active,
            display_name=req.display_name,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/access/users/{user_id}/password")
def change_user_password(user_id: int, req: ResetPassword, request: Request):
    _validate_password(req.password)
    try:
        return reset_user_password(request, user_id=user_id, new_password=req.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/access/users/{user_id}")
def remove_user(user_id: int, request: Request):
    try:
        return delete_user(request, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
