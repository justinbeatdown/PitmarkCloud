from __future__ import annotations

import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from models.schemas import ShopifyStatusResponse
from services import prt_licensing_store
from services.shopify_service import (
    connection_test,
    process_order_invalidation,
    process_paid_order,
    process_refund,
    process_subscription_status,
    status as shopify_status,
    verify_webhook,
)

router = APIRouter()


@router.get("/status", response_model=ShopifyStatusResponse)
async def status_endpoint() -> ShopifyStatusResponse:
    status = shopify_status()
    return ShopifyStatusResponse(configured=status["configured"], message=status["message"])


@router.get("/connection")
async def connection_endpoint():
    try:
        return connection_test()
    except Exception as exc:
        return {"configured": shopify_status().get("configured", False), "authenticated": False, "error": str(exc)}


@router.post("/webhooks")
async def webhooks(request: Request) -> JSONResponse:
    body = await request.body()
    supplied_hmac = request.headers.get("X-Shopify-Hmac-Sha256", "")
    if not verify_webhook(body, supplied_hmac):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid Shopify webhook payload")

    topic = request.headers.get("X-Shopify-Topic", "").strip().lower()
    result: dict = {"ok": True, "topic": topic}

    if topic in {"orders/paid", "orders/create"}:
        financial = str(payload.get("financial_status") or "").lower()
        if topic == "orders/create" and financial not in {"paid", "partially_paid"}:
            result["ignored"] = "order is not paid yet"
        else:
            records = process_paid_order(payload)
            result["prt_purchases"] = len(records)
            result["plans"] = sorted({r.get("plan", "") for r in records if r.get("plan")})
    elif topic == "orders/cancelled":
        result["entitlements_updated"] = process_order_invalidation(payload, "inactive")
    elif topic == "refunds/create":
        result["entitlements_updated"] = process_refund(payload)
    elif topic.startswith("subscription_contracts/"):
        result["entitlements_updated"] = process_subscription_status(payload)
    else:
        result["ignored"] = "topic not used by Pitmark licensing"

    return JSONResponse(result)


@router.get("/prt-products")
async def prt_products() -> dict:
    prt_licensing_store.ensure_default_shopify_mappings()
    return {"items": prt_licensing_store.list_shopify_mappings()}
