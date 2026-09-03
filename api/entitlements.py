from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from models.schemas import (
    EntitlementResponse,
    ManualEntitlementUpdate,
    PitmarkPlan,
    ShopifyLicenseClaim,
    ShopifyPlanMappingUpdate,
)
from services import device_auth_service, prt_licensing_store, prt_feedback
from services.control_auth import require_control_user
from services.control_access import access_from_request
from services.prt_analytics import summary as prt_analytics_summary, active_device_ids
from services.licensing import (
    current_entitlements,
    development_entitlements,
    grant_manual_entitlement,
)
from utils.config import settings
from utils.security import enforce_rate_limit

router = APIRouter()


class EarlyAccessClaim(BaseModel):
    device_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    code: str = Field(min_length=16, max_length=64)
    display_name: str = Field(default="Pitmark Racer", max_length=180)


class EarlyAccessInviteCreate(BaseModel):
    applicant_name: str = Field(min_length=1, max_length=180)
    email: str = Field(min_length=3, max_length=254)
    discord: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)
    expires_days: int = Field(default=14, ge=1, le=90)


class TesterStatusUpdate(BaseModel):
    tester_status: str = Field(min_length=1, max_length=32)


class TesterFeedbackCreate(BaseModel):
    invite_id: int | None = None
    tester_name: str = Field(default="", max_length=180)
    tester_email: str = Field(default="", max_length=254)
    kind: str = Field(default="feedback", max_length=32)
    severity: str = Field(default="normal", max_length=24)
    title: str = Field(min_length=1, max_length=220)
    detail: str = Field(min_length=1, max_length=8000)


class TesterFeedbackStatus(BaseModel):
    status: str = Field(min_length=1, max_length=24)


class EarlyAccessFeedbackSubmit(BaseModel):
    device_id: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    kind: str = Field(default="feedback", max_length=32)
    severity: str = Field(default="normal", max_length=24)
    title: str = Field(min_length=1, max_length=220)
    detail: str = Field(min_length=1, max_length=8000)


def _require_early_access_admin(request: Request, admin_key: str | None = None):
    user = require_control_user(request, admin_key)
    # Service-admin key remains available for automation/emergency use. Human UI
    # code generation is limited to Control Center owners/admins.
    if user is None:
        return None
    access = access_from_request(request)
    if not access or access.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="PRT Early Access management requires Owner or Admin access.")
    return access


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


@router.post("/claim-early-access", response_model=EntitlementResponse)
async def claim_early_access(payload: EarlyAccessClaim, request: Request) -> EntitlementResponse:
    enforce_rate_limit(request, "prt-entitlement-early-access-claim", 12, 300)
    token = request.headers.get("X-Pitmark-Device-Token")
    if not device_auth_service.authenticate(payload.device_id, token):
        raise HTTPException(status_code=401, detail="Invalid Pitmark device credential.")

    try:
        invite = prt_licensing_store.redeem_early_access_invite(payload.code, payload.device_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="That PRT Early Access code was not found.")
    except TimeoutError:
        raise HTTPException(status_code=410, detail="That PRT Early Access code has expired.")
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    # Early Access gets the complete current feature set while remaining fully
    # revocable and separate from Shopify purchases. A short offline grace keeps
    # testers usable through temporary outages without making revoked access linger.
    grace = datetime.now(timezone.utc) + timedelta(days=3)
    existing = prt_licensing_store.get_entitlement(payload.device_id)
    if not existing or str(existing.get("source") or "") != "shopify":
        prt_licensing_store.upsert_entitlement({
            "device_id": payload.device_id,
            "customer_id": f"early-access:{invite['id']}",
            "display_name": payload.display_name.strip() or invite.get("applicant_name") or "Pitmark Tester",
            "plan": PitmarkPlan.league_team.value,
            "status": "active",
            "source": "early_access",
            "shopify_customer_id": "",
            "shopify_subscription_id": "",
            "offline_grace_until": grace.isoformat(),
        })
    return current_entitlements(payload.device_id)


@router.get("/admin/summary")
async def admin_prt_summary(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    analytics = prt_analytics_summary()
    feedback = prt_feedback.summary()
    return prt_licensing_store.licensing_summary(
        registered_devices=int(analytics.get("registered_devices") or 0),
        recent_device_ids=active_device_ids(15),
        open_feedback=int(feedback.get("open") or 0),
    )


@router.get("/admin/early-access")
async def admin_early_access_list(
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    return {"items": prt_licensing_store.list_early_access_invites()}


@router.post("/admin/early-access")
async def admin_early_access_create(
    payload: EarlyAccessInviteCreate,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    enforce_rate_limit(request, "prt-early-access-admin-create", 60, 300)
    item = prt_licensing_store.create_early_access_invite(
        applicant_name=payload.applicant_name,
        email=payload.email,
        discord=payload.discord,
        notes=payload.notes,
        expires_days=payload.expires_days,
    )
    code = item.pop("code")
    return {"ok": True, "code": code, "invite": item}


@router.post("/admin/early-access/{invite_id}/revoke")
async def admin_early_access_revoke(
    invite_id: int,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    item = prt_licensing_store.revoke_early_access_invite(invite_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Early Access invite not found.")
    return {"ok": True, "invite": item}


@router.post("/admin/early-access/{invite_id}/tester-status")
async def admin_early_access_tester_status(
    invite_id: int, payload: TesterStatusUpdate, request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    try:
        item = prt_licensing_store.set_early_access_tester_status(invite_id, payload.tester_status)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if item is None:
        raise HTTPException(status_code=404, detail="Early Access invite not found.")
    return {"ok": True, "invite": item}


@router.get("/admin/feedback")
async def admin_feedback_list(
    request: Request, status: str | None = None,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    return {"items": prt_feedback.list_feedback(status=status), "summary": prt_feedback.summary()}


@router.post("/admin/feedback")
async def admin_feedback_create(
    payload: TesterFeedbackCreate, request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    enforce_rate_limit(request, "prt-feedback-admin-create", 120, 300)
    try:
        item = prt_feedback.create_feedback(
            invite_id=payload.invite_id, tester_name=payload.tester_name, tester_email=payload.tester_email,
            kind=payload.kind, severity=payload.severity, title=payload.title, detail=payload.detail,
            source="control_center",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "feedback": item}


@router.post("/admin/feedback/{feedback_id}/status")
async def admin_feedback_status(
    feedback_id: int, payload: TesterFeedbackStatus, request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
) -> dict:
    _require_early_access_admin(request, x_pitmark_admin_key)
    try:
        item = prt_feedback.update_status(feedback_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if item is None:
        raise HTTPException(status_code=404, detail="Feedback report not found.")
    return {"ok": True, "feedback": item}


@router.post("/feedback")
async def tester_feedback_submit(payload: EarlyAccessFeedbackSubmit, request: Request) -> dict:
    enforce_rate_limit(request, "prt-feedback-submit", 20, 300)
    token = request.headers.get("X-Pitmark-Device-Token")
    if not device_auth_service.authenticate(payload.device_id, token):
        raise HTTPException(status_code=401, detail="Invalid Pitmark device credential.")
    invite = prt_licensing_store.get_early_access_for_device(payload.device_id)
    if not invite:
        raise HTTPException(status_code=403, detail="Active PRT Early Access is required to submit tester feedback.")
    try:
        item = prt_feedback.create_feedback(
            invite_id=invite.get("id"), tester_name=invite.get("applicant_name") or "",
            tester_email=invite.get("email") or "", device_id=payload.device_id,
            kind=payload.kind, severity=payload.severity, title=payload.title, detail=payload.detail, source="prt_app",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "feedback_id": item["id"]}


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
