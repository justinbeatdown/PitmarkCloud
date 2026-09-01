from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, String, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PrtEntitlementRow(Base):
    __tablename__ = "prt_entitlements"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(180), default="")
    display_name: Mapped[str] = mapped_column(String(180), default="")
    plan: Mapped[str] = mapped_column(String(32), default="free")
    status: Mapped[str] = mapped_column(String(32), default="active")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    shopify_customer_id: Mapped[str] = mapped_column(String(80), default="")
    shopify_subscription_id: Mapped[str] = mapped_column(String(80), default="")
    offline_grace_until: Mapped[str] = mapped_column(String(64), default=_now_iso)
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


class ShopifyPlanMappingRow(Base):
    __tablename__ = "prt_shopify_plan_mappings"

    variant_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(80), default="")
    plan: Mapped[str] = mapped_column(String(32), default="free")
    billing_interval: Mapped[str] = mapped_column(String(32), default="monthly")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


class ShopifyPurchaseRow(Base):
    __tablename__ = "prt_shopify_purchases"

    order_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    order_name: Mapped[str] = mapped_column(String(80), default="")
    customer_id: Mapped[str] = mapped_column(String(80), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    product_id: Mapped[str] = mapped_column(String(80), default="")
    variant_id: Mapped[str] = mapped_column(String(80), default="")
    plan: Mapped[str] = mapped_column(String(32), default="free")
    billing_interval: Mapped[str] = mapped_column(String(32), default="monthly")
    status: Mapped[str] = mapped_column(String(32), default="active")
    selling_plan_name: Mapped[str] = mapped_column(String(180), default="")
    paid_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


DEFAULT_SHOPIFY_MAPPINGS = (
    {
        "variant_id": "60271858024529",
        "product_id": "16009945579601",
        "plan": "pro",
        "billing_interval": "subscription",
        "active": True,
    },
    {
        "variant_id": "60271874211921",
        "product_id": "16009947643985",
        "plan": "league_team",
        "billing_interval": "subscription",
        "active": True,
    },
)


def get_entitlement(device_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.get(PrtEntitlementRow, device_id)
        if row is None:
            return None
        return {
            "device_id": row.device_id,
            "customer_id": row.customer_id,
            "display_name": row.display_name,
            "plan": row.plan,
            "status": row.status,
            "source": row.source,
            "shopify_customer_id": row.shopify_customer_id,
            "shopify_subscription_id": row.shopify_subscription_id,
            "offline_grace_until": row.offline_grace_until,
            "updated_at": row.updated_at,
        }


def upsert_entitlement(values: dict) -> dict:
    device_id = str(values["device_id"])
    with SessionLocal() as db:
        row = db.get(PrtEntitlementRow, device_id)
        if row is None:
            row = PrtEntitlementRow(device_id=device_id)
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key) and key != "device_id":
                setattr(row, key, value)
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
    return get_entitlement(device_id) or {}


def upsert_shopify_mapping(values: dict) -> dict:
    variant_id = str(values["variant_id"])
    with SessionLocal() as db:
        row = db.get(ShopifyPlanMappingRow, variant_id)
        if row is None:
            row = ShopifyPlanMappingRow(variant_id=variant_id)
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key) and key != "variant_id":
                setattr(row, key, value)
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
        return {
            "variant_id": row.variant_id,
            "product_id": row.product_id,
            "plan": row.plan,
            "billing_interval": row.billing_interval,
            "active": row.active,
            "updated_at": row.updated_at,
        }


def ensure_default_shopify_mappings() -> None:
    for mapping in DEFAULT_SHOPIFY_MAPPINGS:
        if get_shopify_mapping(mapping["variant_id"]) is None:
            upsert_shopify_mapping(mapping)


def list_shopify_mappings() -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ShopifyPlanMappingRow).order_by(ShopifyPlanMappingRow.variant_id)
        ).all()
        return [{
            "variant_id": row.variant_id,
            "product_id": row.product_id,
            "plan": row.plan,
            "billing_interval": row.billing_interval,
            "active": row.active,
            "updated_at": row.updated_at,
        } for row in rows]


def get_shopify_mapping(variant_id: str) -> dict | None:
    with SessionLocal() as db:
        row = db.get(ShopifyPlanMappingRow, str(variant_id))
        if row is None or not row.active:
            return None
        return {
            "variant_id": row.variant_id,
            "product_id": row.product_id,
            "plan": row.plan,
            "billing_interval": row.billing_interval,
            "active": row.active,
            "updated_at": row.updated_at,
        }


def upsert_shopify_purchase(values: dict) -> dict:
    order_id = str(values["order_id"])
    with SessionLocal() as db:
        row = db.get(ShopifyPurchaseRow, order_id)
        if row is None:
            row = ShopifyPurchaseRow(order_id=order_id)
            db.add(row)
        for key, value in values.items():
            if hasattr(row, key) and key != "order_id":
                setattr(row, key, value)
        row.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
        return _purchase_dict(row)


def _purchase_dict(row: ShopifyPurchaseRow) -> dict:
    return {
        "order_id": row.order_id,
        "order_name": row.order_name,
        "customer_id": row.customer_id,
        "email": row.email,
        "product_id": row.product_id,
        "variant_id": row.variant_id,
        "plan": row.plan,
        "billing_interval": row.billing_interval,
        "status": row.status,
        "selling_plan_name": row.selling_plan_name,
        "paid_at": row.paid_at,
        "updated_at": row.updated_at,
    }


def get_shopify_purchase(order_id_or_name: str, email: str = "") -> dict | None:
    needle = str(order_id_or_name).strip()
    normalized_email = email.strip().lower()
    with SessionLocal() as db:
        row = db.get(ShopifyPurchaseRow, needle)
        if row is None:
            row = db.scalar(
                select(ShopifyPurchaseRow).where(ShopifyPurchaseRow.order_name == needle)
            )
        if row is None:
            return None
        if normalized_email and row.email.strip().lower() != normalized_email:
            return None
        return _purchase_dict(row)


def list_shopify_purchases(limit: int = 100) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ShopifyPurchaseRow)
            .order_by(ShopifyPurchaseRow.updated_at.desc())
            .limit(max(1, min(limit, 500)))
        ).all()
        return [_purchase_dict(row) for row in rows]


def set_purchase_status(order_id: str, status: str) -> None:
    with SessionLocal() as db:
        row = db.get(ShopifyPurchaseRow, str(order_id))
        if row is None:
            return
        row.status = status
        row.updated_at = _now_iso()
        db.commit()


def deactivate_entitlements_for_order(order_id: str, status: str = "inactive") -> int:
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtEntitlementRow).where(
                PrtEntitlementRow.shopify_subscription_id == str(order_id)
            )
        ).all()
        for row in rows:
            row.status = status
            row.updated_at = _now_iso()
        db.commit()
        return len(rows)


def set_entitlements_status_for_shopify_customer(customer_id: str, status: str) -> int:
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtEntitlementRow).where(
                PrtEntitlementRow.shopify_customer_id == str(customer_id)
            )
        ).all()
        for row in rows:
            row.status = status
            row.updated_at = _now_iso()
        db.commit()
        return len(rows)


def refresh_entitlements_for_shopify_customer(customer_id: str, *, plan: str, order_id: str, grace_until: str) -> int:
    if not customer_id:
        return 0
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtEntitlementRow).where(
                PrtEntitlementRow.shopify_customer_id == str(customer_id)
            )
        ).all()
        for row in rows:
            row.plan = plan
            row.status = "active"
            row.source = "shopify"
            row.shopify_subscription_id = str(order_id)
            row.offline_grace_until = grace_until
            row.updated_at = _now_iso()
        db.commit()
        return len(rows)
