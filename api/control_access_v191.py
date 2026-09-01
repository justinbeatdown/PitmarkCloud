from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=12, max_length=200)
    role: str = "viewer"
    display_name: str = ""


class UpdateControlUser(BaseModel):
    role: str | None = None
    permissions: list[str] | None = None
    active: bool | None = None
    display_name: str | None = None


class ResetPassword(BaseModel):
    password: str = Field(min_length=12, max_length=200)


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
