from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select

from services.control_center import BlogDraft, OutreachContact, SocialPost
from services.database import SessionLocal
from services.prt_applications import list_applications
from services.prt_feedback import summary as feedback_summary
from services.prt_licensing_store import list_early_access_invites
from services.shopify_service import configured as shopify_configured, graphql
from services.google_business_intelligence_auth import configured as google_bi_configured, authorization_headers
from utils.config import settings


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
    query PitmarkBusinessIntelligenceOrders($query: String!, $after: String) {
      orders(first: 100, after: $after, sortKey: CREATED_AT, reverse: false, query: $query) {
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
        pageInfo { hasNextPage endCursor }
      }
    }
    """
    try:
        nodes: list[dict[str, Any]] = []
        after: str | None = None
        has_more = False
        for _ in range(20):
            data = graphql(query, {"query": "created_at:>=" + since, "after": after})
            orders = data.get("orders") or {}
            nodes.extend(list(orders.get("nodes") or []))
            page_info = orders.get("pageInfo") or {}
            has_more = bool(page_info.get("hasNextPage"))
            after = str(page_info.get("endCursor") or "").strip() or None
            if not has_more or not after:
                break
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
            "has_more": has_more,
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



def _meta_snapshot(days: int = 30) -> dict[str, Any]:
    token = (settings.meta_system_user_access_token or settings.meta_page_access_token or "").strip()
    page_id = (settings.meta_page_id or "").strip()
    ig_id = (settings.meta_instagram_account_id or "").strip()
    if not token or not page_id:
        return {
            "status": "not_configured",
            "facebook": {},
            "instagram": {},
            "ads": {},
            "error": "Meta page credentials are not configured.",
        }

    base = "https://graph.facebook.com/%s" % settings.meta_graph_version
    facebook: dict[str, Any] = {}
    instagram: dict[str, Any] = {}
    ads: dict[str, Any] = {}
    errors: list[str] = []
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    until = int(datetime.now(timezone.utc).timestamp())

    with httpx.Client(timeout=20.0) as client:
        try:
            page = client.get(
                base + "/" + page_id,
                params={
                    "fields": "id,name,fan_count,followers_count,link",
                    "access_token": token,
                },
            )
            page.raise_for_status()
            facebook["page"] = page.json()
        except Exception as exc:
            errors.append("Facebook page: %s" % str(exc)[:180])

        try:
            posts = client.get(
                base + "/" + page_id + "/posts",
                params={
                    "fields": "id,message,created_time,permalink_url,shares,likes.summary(true),comments.summary(true)",
                    "limit": 25,
                    "since": since,
                    "until": until,
                    "access_token": token,
                },
            )
            posts.raise_for_status()
            rows = list((posts.json() or {}).get("data") or [])
            facebook["posts"] = rows
            facebook["posts_count"] = len(rows)
            facebook["engagement_actions"] = sum(
                int(((row.get("likes") or {}).get("summary") or {}).get("total_count") or 0)
                + int(((row.get("comments") or {}).get("summary") or {}).get("total_count") or 0)
                + int((row.get("shares") or {}).get("count") or 0)
                for row in rows
            )
        except Exception as exc:
            errors.append("Facebook posts: %s" % str(exc)[:180])

        try:
            ad_accounts = client.get(
                base + "/me/adaccounts",
                params={
                    "fields": "id,name,account_status,currency",
                    "limit": 50,
                    "access_token": token,
                },
            )
            ad_accounts.raise_for_status()
            accounts = list((ad_accounts.json() or {}).get("data") or [])
            selected_ad = next(
                (row for row in accounts if "pitmark" in str(row.get("name") or "").lower()),
                None,
            )
            ads["accounts"] = accounts
            ads["selected_account"] = selected_ad
            if selected_ad and selected_ad.get("id"):
                account_id = selected_ad["id"]
                time_range = '{"since":"%s","until":"%s"}' % (
                    (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat(),
                    datetime.now(timezone.utc).date().isoformat(),
                )
                insights = client.get(
                    base + "/" + account_id + "/insights",
                    params={
                        "fields": "spend,impressions,reach,clicks,ctr,cpc,actions",
                        "time_range": time_range,
                        "access_token": token,
                    },
                )
                insights.raise_for_status()
                rows = list((insights.json() or {}).get("data") or [])
                ads["summary"] = rows[0] if rows else {}
                campaigns = client.get(
                    base + "/" + account_id + "/campaigns",
                    params={
                        "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,start_time,stop_time",
                        "limit": 50,
                        "access_token": token,
                    },
                )
                campaigns.raise_for_status()
                ads["campaigns"] = list((campaigns.json() or {}).get("data") or [])
        except Exception as exc:
            errors.append("Meta Ads: %s" % str(exc)[:180])

        if ig_id:
            try:
                profile = client.get(
                    base + "/" + ig_id,
                    params={
                        "fields": "id,username,followers_count,media_count",
                        "access_token": token,
                    },
                )
                profile.raise_for_status()
                instagram["profile"] = profile.json()
            except Exception as exc:
                errors.append("Instagram profile: %s" % str(exc)[:180])

            try:
                media = client.get(
                    base + "/" + ig_id + "/media",
                    params={
                        "fields": "id,caption,media_type,timestamp,permalink,like_count,comments_count",
                        "limit": 25,
                        "access_token": token,
                    },
                )
                media.raise_for_status()
                rows = list((media.json() or {}).get("data") or [])
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                recent = []
                for row in rows:
                    ts = _parse_dt(row.get("timestamp"))
                    if not ts or ts >= cutoff:
                        recent.append(row)
                instagram["posts"] = recent
                instagram["posts_count"] = len(recent)
                instagram["engagement_actions"] = sum(
                    int(row.get("like_count") or 0) + int(row.get("comments_count") or 0)
                    for row in recent
                )
            except Exception as exc:
                errors.append("Instagram media: %s" % str(exc)[:180])

    facebook.setdefault("posts", [])
    instagram.setdefault("posts", [])
    live = bool(facebook.get("page"))
    return {
        "status": "live" if live else "error",
        "facebook": facebook,
        "instagram": instagram,
        "ads": ads,
        "error": "; ".join(errors)[:500] if errors else None,
    }



def _google_snapshot(days: int = 30) -> dict[str, Any]:
    if not google_bi_configured():
        return {
            "status": "not_configured",
            "ga4": {},
            "search_console": {},
            "youtube": {},
            "error": None,
        }

    headers = authorization_headers()
    errors: list[str] = []
    ga4: dict[str, Any] = {}
    search_console: dict[str, Any] = {}
    youtube: dict[str, Any] = {}
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=max(1, days - 1))

    with httpx.Client(timeout=25.0, headers=headers) as client:
        try:
            response = client.get(
                "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                params={"pageSize": 200},
            )
            response.raise_for_status()
            summaries = list((response.json() or {}).get("accountSummaries") or [])
            properties = []
            for account in summaries:
                for prop in account.get("propertySummaries") or []:
                    properties.append({
                        "account": account.get("displayName"),
                        "property": prop.get("property"),
                        "display_name": prop.get("displayName"),
                    })
            selected = next(
                (row for row in properties if "pitmark" in str(row.get("display_name") or "").lower()),
                properties[0] if properties else None,
            )
            ga4["properties"] = properties
            ga4["selected_property"] = selected
            if selected and selected.get("property"):
                property_name = selected["property"]
                report = client.post(
                    "https://analyticsdata.googleapis.com/v1beta/%s:runReport" % property_name,
                    json={
                        "dateRanges": [{"startDate": "%sdaysAgo" % days, "endDate": "today"}],
                        "metrics": [
                            {"name": "sessions"},
                            {"name": "totalUsers"},
                            {"name": "screenPageViews"},
                            {"name": "eventCount"},
                        ],
                    },
                )
                report.raise_for_status()
                rows = list((report.json() or {}).get("rows") or [])
                values = ((rows[0].get("metricValues") or []) if rows else [])
                metric_names = ["sessions", "total_users", "page_views", "event_count"]
                ga4["summary"] = {
                    metric_names[i]: _money(value.get("value"))
                    for i, value in enumerate(values)
                    if i < len(metric_names)
                }

                pages = client.post(
                    "https://analyticsdata.googleapis.com/v1beta/%s:runReport" % property_name,
                    json={
                        "dateRanges": [{"startDate": "%sdaysAgo" % days, "endDate": "today"}],
                        "dimensions": [{"name": "pagePath"}],
                        "metrics": [{"name": "screenPageViews"}, {"name": "sessions"}],
                        "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
                        "limit": 10,
                    },
                )
                pages.raise_for_status()
                ga4["top_pages"] = [
                    {
                        "path": ((row.get("dimensionValues") or [{}])[0]).get("value"),
                        "page_views": _money(((row.get("metricValues") or [{}, {}])[0]).get("value")),
                        "sessions": _money(((row.get("metricValues") or [{}, {}])[1]).get("value")),
                    }
                    for row in ((pages.json() or {}).get("rows") or [])
                ]
        except Exception as exc:
            errors.append("GA4: %s" % str(exc)[:180])

        try:
            response = client.get("https://www.googleapis.com/webmasters/v3/sites")
            response.raise_for_status()
            sites = list((response.json() or {}).get("siteEntry") or [])
            selected = next(
                (row for row in sites if "pitmarkracing.com" in str(row.get("siteUrl") or "").lower()),
                sites[0] if sites else None,
            )
            search_console["sites"] = sites
            search_console["selected_site"] = selected
            if selected and selected.get("siteUrl"):
                site = selected["siteUrl"]
                encoded = quote(site, safe="")
                query = client.post(
                    "https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % encoded,
                    json={
                        "startDate": start_date.isoformat(),
                        "endDate": end_date.isoformat(),
                        "dimensions": ["query"],
                        "rowLimit": 10,
                    },
                )
                query.raise_for_status()
                search_console["top_queries"] = [
                    {
                        "query": ((row.get("keys") or [""])[0]),
                        "clicks": row.get("clicks", 0),
                        "impressions": row.get("impressions", 0),
                        "ctr": row.get("ctr", 0),
                        "position": row.get("position", 0),
                    }
                    for row in ((query.json() or {}).get("rows") or [])
                ]
        except Exception as exc:
            errors.append("Search Console: %s" % str(exc)[:180])

        try:
            response = client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet,statistics", "mine": "true"},
            )
            response.raise_for_status()
            channels = list((response.json() or {}).get("items") or [])
            youtube["channels"] = channels
            if channels:
                channel = channels[0]
                stats = channel.get("statistics") or {}
                youtube["summary"] = {
                    "title": ((channel.get("snippet") or {}).get("title")),
                    "subscribers": int(stats.get("subscriberCount") or 0),
                    "views": int(stats.get("viewCount") or 0),
                    "videos": int(stats.get("videoCount") or 0),
                }
        except Exception as exc:
            errors.append("YouTube: %s" % str(exc)[:180])

    live = bool(ga4.get("selected_property") or search_console.get("selected_site") or youtube.get("channels"))
    return {
        "status": "live" if live else "error",
        "ga4": ga4,
        "search_console": search_console,
        "youtube": youtube,
        "error": "; ".join(errors)[:700] if errors else None,
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
            "feedback_open": int(feedback["open"] if "open" in feedback else (feedback.get("total") or 0)),
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


def _recommendations(shopify: dict[str, Any], growth: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, str]]:
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

    ads = meta.get("ads") or {}
    ad_summary = ads.get("summary") or {}
    ad_spend = _money(ad_summary.get("spend"))
    ad_clicks = int(float(ad_summary.get("clicks") or 0))
    if ad_spend > 0 and orders == 0:
        items.append({
            "priority": "high",
            "type": "paid_media",
            "title": "Paid Meta spend occurred without a Shopify order in the same window",
            "reason": "Meta reports $%,.2f in spend and %s click(s), while Shopify reports zero qualifying orders for the same reporting window." % (ad_spend, ad_clicks),
            "action": "Do not increase paid spend until landing-page, offer, tracking, and checkout friction are reviewed.",
        })
    elif ad_spend > 0 and ad_clicks == 0:
        items.append({
            "priority": "high",
            "type": "paid_media",
            "title": "Meta spend is not producing clicks",
            "reason": "Meta reports $%,.2f in spend with zero clicks in the current reporting window." % ad_spend,
            "action": "Pause or inspect active campaigns before allowing additional spend.",
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
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pitmark-intelligence")
    futures = {
        "shopify": executor.submit(_shopify_window, safe_days),
        "growth": executor.submit(_internal_growth),
        "meta": executor.submit(_meta_snapshot, safe_days),
        "google": executor.submit(_google_snapshot, safe_days),
    }
    done, pending = wait(list(futures.values()), timeout=12.0)
    executor.shutdown(wait=False, cancel_futures=True)

    def result(name: str, fallback: dict[str, Any]) -> dict[str, Any]:
        future = futures[name]
        if future not in done:
            return fallback
        try:
            value = future.result()
            return value if isinstance(value, dict) else fallback
        except Exception as exc:
            return {**fallback, "status": "error", "error": str(exc)[:400]}

    shopify = result("shopify", {
        "status": "timeout", "days": safe_days, "revenue": 0.0, "orders": 0,
        "average_order_value": 0.0, "currency": "USD", "daily": [],
        "top_products": [], "recent_orders": [], "error": "Shopify did not respond within 12 seconds.",
    })
    growth = result("growth", {
        "prt": {}, "content": {}, "relationships": {}, "status": "timeout",
        "error": "Pitmark internal intelligence did not respond within 12 seconds.",
    })
    meta = result("meta", {
        "status": "timeout", "facebook": {}, "instagram": {}, "ads": {},
        "error": "Meta did not respond within 12 seconds.",
    })
    google = result("google", {
        "status": "timeout", "ga4": {}, "search_console": {}, "youtube": {},
        "error": "Google analytics sources did not respond within 12 seconds.",
    })
    return {
        "version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": safe_days,
        "sources": {
            "shopify": {"status": shopify.get("status"), "live": shopify.get("status") == "live", "error": shopify.get("error")},
            "pitmark_internal": {"status": "live", "live": True, "error": None},
            "meta": {"status": meta.get("status"), "live": meta.get("status") == "live", "error": meta.get("error")},
            "meta_ads": {"status": meta.get("status"), "live": bool((meta.get("ads") or {}).get("selected_account")), "error": meta.get("error")},
            "ga4": {"status": google.get("status"), "live": bool((google.get("ga4") or {}).get("selected_property")), "error": google.get("error")},
            "search_console": {"status": google.get("status"), "live": bool((google.get("search_console") or {}).get("selected_site")), "error": google.get("error")},
            "youtube": {"status": google.get("status"), "live": bool((google.get("youtube") or {}).get("channels")), "error": google.get("error")},
            "tiktok": {
                "status": "auth_required" if (settings.tiktok_client_key and settings.tiktok_client_secret) else "not_configured",
                "live": False,
                "error": None,
            },
            "x": {
                "status": "cost_guarded" if (settings.x_access_token or settings.x_api_key) else "not_configured",
                "live": False,
                "error": "Paid X reads remain disabled by Pitmark cost controls." if (settings.x_access_token or settings.x_api_key) else None,
            },
        },
        "commerce": shopify,
        "social": {"meta": meta, "google": google},
        "growth": growth,
        "recommendations": _recommendations(shopify, growth, meta),
    }
