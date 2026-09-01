from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from models.schemas import (
    EntitlementResponse,
    ManualEntitlementUpdate,
    PitmarkPlan,
    ShopifyLicenseClaim,
    ShopifyPlanMappingUpdate,
)
from services import device_auth_service, prt_licensing_store
from services.licensing import (
    current_entitlements,
    development_entitlements,
    grant_manual_entitlement,
)
from utils.config import settings
from utils.security import enforce_rate_limit

router = APIRouter()


def _require_admin(request: Request) -> None:
    supplied = request.headers.get("X-Pitmark-Admin-Key", "")
    configured = settings.pitmark_admin_key or ""
    if not supplied or not configured or not hmac.compare_digest(supplied, configured):
        raise HTTPException(status_code=401, detail="Pitmark admin authentication required.")


@router.get("/development", response_model=EntitlementResponse)
async def development() -> EntitlementResponse:
    return development_entitlements()


@router.get("/current/{device_id}", response_model=EntitlementResponse)
async def current(device_id: str, request: Request) -> EntitlementResponse:
    enforce_rate_limit(request, "prt-entitlement-current", 120, 300)
    token = request.headers.get("X-Pitmark-Device-Token")
    if not device_auth_service.authenticate(device_id, token):
        raise HTTPException(status_code=401, detail="Invalid Pitmark device credential.")
    return current_entitlements(device_id)


@router.post("/claim-shopify", response_model=EntitlementResponse)
async def claim_shopify(payload: ShopifyLicenseClaim, request: Request) -> EntitlementResponse:
    enforce_rate_limit(request, "prt-entitlement-shopify-claim", 20, 300)
    token = request.headers.get("X-Pitmark-Device-Token")
    if not device_auth_service.authenticate(payload.device_id, token):
        raise HTTPException(status_code=401, detail="Invalid Pitmark device credential.")

    purchase = prt_licensing_store.get_shopify_purchase(payload.order_id, payload.email)
    if purchase is None:
        raise HTTPException(status_code=404, detail="No matching Pitmark Racing Tools Shopify purchase was found.")
    if str(purchase.get("status") or "").lower() not in {"active", "paid"}:
        raise HTTPException(status_code=409, detail="This Shopify purchase is not active.")

    try:
        plan = PitmarkPlan(str(purchase.get("plan") or "free"))
    except ValueError:
        raise HTTPException(status_code=409, detail="This purchase is not mapped to a valid PRT plan.")

    interval = str(purchase.get("billing_interval") or "monthly").lower()
    grace_days = 380 if interval == "yearly" else 40
    grace = datetime.now(timezone.utc) + timedelta(days=grace_days)
    customer_id = str(purchase.get("customer_id") or payload.email.strip().lower())

    prt_licensing_store.upsert_entitlement({
        "device_id": payload.device_id,
        "customer_id": customer_id,
        "display_name": payload.display_name.strip() or "Pitmark Racer",
        "plan": plan.value,
        "status": "active",
        "source": "shopify",
        "shopify_customer_id": str(purchase.get("customer_id") or ""),
        "shopify_subscription_id": str(purchase.get("order_id") or ""),
        "offline_grace_until": grace.isoformat(),
    })
    return current_entitlements(payload.device_id)


@router.post("/admin/grant", response_model=EntitlementResponse)
async def admin_grant(payload: ManualEntitlementUpdate, request: Request) -> EntitlementResponse:
    _require_admin(request)
    enforce_rate_limit(request, "prt-entitlement-admin-grant", 60, 300)
    return grant_manual_entitlement(
        device_id=payload.device_id,
        customer_id=payload.customer_id,
        display_name=payload.display_name,
        plan=payload.plan,
        status=payload.status,
        source=payload.source,
        offline_grace_days=payload.offline_grace_days,
    )


@router.get("/admin/shopify-mappings")
async def admin_shopify_mappings(request: Request) -> dict:
    _require_admin(request)
    prt_licensing_store.ensure_default_shopify_mappings()
    return {"items": prt_licensing_store.list_shopify_mappings()}


@router.post("/admin/shopify-mappings")
async def admin_shopify_mapping(payload: ShopifyPlanMappingUpdate, request: Request) -> dict:
    _require_admin(request)
    return prt_licensing_store.upsert_shopify_mapping({
        "variant_id": payload.variant_id,
        "product_id": payload.product_id,
        "plan": payload.plan.value,
        "billing_interval": payload.billing_interval.strip().lower(),
        "active": payload.active,
    })


@router.get("/admin/shopify-purchases")
async def admin_shopify_purchases(request: Request, limit: int = 100) -> dict:
    _require_admin(request)
    return {"items": prt_licensing_store.list_shopify_purchases(limit=limit)}
