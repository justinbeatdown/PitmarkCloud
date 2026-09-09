from __future__ import annotations

import base64
import hashlib
import hmac
from html import escape
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from services import google_gmail, prt_licensing_store, prt_paid_activation
from utils.config import settings

log = logging.getLogger("pitmark.shopify")

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


def _plan_label(plan: str) -> str:
    return "PRT League / Team" if (plan or "").strip().lower() == "league_team" else "PRT Pro"


def _prt_sender() -> str:
    preferred = f"prt@{google_gmail.business_domain()}".lower()
    send_as = google_gmail.list_send_as()

    for row in send_as:
        address = str(row.get("sendAsEmail") or "").strip().lower()
        if address == preferred:
            return address

    for row in send_as:
        if bool(row.get("isPrimary")) or bool(row.get("isDefault")):
            address = str(row.get("sendAsEmail") or "").strip()
            if address:
                return address

    for row in send_as:
        address = str(row.get("sendAsEmail") or "").strip()
        if address:
            return address

    configured_user = google_gmail.gmail_user().strip()
    if configured_user and configured_user.lower() != "me":
        return configured_user
    return f"justin@{google_gmail.business_domain()}"


def _deliver_paid_activation_email(activation: dict) -> None:
    code = str(activation.get("code") or "").strip()
    email = str(activation.get("email") or "").strip().lower()
    if not code or not email:
        raise RuntimeError("Paid PRT activation is missing its delivery code or customer email.")

    activation_id = int(activation["id"])
    plan_label = _plan_label(str(activation.get("plan") or "pro"))
    order_name = str(activation.get("order_name") or activation.get("order_id") or "").strip()
    sender = _prt_sender()

    subject = f"Your {plan_label} activation code"
    text = (
        f"Thanks for subscribing to {plan_label} during Pitmark Racing Tools Early Access.\n\n"
        f"YOUR PRT ACTIVATION CODE\n{code}\n\n"
        "How to activate:\n"
        "1. Install or open the latest Pitmark Racing Tools build.\n"
        "2. Enter this code on the PRT activation screen.\n"
        "3. PRT will bind your paid subscription to that PC through Pitmark Cloud.\n\n"
        "Your subscription stays linked to Shopify. Successful renewals keep access active; "
        "cancellations, failed payments, and refunds are reflected through Pitmark Cloud.\n"
    )
    if order_name:
        text += f"\nShopify order: {order_name}\n"
    text += "\nPitmark Racing Co.\nLeave your mark."

    safe_code = escape(code)
    safe_plan = escape(plan_label)
    safe_order = escape(order_name)
    html = f"""
    <div style="margin:0;padding:28px;background:#111214;color:#f3f3f3;font-family:Arial,sans-serif">
      <div style="max-width:620px;margin:0 auto;background:#1b1d20;border:1px solid #33363a;border-radius:12px;overflow:hidden">
        <div style="padding:24px 28px;border-bottom:3px solid #ff5500">
          <div style="font-size:12px;letter-spacing:2px;color:#ff5500;font-weight:700">PITMARK RACING TOOLS</div>
          <h1 style="margin:8px 0 0;font-size:26px;color:#fff">Your {safe_plan} code is ready.</h1>
        </div>
        <div style="padding:28px">
          <p style="line-height:1.6;color:#d5d7da">Thanks for subscribing while PRT is in Early Access. Your paid plan is ready to activate.</p>
          <div style="margin:24px 0;padding:18px;background:#101113;border:1px solid #ff5500;border-radius:8px;text-align:center">
            <div style="font-size:11px;letter-spacing:1.5px;color:#a9adb2">PRT ACTIVATION CODE</div>
            <div style="margin-top:9px;font-family:Consolas,monospace;font-size:23px;font-weight:700;color:#fff;letter-spacing:1px">{safe_code}</div>
          </div>
          <p style="line-height:1.7;color:#d5d7da">
            Install or open the latest PRT build, enter this code on the activation screen, and Pitmark Cloud will bind the subscription to that PC.
          </p>
          <p style="line-height:1.7;color:#aeb2b7;font-size:13px">
            Renewals stay automatic through Shopify. If a subscription is cancelled, refunded, or becomes inactive, Pitmark Cloud updates access automatically.
          </p>
          {"<p style='color:#8f949a;font-size:12px'>Shopify order: " + safe_order + "</p>" if safe_order else ""}
        </div>
        <div style="padding:18px 28px;background:#141517;color:#8f949a;font-size:12px">Pitmark Racing Co. &mdash; Leave your mark.</div>
      </div>
    </div>
    """

    try:
        raw = google_gmail.build_raw_message(
            sender=sender,
            to=[email],
            subject=subject,
            text=text,
            html=html,
            reply_to=[sender],
            headers={"X-Pitmark-Purpose": "prt-paid-activation"},
        )
        google_gmail.send_message(raw=raw)
    except Exception as exc:
        prt_paid_activation.mark_delivery_failure(activation_id, str(exc))
        log.exception(
            "PRT paid activation email failed: activation_id=%s order=%s",
            activation_id,
            activation.get("order_id"),
        )
        # Fail the webhook so Shopify retries. ensure_for_purchase() is idempotent,
        # so a retry resends the same code instead of minting duplicates.
        raise RuntimeError("PRT activation code was created but email delivery failed.") from exc

    prt_paid_activation.mark_delivery_success(activation_id)
    log.info(
        "PRT paid activation delivered: activation_id=%s plan=%s order=%s",
        activation_id,
        activation.get("plan"),
        activation.get("order_id"),
    )


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

        renewal_days = 380 if billing_interval == "yearly" else 40
        prt_licensing_store.refresh_entitlements_for_shopify_customer(
            customer_id,
            plan=mapping["plan"],
            order_id=order_id,
            grace_until=(datetime.now(timezone.utc) + timedelta(days=renewal_days)).isoformat(),
        )

        activation = prt_paid_activation.ensure_for_purchase(record)
        if activation and activation.get("code"):
            _deliver_paid_activation_email(activation)
        if activation:
            record["activation"] = {
                key: value
                for key, value in activation.items()
                if key != "code"
            }
        records.append(record)
    return records


def process_order_invalidation(order: dict[str, Any], status: str) -> int:
    order_id = _as_id(order.get("order_id") or order.get("id") or order.get("admin_graphql_api_id"))
    if not order_id:
        return 0
    prt_licensing_store.set_purchase_status(order_id, status)
    prt_paid_activation.revoke_for_order(order_id)
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
        prt_paid_activation.revoke_issued_for_customer(customer_id)
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
