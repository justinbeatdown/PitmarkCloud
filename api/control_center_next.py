"""Control Center 2.0: owner-first read model, without touching publishing authority."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, or_

from services.control_auth import require_control_user
from services.control_center import BlogDraft, OutreachContact, ShopifyPublishRecord, SocialPost, serialize
from services.database import SessionLocal
from services.persistent_store import get_runtime_state, set_runtime_state

router = APIRouter()
MAX_EVENTS = 60
MAX_ACTIONS = 45
CLOSED_STAGES = {"closed", "declined", "inactive", "published", "alumni", "complete", "completed"}
ATTENTION_POST_STATES = {"failed", "error", "publish_failed", "needs_review", "blocked"}
ACTIVITY_POST_STATES = {"published"}
ACTIVITY_ARTICLE_STATES = {"published"}


def _now():
    return datetime.now(timezone.utc)


def _as_datetime(value):
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def _iso(value):
    value = _as_datetime(value)
    return value.isoformat() if value else None


def _view(user):
    # A signed authenticated Control Center user owns this read state.
    return "control_hq_v2_user_%s" % user.id


def _read_state(user):
    try:
        data = json.loads(get_runtime_state(_view(user)) or "{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def _safe_str(value, limit=200):
    return " ".join(str(value or "").split())[:limit]


def _event(key, kind, title, at, target, detail="", source="Pitmark Cloud"):
    return {"id": key, "kind": kind, "title": _safe_str(title), "at": _iso(at),
            "target": target, "detail": _safe_str(detail, 260), "source": source}


def _action(key, kind, title, target, detail="", priority="action", at=None):
    return {"id": key, "kind": kind, "title": _safe_str(title), "detail": _safe_str(detail, 260),
            "priority": priority, "target": target, "at": _iso(at), "source": "Pitmark Cloud"}


def _snapshot(since):
    """One bounded local DB read. External providers must not block the HQ first paint."""
    events, actions = [], []
    with SessionLocal() as db:
        social_total = db.scalar(select(func.count(SocialPost.id))) or 0
        posts = db.scalars(select(SocialPost).order_by(SocialPost.updated_at.desc(), SocialPost.id.desc()).limit(100)).all()
        articles = db.scalars(select(ShopifyPublishRecord).order_by(ShopifyPublishRecord.created_at.desc()).limit(70)).all()
        relationships = db.scalars(select(OutreachContact).order_by(OutreachContact.updated_at.desc(), OutreachContact.id.desc()).limit(250)).all()
        pending_posts = db.scalar(select(func.count(SocialPost.id)).where(SocialPost.status == "pending")) or 0
        scheduled_posts = db.scalar(select(func.count(SocialPost.id)).where(SocialPost.status == "scheduled")) or 0
        failed_posts = db.scalar(select(func.count(SocialPost.id)).where(SocialPost.status.in_(ATTENTION_POST_STATES))) or 0
        published_articles = db.scalar(select(func.count(ShopifyPublishRecord.id)).where(ShopifyPublishRecord.status == "published")) or 0
        relationship_count = db.scalar(select(func.count(OutreachContact.id))) or 0

        for post in posts:
            status = str(post.status or "").lower()
            stamp = _as_datetime(post.updated_at)
            if status in ACTIVITY_POST_STATES and stamp and stamp >= since:
                events.append(_event("post:%s" % post.id, "content", post.title or "Social post published",
                                     stamp, "#content", "%s · recorded as published locally" % post.platform,
                                     "Pitmark publishing record"))
            if status in ATTENTION_POST_STATES:
                actions.append(_action("post:%s" % post.id, "publishing", post.title or "Publishing needs review",
                                       "#content", "%s · %s. Reconcile provider status before retrying." % (post.platform, post.status),
                                       "critical", stamp))
        for article in articles:
            stamp = _as_datetime(article.created_at)
            if str(article.status or "").lower() in ACTIVITY_ARTICLE_STATES and stamp and stamp >= since:
                # A durable Shopify article URL is stronger proof than a local draft status.
                target = article.url if str(article.url or "").startswith("https://") else "#content"
                events.append(_event("article:%s" % article.id, "article", article.title, stamp, target,
                                     "Shopify publication record", "Shopify publish record"))
        for person in relationships:
            stamp = _as_datetime(person.updated_at)
            title = person.organization or person.name or "Relationship"
            if stamp and stamp >= since and str(person.stage or "").lower() not in CLOSED_STAGES:
                events.append(_event("relationship:%s" % person.id, "relationship", title, stamp,
                                     "#relationships", "Relationship updated · %s" % person.stage,
                                     "Pitmark relationships"))
            follow = _as_datetime(person.next_follow_up)
            if follow and follow <= _now() and str(person.stage or "").lower() not in CLOSED_STAGES:
                actions.append(_action("followup:%s" % person.id, "relationship", "Follow up · %s" % title,
                                       "#relationships", "Due %s · %s" % (follow.strftime("%b %d"), person.stage),
                                       "action", follow))

    if pending_posts:
        actions.append(_action("content-approvals", "approval", "%s social approvals pending" % pending_posts,
                               "#content", "Review the existing publishing queue; no automatic approval.",
                               "action", _now()))
    events.sort(key=lambda x: x["at"] or "", reverse=True)
    rank = {"critical": 0, "action": 1, "opportunity": 2}
    actions.sort(key=lambda x: (rank.get(x["priority"], 9), x["at"] or ""), reverse=False)
    # Do not silently claim that the bounded preview is a total.
    return {"events": events[:MAX_EVENTS], "actions": actions[:MAX_ACTIONS],
            "metrics": {"posts_total": social_total, "pending_posts": pending_posts,
                        "scheduled_posts": scheduled_posts, "failed_posts": failed_posts,
                        "published_articles": published_articles, "relationships": relationship_count},
            "limits": {"events": MAX_EVENTS, "actions": MAX_ACTIONS,
                       "preview_may_be_incomplete": len(posts) == 100 or len(relationships) == 250}}


@router.get("/api/control/hq/v2")
def owner_hq(request: Request):
    user = require_control_user(request, None)
    if user is None:
        raise HTTPException(401, "A signed-in Control Center user is required.")
    now = _now()
    state_error = None
    try:
        state = _read_state(user)
    except Exception:
        state = {}
        state_error = "Visit history unavailable"
    prior = _as_datetime(state.get("last_visit"))
    # Bound the feed to 7 days on first use, and 30 days for long absences.
    since = max(now - timedelta(days=30), min(prior, now)) if prior else now - timedelta(days=7)
    result = {"generated_at": now.isoformat(), "since": since.isoformat(),
              "since_label": "Since your last visit" if prior else "Last 7 days",
              "state_error": state_error, "source": "Pitmark Cloud database"}
    try:
        result.update(_snapshot(since))
        result["status"] = "live"
    except Exception:
        # Don't leak SQL error strings or transform unknown counts into zeros.
        result.update({"events": [], "actions": [], "metrics": None,
                       "limits": {}, "status": "unavailable", "source_error": "Internal operations data unavailable"})
    return result


@router.post("/api/control/hq/v2/visit")
def record_visit(request: Request):
    user = require_control_user(request, None)
    if user is None:
        raise HTTPException(401, "A signed-in Control Center user is required.")
    now = _now().isoformat()
    state = _read_state(user)
    state["last_visit"] = now
    set_runtime_state(_view(user), json.dumps(state))
    return {"ok": True, "last_visit": now}


@router.get("/api/control/hq/v2/records/{kind}")
def owner_records(
    kind: str,
    request: Request,
    status: str = "",
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=35, ge=1, le=75),
    offset: int = Query(default=0, ge=0, le=10000),
):
    """Bounded, queryable data for native workspaces; no whole-table frontend fetch."""
    user = require_control_user(request, None)
    if user is None:
        raise HTTPException(401, "A signed-in owner is required.")
    models = {"posts": SocialPost, "relationships": OutreachContact, "editorial": BlogDraft}
    model = models.get(kind)
    if model is None:
        raise HTTPException(404, "Unknown operating area.")
    conditions = []
    status = (status or "").strip().lower()
    if status:
        if kind == "posts" and status == "attention":
            conditions.append(SocialPost.status.in_(ATTENTION_POST_STATES))
        else:
            conditions.append(model.status == status if kind != "relationships" else model.stage == status)
    if q.strip():
        term = "%" + q.strip().replace("%", r"\%").replace("_", r"\_") + "%"
        if kind == "posts":
            conditions.append(or_(SocialPost.title.ilike(term), SocialPost.body.ilike(term), SocialPost.platform.ilike(term)))
        elif kind == "relationships":
            conditions.append(or_(OutreachContact.name.ilike(term), OutreachContact.organization.ilike(term)))
        else:
            conditions.append(BlogDraft.title.ilike(term))
    with SessionLocal() as db:
        total = int(db.scalar(select(func.count(model.id)).where(*conditions)) or 0)
        stmt = select(model).where(*conditions).order_by(model.id.desc()).offset(offset).limit(limit)
        rows = list(db.scalars(stmt).all())
        return {
            "items": [serialize(row) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
            "source": "pitmark_cloud",
            "generated_at": _now().isoformat(),
        }
