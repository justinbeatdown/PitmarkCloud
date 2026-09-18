from __future__ import annotations

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from services.control_auth import require_control_user
from services.astra_director import director_state, recent_runs, run_director

router = APIRouter()


class DirectorRunRequest(BaseModel):
    request: str = Field(default="", max_length=6000)
    mode: str | None = Field(default=None, max_length=30)


def _auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


@router.get("/status")
def director_status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    try:
        return director_state()
    except Exception as exc:
        raise HTTPException(503, str(exc)[:500]) from exc


@router.post("/run")
def director_run(payload: DirectorRunRequest, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    try:
        return run_director(payload.request, mode=payload.mode)
    except httpx.HTTPStatusError as exc:
        detail = "Astra API request failed."
        try:
            detail = exc.response.json().get("error", {}).get("message") or detail
        except Exception:
            pass
        raise HTTPException(502, detail[:700]) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)[:700]) from exc


@router.get("/history")
def director_history(request: Request, limit: int = 10, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    return {"items": recent_runs(limit)}
