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
