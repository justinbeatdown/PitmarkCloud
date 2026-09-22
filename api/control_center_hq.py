from __future__ import annotations

from collections import Counter
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from services.control_auth import require_control_user
from services.database import SessionLocal, database_status
from services.founders_race import leaderboard
from services.master_checklist import bucket_for, list_items, update_item
from services.google_workspace_auth import (
    WorkspaceAuthorizationRequired,
    begin_authorization,
    complete_authorization,
    credential_source,
    workspace_credentials_configured,
)
from services.prt_applications import application_role_from_placement, list_applications
from services.prt_feedback import list_feedback, summary as feedback_summary
from services.prt_licensing_store import list_early_access_invites
from services.control_center import BlogDraft, OutreachContact, SocialPost
from utils.config import settings

router = APIRouter()


class WorkspaceOAuthComplete(BaseModel):
    callback_url: str = Field(min_length=20, max_length=8000)


class WorkUpdate(BaseModel):
    status: str | None = Field(default=None, min_length=2, max_length=40)
    priority: str | None = Field(default=None, min_length=1, max_length=24)
    next_action: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=12000)


def _auth(request: Request):
    return require_control_user(request, None)


def _guard(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "data": fn(), "error": None, "source": name}
    except Exception as exc:
        return {
            "ok": False,
            "data": None,
            "error": f"{type(exc).__name__}: {str(exc)[:600]}",
            "source": name,
        }


def _priority_rank(priority: str) -> int:
    value = (priority or "").strip().upper()
    if value == "P0":
        return 0
    if value == "P1":
        return 1
    if value == "P2":
        return 2
    if value == "P3":
        return 3
    if value in {"COMPLETE", "DONE"}:
        return 9
    return 5


def _bucket_rank(bucket: str) -> int:
    return {
        "blocked": 0,
        "active": 1,
        "waiting": 2,
        "monitoring": 3,
        "other": 4,
        "roadmap": 5,
        "completed": 9,
    }.get(bucket, 6)


def _sort_work(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            _bucket_rank(str(item.get("bucket") or bucket_for(item))),
            _priority_rank(str(item.get("priority") or "")),
            str(item.get("last_updated") or ""),
            int(item.get("row_number") or 0),
        ),
    )


def _work_view(snapshot: dict[str, Any], view: str) -> list[dict[str, Any]]:
    items = list(snapshot.get("items") or [])
    normalized = view.strip().lower()

    if normalized in {"active", "waiting", "monitoring", "blocked", "completed", "roadmap"}:
        selected = [item for item in items if str(item.get("bucket") or bucket_for(item)) == normalized]
    elif normalized == "desktop":
        selected = [
            item for item in items
            if item.get("desktop_required") and str(item.get("bucket") or bucket_for(item)) != "completed"
        ]
    elif normalized == "phone":
        selected = [
            item for item in items
            if item.get("phone_actionable") and str(item.get("bucket") or bucket_for(item)) != "completed"
        ]
    elif normalized == "today":
        selected = [
            item for item in items
            if str(item.get("bucket") or bucket_for(item)) not in {"completed", "roadmap"}
        ]
    elif normalized == "now":
        selected = [
            item for item in items
            if str(item.get("bucket") or bucket_for(item)) == "blocked"
            or str(item.get("priority") or "").strip().upper() in {"P0", "P1"}
            or str(item.get("bucket") or bucket_for(item)) == "active"
        ]
    else:
        raise ValueError(f"Unsupported work view: {view}")

    ordered = _sort_work(selected)
    if normalized in {"now", "today"}:
        return ordered[:60]
    return ordered


def _checklist_hq() -> dict[str, Any]:
    snapshot = list_items()
    attention = _work_view(snapshot, "now")[:10]
    waiting = _work_view(snapshot, "waiting")[:8]
    recently_completed = list(reversed(_work_view(snapshot, "completed")))[:8]
    return {
        "summary": snapshot.get("summary") or {},
        "attention": attention,
        "waiting": waiting,
        "recently_completed": recently_completed,
        "fetched_at": snapshot.get("fetched_at"),
        "stale": bool(snapshot.get("stale")),
        "error": snapshot.get("error"),
    }


def _prt_hq() -> dict[str, Any]:
    applications = list_applications(limit=200)
    invites = list_early_access_invites(limit=500)
    race = leaderboard()
    feedback = feedback_summary()
    app_counts = Counter(str(row.get("status") or "new").lower() for row in applications)
    invite_counts = Counter(str(row.get("status") or "unknown").lower() for row in invites)
    return {
        "applications": {
            "new": app_counts.get("new", 0),
            "accepted": app_counts.get("accepted", 0),
            "hold": app_counts.get("hold", 0),
            "total": len(applications),
        },
        "testers": {
            "total_invites": len(invites),
            "redeemed": invite_counts.get("redeemed", 0),
            "issued": invite_counts.get("issued", 0),
        },
        "founders_race": {
            "racers": len(race),
            "qualified": sum(int(row.get("qualified") or 0) for row in race),
            "pending": sum(int(row.get("pending") or 0) for row in race),
            "flagged": sum(int(row.get("flagged") or 0) for row in race),
        },
        "feedback": feedback,
    }


def _content_hq() -> dict[str, Any]:
    with SessionLocal() as db:
        posts = list(db.scalars(select(SocialPost).order_by(SocialPost.id.desc()).limit(500)).all())
        drafts = list(db.scalars(select(BlogDraft).order_by(BlogDraft.id.desc()).limit(300)).all())
    post_counts = Counter(str(row.status or "unknown").lower() for row in posts)
    draft_counts = Counter(str(row.status or "unknown").lower() for row in drafts)
    return {
        "autopilot": {
            "pending": post_counts.get("pending", 0),
            "approved": post_counts.get("approved", 0),
            "scheduled": post_counts.get("scheduled", 0),
            "published": post_counts.get("published", 0),
        },
        "editorial": {
            "drafts": draft_counts.get("draft", 0),
            "scheduled": draft_counts.get("scheduled", 0),
            "published": draft_counts.get("published", 0),
        },
    }


def _relationships_hq() -> dict[str, Any]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(OutreachContact).order_by(OutreachContact.id.desc()).limit(1000)).all())
    stages = Counter(str(row.stage or "unknown").lower() for row in rows)
    return {
        "total": len(rows),
        "stages": dict(stages),
        "waiting_follow_up": sum(1 for row in rows if row.next_follow_up),
    }


def _systems_hq() -> dict[str, Any]:
    db = database_status()
    return {
        "app_version": settings.app_version,
        "environment": settings.environment,
        "database": db,
    }


def _notifications_hq() -> dict[str, Any]:
    from services.notification_engine import list_notifications

    rows = list_notifications()
    unread = [row for row in rows if str(row.get("status") or "unread").lower() == "unread"]
    return {"unread": len(unread), "items": unread[:8]}


@router.get("/api/control/workspace/status")
def workspace_status(request: Request):
    _auth(request)
    configured = workspace_credentials_configured()
    connected = False
    error = None
    if configured:
        try:
            list_items(force=True)
            connected = True
        except Exception as exc:
            error = str(exc)[:600]
    return {
        "configured": configured,
        "connected": connected,
        "credential_source": credential_source(),
        "spreadsheet_id": "18k0Lnc4Dh8WsWssLDbOobE5lCXIQO1FjlAEKcHJ-UtI",
        "sheet_name": "Master Checklist",
        "error": error,
    }


@router.post("/api/control/workspace/oauth/start")
def workspace_oauth_start(request: Request):
    user = _auth(request)
    user_key = user.username if user else "admin"
    try:
        return begin_authorization(user_key)
    except WorkspaceAuthorizationRequired as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/api/control/workspace/oauth/complete")
def workspace_oauth_complete(payload: WorkspaceOAuthComplete, request: Request):
    user = _auth(request)
    user_key = user.username if user else "admin"
    try:
        complete_authorization(payload.callback_url, user_key)
        snapshot = list_items(force=True)
    except WorkspaceAuthorizationRequired as exc:
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "ok": True,
        "connected": True,
        "summary": snapshot.get("summary") or {},
        "fetched_at": snapshot.get("fetched_at"),
    }



@router.get("/api/control/intelligence/google/status")
def intelligence_google_status(request: Request):
    _auth(request)
    from services.google_business_intelligence_auth import configured as analytics_credentials_configured
    connected = analytics_credentials_configured()
    return {
        "configured": connected,
        "connected": connected,
        "scopes": ["GA4", "Search Console", "YouTube"],
    }


@router.post("/api/control/intelligence/google/oauth/start")
def intelligence_google_oauth_start(request: Request):
    user = _auth(request)
    user_key = user.username if user else "admin"
    from services.google_business_intelligence_auth import (
        AnalyticsAuthorizationRequired,
        begin_authorization as begin_analytics_authorization,
    )
    try:
        return begin_analytics_authorization(user_key)
    except AnalyticsAuthorizationRequired as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/api/control/intelligence/google/oauth/complete")
def intelligence_google_oauth_complete(payload: WorkspaceOAuthComplete, request: Request):
    user = _auth(request)
    user_key = user.username if user else "admin"
    from services.google_business_intelligence_auth import (
        AnalyticsAuthorizationRequired,
        complete_authorization as complete_analytics_authorization,
    )
    try:
        complete_analytics_authorization(payload.callback_url, user_key)
    except AnalyticsAuthorizationRequired as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "connected": True}


@router.get("/api/control/hq/overview")
def hq_overview(request: Request):
    _auth(request)
    return {
        "version": settings.app_version,
        "modules": {
            "work": _guard("master_checklist", _checklist_hq),
            "prt": _guard("prt", _prt_hq),
            "content": _guard("content", _content_hq),
            "relationships": _guard("relationships", _relationships_hq),
            "systems": _guard("systems", _systems_hq),
            "notifications": _guard("notifications", _notifications_hq),
        },
    }


@router.get("/api/control/work")
def work_list(request: Request, view: str = Query(default="now")):
    _auth(request)
    try:
        snapshot = list_items()
        items = _work_view(snapshot, view)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "view": view.strip().lower(),
        "source": snapshot.get("source"),
        "fetched_at": snapshot.get("fetched_at"),
        "stale": bool(snapshot.get("stale")),
        "error": snapshot.get("error"),
        "summary": snapshot.get("summary") or {},
        "items": items,
    }


@router.patch("/api/control/work/{row_number}")
def work_update(row_number: int, payload: WorkUpdate, request: Request):
    _auth(request)
    updates = payload.model_dump(exclude_unset=True)
    try:
        item = update_item(row_number, updates)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "item": item}


def _contains(query: str, *values: Any) -> bool:
    haystack = " ".join(str(value or "") for value in values).lower()
    return query in haystack


def _result(kind: str, title: str, subtitle: str, target_view: str, target_id: Any = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "target_view": target_view,
        "target_id": target_id,
    }


@router.get("/api/control/search")
def control_search(request: Request, q: str = Query(min_length=2, max_length=120)):
    _auth(request)
    query = " ".join(q.lower().split())
    groups: dict[str, list[dict[str, Any]]] = {
        "work": [],
        "applications": [],
        "testers": [],
        "founders_race": [],
        "relationships": [],
        "content": [],
    }

    try:
        snapshot = list_items()
        for item in snapshot.get("items") or []:
            if _contains(query, item.get("task"), item.get("area"), item.get("next_action"), item.get("notes"), item.get("status")):
                groups["work"].append(
                    _result(
                        "work",
                        str(item.get("task") or "Untitled checklist item"),
                        f"{item.get('area') or 'Work'} · {item.get('status') or 'Unknown'} · {item.get('priority') or 'No priority'}",
                        "work",
                        item.get("row_number"),
                    )
                )
    except Exception:
        pass

    try:
        for row in list_applications(limit=250):
            name = str(row.get("name") or row.get("full_name") or row.get("email") or "PRT applicant")
            role = application_role_from_placement(row.get("placement"))
            if _contains(query, name, row.get("email"), row.get("discord"), row.get("iracing_name"), role, row.get("status")):
                groups["applications"].append(
                    _result("application", name, f"{role} · {row.get('status') or 'new'}", "prt", row.get("id"))
                )
    except Exception:
        pass

    try:
        for row in list_early_access_invites(limit=500):
            title = str(row.get("tester_name") or row.get("name") or row.get("email") or row.get("code") or "PRT tester")
            if _contains(query, title, row.get("email"), row.get("code"), row.get("status"), row.get("tester_status")):
                groups["testers"].append(
                    _result("tester", title, f"{row.get('status') or 'unknown'} · {row.get('tester_status') or 'unknown'}", "prt", row.get("id"))
                )
    except Exception:
        pass

    try:
        for row in leaderboard():
            title = str(row.get("tester_name") or row.get("name") or row.get("email") or "Founder's Race participant")
            if _contains(query, title, row.get("referral_code"), row.get("email")):
                groups["founders_race"].append(
                    _result("founders_race", title, f"#{row.get('position') or '?'} · {row.get('qualified') or 0} qualified", "prt", row.get("tester_id"))
                )
    except Exception:
        pass

    try:
        with SessionLocal() as db:
            relationships = list(db.scalars(select(OutreachContact).order_by(OutreachContact.id.desc()).limit(500)).all())
            posts = list(db.scalars(select(SocialPost).order_by(SocialPost.id.desc()).limit(250)).all())
            drafts = list(db.scalars(select(BlogDraft).order_by(BlogDraft.id.desc()).limit(250)).all())
        for row in relationships:
            title = row.organization or row.name
            if _contains(query, row.name, row.organization, row.contact_type, row.stage, row.notes):
                groups["relationships"].append(
                    _result("relationship", title, f"{row.contact_type} · {row.stage}", "partnerships", row.id)
                )
        for row in posts:
            if _contains(query, row.title, row.body, row.platform, row.status, row.source):
                groups["content"].append(
                    _result("social_post", row.title or row.body[:80], f"{row.platform} · {row.status}", "content", row.id)
                )
        for row in drafts:
            if _contains(query, row.title, row.content_type, row.status):
                groups["content"].append(
                    _result("editorial", row.title, f"{row.content_type} · {row.status}", "content", row.id)
                )
    except Exception:
        pass

    for key, values in groups.items():
        groups[key] = values[:12]
    total = sum(len(values) for values in groups.values())
    return {"query": q, "total": total, "groups": groups}


@router.get("/api/control/intelligence/overview")
def intelligence_overview(request: Request, days: int = Query(default=30, ge=7, le=90)):
    _auth(request)
    from services.business_intelligence import overview as business_intelligence_overview
    return business_intelligence_overview(days)
