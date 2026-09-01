from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from services import prt_licensing_store
from utils.config import settings

_TOKEN: str | None = None
_TOKEN_EXPIRES_AT: float = 0.0
API_VERSION = "2026-07"


def _shop_host() -> str:
    raw = (settings.shopify_shop_domain or "").strip()
    if not raw:
        return ""
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.strip("/")


def configured() -> bool:
    return bool(_shop_host() and settings.shopify_client_id and settings.shopify_client_secret)


def status() -> dict:
    return {
        "configured": configured(),
        "webhook_configured": bool(settings.shopify_webhook_secret),
        "prt_products_mapped": True,
        "message": (
            "Shopify credentials are configured; live authentication is available."
            if configured()
            else "Shopify integration is ready. Credentials have not been configured yet."
        ),
    }


def get_access_token(force_refresh: bool = False) -> str:
    global _TOKEN, _TOKEN_EXPIRES_AT
    if not configured():
        raise RuntimeError("Shopify credentials are not configured")
    now = time.time()
    if not force_refresh and _TOKEN and now < (_TOKEN_EXPIRES_AT - 60):
        return _TOKEN
    url = f"https://{_shop_host()}/admin/oauth/access_token"
    with httpx.Client(timeout=20.0) as client:
        response = client.post(
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
            },
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Shopify token request failed ({response.status_code})")
    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Shopify token response did not include an access token")
    expires_in = int(data.get("expires_in") or 86399)
    _TOKEN = token
    _TOKEN_EXPIRES_AT = now + expires_in
    return token


def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    token = get_access_token()
    url = f"https://{_shop_host()}/admin/api/{API_VERSION}/graphql.json"
    with httpx.Client(timeout=25.0) as client:
        response = client.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": token,
            },
            json={"query": query, "variables": variables or {}},
        )
    if response.status_code == 401:
        token = get_access_token(force_refresh=True)
        with httpx.Client(timeout=25.0) as client:
            response = client.post(
                url,
                headers={"Content-Type": "application/json", "X-Shopify-Access-Token": token},
                json={"query": query, "variables": variables or {}},
            )
    if response.status_code >= 400:
        raise RuntimeError(f"Shopify API request failed ({response.status_code})")
    payload = response.json()
    if payload.get("errors"):
        msg = "; ".join(str(e.get("message", "GraphQL error")) for e in payload["errors"][:3])
        raise RuntimeError(f"Shopify GraphQL error: {msg}")
    return payload.get("data") or {}


def connection_test() -> dict[str, Any]:
    data = graphql("query PitmarkShopifyConnection { shop { name myshopifyDomain } }")
    shop = data.get("shop") or {}
    return {
        "configured": True,
        "authenticated": bool(shop.get("myshopifyDomain")),
        "shop_name": shop.get("name"),
        "shop_domain": shop.get("myshopifyDomain"),
        "api_version": API_VERSION,
        "webhook_configured": bool(settings.shopify_webhook_secret),
    }


def verify_webhook(body: bytes, supplied_hmac: str) -> bool:
    secret = (settings.shopify_webhook_secret or settings.shopify_client_secret or "").encode("utf-8")
    if not secret or not supplied_hmac:
        return False
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, supplied_hmac.strip())


def _as_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith("gid://"):
        return text.rsplit("/", 1)[-1]
    return text


def _selling_plan_name(line: dict[str, Any]) -> str:
    allocation = line.get("selling_plan_allocation") or {}
    selling_plan = allocation.get("selling_plan") or {}
    candidates = [
        selling_plan.get("name"),
        allocation.get("selling_plan_name"),
        line.get("selling_plan_name"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return ""


def infer_billing_interval(line: dict[str, Any], order: dict[str, Any]) -> str:
    text = " ".join([
        _selling_plan_name(line),
        str(line.get("title") or ""),
        str(line.get("variant_title") or ""),
        json.dumps(line.get("properties") or [], default=str),
        str(order.get("note") or ""),
    ]).lower()
    if any(token in text for token in ("12 month", "12-month", "yearly", "annual", "1 year")):
        return "yearly"
    return "monthly"


def process_paid_order(order: dict[str, Any]) -> list[dict[str, Any]]:
    prt_licensing_store.ensure_default_shopify_mappings()
    order_id = _as_id(order.get("id") or order.get("admin_graphql_api_id"))
    if not order_id:
        return []
    customer = order.get("customer") or {}
    customer_id = _as_id(customer.get("id") or order.get("customer_id"))
    email = str(order.get("email") or order.get("contact_email") or customer.get("email") or "").strip().lower()
    order_name = str(order.get("name") or order.get("order_number") or order_id)
    paid_at = str(order.get("processed_at") or order.get("created_at") or "")
    records: list[dict[str, Any]] = []
    for line in order.get("line_items") or []:
        variant_id = _as_id(line.get("variant_id") or line.get("variant", {}).get("id"))
        product_id = _as_id(line.get("product_id") or line.get("product", {}).get("id"))
        mapping = prt_licensing_store.get_shopify_mapping(variant_id)
        if not mapping:
            continue
        billing_interval = infer_billing_interval(line, order)
        record = prt_licensing_store.upsert_shopify_purchase({
            "order_id": order_id,
            "order_name": order_name,
            "customer_id": customer_id,
            "email": email,
            "product_id": product_id or mapping.get("product_id", ""),
            "variant_id": variant_id,
            "plan": mapping["plan"],
            "billing_interval": billing_interval,
            "status": "active",
            "selling_plan_name": _selling_plan_name(line),
            "paid_at": paid_at,
        })
        records.append(record)
        renewal_days = 380 if billing_interval == "yearly" else 40
        prt_licensing_store.refresh_entitlements_for_shopify_customer(
            customer_id,
            plan=mapping["plan"],
            order_id=order_id,
            grace_until=(datetime.now(timezone.utc) + timedelta(days=renewal_days)).isoformat(),
        )
    return records


def process_order_invalidation(order: dict[str, Any], status: str) -> int:
    order_id = _as_id(order.get("order_id") or order.get("id") or order.get("admin_graphql_api_id"))
    if not order_id:
        return 0
    prt_licensing_store.set_purchase_status(order_id, status)
    return prt_licensing_store.deactivate_entitlements_for_order(order_id, status=status)



def process_refund(refund: dict[str, Any]) -> int:
    prt_licensing_store.ensure_default_shopify_mappings()
    prt_refunded = False
    for item in refund.get("refund_line_items") or []:
        line = item.get("line_item") or {}
        variant_id = _as_id(line.get("variant_id") or line.get("variant", {}).get("id"))
        if variant_id and prt_licensing_store.get_shopify_mapping(variant_id):
            prt_refunded = True
            break
    if not prt_refunded:
        return 0
    return process_order_invalidation(refund, "inactive")

def process_subscription_status(payload: dict[str, Any], status_override: str = "") -> int:
    customer_id = _as_id(payload.get("customer_id") or payload.get("admin_graphql_api_customer_id"))
    if not customer_id:
        return 0
    raw = status_override or str(payload.get("status") or "inactive")
    normalized = raw.strip().lower()
    if normalized in {"active", "trialing"}:
        entitlement_status = "active"
    elif normalized in {"paused", "failed"}:
        entitlement_status = "grace"
    else:
        entitlement_status = "inactive"
    return prt_licensing_store.set_entitlements_status_for_shopify_customer(customer_id, entitlement_status)


def list_blogs() -> list[dict[str, Any]]:
    data = graphql("query PitmarkBlogs { blogs(first: 25) { nodes { id title handle } } }")
    blogs = list(((data.get("blogs") or {}).get("nodes") or []))
    preferred_handles = {"racing-culture", "news", "pitmark", "track-spotlight"}
    blogs.sort(key=lambda blog: 0 if (blog.get("handle") or "").lower() in preferred_handles else 1)
    return blogs


def publish_article(*, blog_id: str, title: str, body_html: str, author: str = "Pitmark Racing Co.", image_url: str | None = None) -> dict[str, Any]:
    mutation = """
    mutation PitmarkPublishArticle($article: ArticleCreateInput!) {
      articleCreate(article: $article) {
        article { id title handle isPublished }
        userErrors { code field message }
      }
    }
    """
    article: dict[str, Any] = {
        "blogId": blog_id,
        "title": title,
        "author": {"name": author},
        "body": body_html,
        "isPublished": True,
    }
    if image_url:
        article["image"] = {"url": image_url, "altText": title}
    data = graphql(mutation, {"article": article})
    result = data.get("articleCreate") or {}
    errors = result.get("userErrors") or []
    if errors:
        raise RuntimeError("Shopify article rejected: " + "; ".join(str(e.get("message", "Unknown error")) for e in errors[:3]))
    created = result.get("article")
    if not created:
        raise RuntimeError("Shopify did not return the created article")
    return created
