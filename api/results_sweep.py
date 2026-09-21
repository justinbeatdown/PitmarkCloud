from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from services.control_auth import require_control_user
from services import results_sweep

router = APIRouter()
public_router = APIRouter()


def _auth(request: Request, key: str | None):
    return require_control_user(request, key)


@router.get("/status")
def status(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    return {
        "latest_run": results_sweep.latest_run(),
        "uncovered": results_sweep.list_items(limit=40, status="uncovered"),
        "needs_review": results_sweep.list_items(limit=40, status="needs_review"),
        "recent": results_sweep.list_items(limit=60),
    }


@router.get("/items")
def items(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    _auth(request, x_pitmark_admin_key)
    return {"items": results_sweep.list_items(limit=limit, status=status)}


@router.post("/run")
def run(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    return results_sweep.run_sweep(force=True)


@public_router.get("/image/{token}")
def public_image(token: str):
    media = results_sweep.resolve_media(token)
    if media is None:
        return Response(status_code=404)
    return Response(
        content=media["data"],
        media_type=media["media_type"],
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )
