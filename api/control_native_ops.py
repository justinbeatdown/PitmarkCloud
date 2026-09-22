from __future__ import annotations

from fastapi import APIRouter, Query, Request

from services.control_auth import require_control_user

router = APIRouter(prefix="/api/control/native-ops", tags=["control-native-ops"])


def _auth(request: Request):
    return require_control_user(request, None)


@router.get("/analytics")
def analytics(request: Request, days: int = Query(default=30, ge=7, le=90), force: bool = False):
    _auth(request)
    from services.native_analytics_suite import analytics_overview

    return analytics_overview(days, force=force)


@router.get("/social")
def social(request: Request, days: int = Query(default=30, ge=7, le=90), force: bool = False):
    _auth(request)
    from services.native_analytics_suite import social_desk

    return social_desk(days, force=force)


@router.post("/refresh")
def refresh(request: Request):
    _auth(request)
    from services.native_analytics_suite import clear_cache

    clear_cache()
    return {"ok": True, "cleared": True}
