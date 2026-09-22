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


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(raw[:10], "%Y-%m-%d")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
            "top_products": [],
            "recent_orders": [],
            "error": "Shopify credentials are not configured.",
        }

    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = """
    query PitmarkBusinessIntelligenceOrders($query: String!) {
      orders(first: 100, sortKey: CREATED_AT, reverse: false, query: $query) {
        nodes {
          name
          createdAt
          displayFinancialStatus
          displayFulfillmentStatus
          currentTotalPriceSet { shopMoney { amount currencyCode } }
          lineItems(first: 50) {
            nodes {
              title
              quantity
              originalUnitPriceSet { shopMoney { amount currencyCode } }
              discountedTotalSet { shopMoney { amount currencyCode } }
            }
          }
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
        products: dict[str, dict[str, Any]] = {}
        recent_orders: list[dict[str, Any]] = []

        for row in valid:
            money = ((row.get("currentTotalPriceSet") or {}).get("shopMoney") or {})
            currency = str(money.get("currencyCode") or currency)
            day = str(row.get("createdAt") or "")[:10] or "unknown"
            bucket = buckets.setdefault(day, {"date": day, "orders": 0, "revenue": 0.0})
            bucket["orders"] += 1
            bucket["revenue"] = round(bucket["revenue"] + _money(money.get("amount")), 2)

            recent_orders.append({
                "name": row.get("name"),
                "created_at": row.get("createdAt"),
                "financial_status": row.get("displayFinancialStatus"),
                "fulfillment_status": row.get("displayFulfillmentStatus"),
                "amount": _money(money.get("amount")),
                "currency": money.get("currencyCode") or currency,
            })

            for line in ((row.get("lineItems") or {}).get("nodes") or []):
                title = str(line.get("title") or "Unknown product").strip()
                quantity = int(line.get("quantity") or 0)
                line_money = ((line.get("discountedTotalSet") or {}).get("shopMoney") or {})
                line_revenue = _money(line_money.get("amount"))
                product = products.setdefault(title, {
                    "title": title,
                    "quantity": 0,
                    "revenue": 0.0,
                    "orders": 0,
                    "currency": line_money.get("currencyCode") or currency,
                })
                product["quantity"] += quantity
                product["revenue"] = round(product["revenue"] + line_revenue, 2)
                product["orders"] += 1

        count = len(valid)
        return {
            "status": "live",
            "days": days,
            "revenue": round(revenue, 2),
            "orders": count,
            "average_order_value": round(revenue / count, 2) if count else 0.0,
            "currency": currency,
            "daily": sorted(buckets.values(), key=lambda row: row["date"]),
            "top_products": sorted(products.values(), key=lambda row: (row["revenue"], row["quantity"]), reverse=True)[:12],
            "recent_orders": sorted(recent_orders, key=lambda row: str(row.get("created_at") or ""), reverse=True)[:10],
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
            "top_products": [],
            "recent_orders": [],
            "error": str(exc)[:400],
        }


def _internal_growth() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
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

    overdue: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    warm: list[dict[str, Any]] = []
    warm_stages = {"replied", "warm", "interested", "call", "meeting", "partner", "collaboration", "active"}

    for row in relationships:
        stage = str(row.stage or "unknown").strip().lower()
        follow_up = _parse_dt(row.next_follow_up)
        updated = _parse_dt(row.updated_at)
        item = {
            "id": row.id,
            "name": row.name,
            "organization": row.organization,
            "contact_type": row.contact_type,
            "stage": row.stage,
            "next_follow_up": row.next_follow_up,
            "updated_at": row.updated_at.isoformat() if isinstance(row.updated_at, datetime) else row.updated_at,
        }
        if follow_up and follow_up < now:
            overdue.append(item)
        if updated and updated < now - timedelta(days=14) and stage not in {"closed", "declined", "dead", "complete", "completed"}:
            stale.append(item)
        if stage in warm_stages:
            warm.append(item)

    issued = invite_counts.get("issued", 0)
    redeemed = invite_counts.get("redeemed", 0)
    total_invites = len(invites)
    redemption_rate = round((redeemed / total_invites) * 100, 1) if total_invites else 0.0

    return {
        "prt": {
            "applications_total": len(applications),
            "applications_new": app_counts.get("new", 0),
            "applications_accepted": app_counts.get("accepted", 0),
            "applications_hold": app_counts.get("hold", 0),
            "testers_redeemed": redeemed,
            "testers_issued": issued,
            "testers_total_invites": total_invites,
            "redemption_rate": redemption_rate,
            "feedback_open": int(feedback.get("open") or feedback.get("total") or 0),
            "onboarding_bottleneck": issued,
        },
        "content": {
            "pending": post_counts.get("pending", 0),
            "scheduled": post_counts.get("scheduled", 0),
            "published": post_counts.get("published", 0),
            "editorial_drafts": draft_counts.get("draft", 0),
            "editorial_published": draft_counts.get("published", 0),
            "platforms": dict(Counter(str(row.platform or "unknown").lower() for row in posts)),
            "content_types": dict(Counter(str(row.content_type or "unknown").lower() for row in posts)),
        },
        "relationships": {
            "total": len(relationships),
            "waiting_follow_up": sum(1 for row in relationships if row.next_follow_up),
            "overdue_follow_up": len(overdue),
            "stale_open": len(stale),
            "warm": len(warm),
            "stages": dict(relationship_stages),
            "overdue_items": overdue[:12],
            "stale_items": stale[:12],
            "warm_items": warm[:12],
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
            "reason": "Shopify returned no qualifying orders in the current reporting window.",
            "action": "Prioritize traffic quality, product-page trust, offer clarity, and checkout friction before adding paid tools.",
        })
    elif orders > 0:
        top = (shopify.get("top_products") or [{}])[0]
        detail = ""
        if top.get("title"):
            detail = " Top product: %s ($%.2f)." % (top["title"], _money(top.get("revenue")))
        items.append({
            "priority": "medium",
            "type": "revenue",
            "title": "Protect what is already converting",
            "reason": "Shopify shows %s qualifying order(s) and $%,.2f in the current reporting window.%s" % (orders, revenue, detail),
            "action": "Identify the channel and content behind those orders before increasing spend.",
        })

    rel = growth.get("relationships") or {}
    overdue = int(rel.get("overdue_follow_up") or 0)
    if overdue:
        items.append({
            "priority": "high",
            "type": "relationships",
            "title": "Overdue relationship follow-ups need attention",
            "reason": "%s tracked relationship(s) are past their follow-up date." % overdue,
            "action": "Clear overdue warm follow-ups before launching another large cold-outreach wave.",
        })
    elif int(rel.get("waiting_follow_up") or 0) > 0:
        count = int(rel.get("waiting_follow_up") or 0)
        items.append({
            "priority": "medium",
            "type": "relationships",
            "title": "Warm relationships need follow-through",
            "reason": "%s relationship record(s) have a follow-up date." % count,
            "action": "Keep those conversations moving before adding more cold leads.",
        })

    stale = int(rel.get("stale_open") or 0)
    if stale >= 5:
        items.append({
            "priority": "medium",
            "type": "relationships",
            "title": "The outreach pipeline has stale open records",
            "reason": "%s open relationship(s) have not moved in at least 14 days." % stale,
            "action": "Close, revive, or reclassify stale records so the pipeline reflects reality.",
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
    if int(prt.get("onboarding_bottleneck") or 0) >= 3:
        count = int(prt.get("onboarding_bottleneck") or 0)
        items.append({
            "priority": "medium",
            "type": "prt",
            "title": "Accepted testers are not all redeeming access",
            "reason": "%s PRT invite(s) are still issued rather than redeemed." % count,
            "action": "Check onboarding friction and follow up with accepted testers who have not activated.",
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

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda item: priority_rank.get(item.get("priority", "medium"), 1))[:10]


def overview(days: int = 30) -> dict[str, Any]:
    safe_days = max(7, min(int(days), 90))
    shopify = _shopify_window(safe_days)
    growth = _internal_growth()
    return {
        "version": "2.0",
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
