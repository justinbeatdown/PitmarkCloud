from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from services.control_center import BlogDraft, OutreachContact, SocialPost
from services.database import SessionLocal
from services.prt_applications import list_applications
from services.prt_feedback import summary as feedback_summary
from services.prt_licensing_store import list_early_access_invites
from services.shopify_service import configured as shopify_configured, graphql


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _shopify_window(days: int = 30) -> dict[str, Any]:
    if not shopify_configured():
        return {
            "status": "not_configured",
            "days": days,
            "revenue": 0.0,
            "orders": 0,
            "average_order_value": 0.0,
            "currency": "USD",
            "daily": [],
            "error": "Shopify credentials are not configured.",
        }

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = """
    query PitmarkBusinessIntelligenceOrders($query: String!) {
      orders(first: 100, sortKey: CREATED_AT, reverse: false, query: $query) {
        nodes {
          createdAt
          displayFinancialStatus
          currentTotalPriceSet { shopMoney { amount currencyCode } }
        }
        pageInfo { hasNextPage }
      }
    }
    """
    try:
        data = graphql(query, {"query": "created_at:>=" + since})
        nodes = list(((data.get("orders") or {}).get("nodes") or []))
        valid = [
            row for row in nodes
            if str(row.get("displayFinancialStatus") or "").upper() not in {"VOIDED", "REFUNDED"}
        ]
        revenue = sum(
            _money((((row.get("currentTotalPriceSet") or {}).get("shopMoney") or {}).get("amount")))
            for row in valid
        )
        currency = "USD"
        buckets: dict[str, dict[str, Any]] = {}
        for row in valid:
            money = ((row.get("currentTotalPriceSet") or {}).get("shopMoney") or {})
            currency = str(money.get("currencyCode") or currency)
            day = str(row.get("createdAt") or "")[:10] or "unknown"
            bucket = buckets.setdefault(day, {"date": day, "orders": 0, "revenue": 0.0})
            bucket["orders"] += 1
            bucket["revenue"] = round(bucket["revenue"] + _money(money.get("amount")), 2)
        count = len(valid)
        return {
            "status": "live",
            "days": days,
            "revenue": round(revenue, 2),
            "orders": count,
            "average_order_value": round(revenue / count, 2) if count else 0.0,
            "currency": currency,
            "daily": sorted(buckets.values(), key=lambda row: row["date"]),
            "has_more": bool((data.get("orders") or {}).get("pageInfo", {}).get("hasNextPage")),
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "days": days,
            "revenue": 0.0,
            "orders": 0,
            "average_order_value": 0.0,
            "currency": "USD",
            "daily": [],
            "error": str(exc)[:400],
        }


def _internal_growth() -> dict[str, Any]:
    applications = list_applications(limit=500)
    invites = list_early_access_invites(limit=1000)
    feedback = feedback_summary()
    app_counts = Counter(str(row.get("status") or "new").lower() for row in applications)
    invite_counts = Counter(str(row.get("status") or "unknown").lower() for row in invites)

    with SessionLocal() as db:
        posts = list(db.scalars(select(SocialPost).order_by(SocialPost.id.desc()).limit(1000)).all())
        drafts = list(db.scalars(select(BlogDraft).order_by(BlogDraft.id.desc()).limit(500)).all())
        relationships = list(db.scalars(select(OutreachContact).order_by(OutreachContact.id.desc()).limit(1500)).all())

    post_counts = Counter(str(row.status or "unknown").lower() for row in posts)
    draft_counts = Counter(str(row.status or "unknown").lower() for row in drafts)
    relationship_stages = Counter(str(row.stage or "unknown").lower() for row in relationships)

    return {
        "prt": {
            "applications_total": len(applications),
            "applications_new": app_counts.get("new", 0),
            "applications_accepted": app_counts.get("accepted", 0),
            "testers_redeemed": invite_counts.get("redeemed", 0),
            "testers_issued": invite_counts.get("issued", 0),
            "feedback_open": int(feedback.get("open") or feedback.get("total") or 0),
        },
        "content": {
            "pending": post_counts.get("pending", 0),
            "scheduled": post_counts.get("scheduled", 0),
            "published": post_counts.get("published", 0),
            "editorial_drafts": draft_counts.get("draft", 0),
            "editorial_published": draft_counts.get("published", 0),
        },
        "relationships": {
            "total": len(relationships),
            "waiting_follow_up": sum(1 for row in relationships if row.next_follow_up),
            "stages": dict(relationship_stages),
        },
    }


def _recommendations(shopify: dict[str, Any], growth: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    revenue = _money(shopify.get("revenue"))
    orders = int(shopify.get("orders") or 0)

    if shopify.get("status") == "live" and orders == 0:
        items.append({
            "priority": "high",
            "type": "revenue",
            "title": "First-sale conversion remains the top commerce problem",
            "reason": "Shopify returned no qualifying orders in the current 30-day window.",
            "action": "Prioritize traffic quality, product-page trust, offer clarity, and checkout friction before adding paid tools.",
        })
    elif orders > 0:
        items.append({
            "priority": "medium",
            "type": "revenue",
            "title": "Protect what is already converting",
            "reason": "Shopify shows %s qualifying order(s) and $%,.2f in the current 30-day window." % (orders, revenue),
            "action": "Identify the products and channels behind those orders before increasing spend.",
        })

    rel = growth.get("relationships") or {}
    if int(rel.get("waiting_follow_up") or 0) > 0:
        count = int(rel.get("waiting_follow_up") or 0)
        items.append({
            "priority": "high",
            "type": "relationships",
            "title": "Warm relationships need follow-through",
            "reason": "%s relationship record(s) have a follow-up date." % count,
            "action": "Clear warm follow-ups before launching another large cold-outreach wave.",
        })

    prt = growth.get("prt") or {}
    if int(prt.get("applications_new") or 0) > 0:
        count = int(prt.get("applications_new") or 0)
        items.append({
            "priority": "high",
            "type": "prt",
            "title": "PRT demand is active",
            "reason": "%s new application(s) are waiting." % count,
            "action": "Process applicants quickly and capture which outreach source generated them.",
        })

    content = growth.get("content") or {}
    if int(content.get("pending") or 0) > 8:
        count = int(content.get("pending") or 0)
        items.append({
            "priority": "medium",
            "type": "content",
            "title": "Content queue is getting heavy",
            "reason": "%s generated post(s) are pending." % count,
            "action": "Publish fewer, better pieces and retire low-value drafts instead of increasing posting volume.",
        })

    return items[:8]


def overview(days: int = 30) -> dict[str, Any]:
    safe_days = max(7, min(int(days), 90))
    shopify = _shopify_window(safe_days)
    growth = _internal_growth()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": safe_days,
        "sources": {
            "shopify": {"status": shopify.get("status"), "live": shopify.get("status") == "live", "error": shopify.get("error")},
            "pitmark_internal": {"status": "live", "live": True, "error": None},
            "meta_ads": {"status": "planned", "live": False, "error": None},
            "ga4": {"status": "planned", "live": False, "error": None},
            "search_console": {"status": "planned", "live": False, "error": None},
            "youtube": {"status": "planned", "live": False, "error": None},
            "tiktok": {"status": "planned", "live": False, "error": None},
        },
        "commerce": shopify,
        "growth": growth,
        "recommendations": _recommendations(shopify, growth),
    }
