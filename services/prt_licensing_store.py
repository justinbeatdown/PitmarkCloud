from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import Boolean, Integer, String, select
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


class PrtEarlyAccessInviteRow(Base):
    __tablename__ = "prt_early_access_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    applicant_name: Mapped[str] = mapped_column(String(180), default="")
    email: Mapped[str] = mapped_column(String(254), index=True, default="")
    discord: Mapped[str] = mapped_column(String(120), default="")
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_hint: Mapped[str] = mapped_column(String(48), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="issued")
    tester_status: Mapped[str] = mapped_column(String(32), index=True, default="invited")
    notes: Mapped[str] = mapped_column(String(1000), default="")
    bound_device_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    expires_at: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    redeemed_at: Mapped[str] = mapped_column(String(64), default="")
    revoked_at: Mapped[str] = mapped_column(String(64), default="")
    last_seen_at: Mapped[str] = mapped_column(String(64), default="")



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

_EARLY_ACCESS_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _normalize_early_access_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "")


def _hash_early_access_code(code: str) -> str:
    return hashlib.sha256(_normalize_early_access_code(code).encode("utf-8")).hexdigest()


def _generate_early_access_code() -> str:
    groups = ["".join(secrets.choice(_EARLY_ACCESS_ALPHABET) for _ in range(4)) for _ in range(5)]
    return "PRT-EA-" + "-".join(groups)


def _early_access_dict(row: PrtEarlyAccessInviteRow) -> dict:
    return {
        "id": row.id,
        "applicant_name": row.applicant_name,
        "email": row.email,
        "discord": row.discord,
        "code_hint": row.code_hint,
        "status": row.status,
        "tester_status": row.tester_status,
        "notes": row.notes,
        "bound_device_id": row.bound_device_id,
        "expires_at": row.expires_at,
        "created_at": row.created_at,
        "redeemed_at": row.redeemed_at,
        "revoked_at": row.revoked_at,
        "last_seen_at": row.last_seen_at,
    }



def licensing_summary(*, registered_devices: int = 0) -> dict:
    with SessionLocal() as db:
        entitlements = list(db.scalars(select(PrtEntitlementRow)).all())
        invites = list(db.scalars(select(PrtEarlyAccessInviteRow)).all())

    active = [row for row in entitlements if str(row.status or "").lower() == "active"]
    early_access = [row for row in active if str(row.source or "").lower() == "early_access"]
    paid_or_manual = [row for row in active if str(row.source or "").lower() != "early_access"]
    active_device_ids = {row.device_id for row in active if row.device_id}
    free_devices = max(int(registered_devices or 0) - len(active_device_ids), 0)

    return {
        "registered_devices": int(registered_devices or 0),
        "free_devices": free_devices,
        "early_access": len(early_access),
        "pro": sum(1 for row in paid_or_manual if str(row.plan or "").lower() == "pro"),
        "league_team": sum(1 for row in paid_or_manual if str(row.plan or "").lower() == "league_team"),
        "active_entitlements": len(active),
        "invites_issued": sum(1 for row in invites if row.status == "issued"),
        "invites_redeemed": sum(1 for row in invites if row.status == "redeemed"),
        "invites_revoked": sum(1 for row in invites if row.status == "revoked"),
        "invites_expired": sum(1 for row in invites if row.status == "expired"),
    }

def create_early_access_invite(
    *,
    applicant_name: str,
    email: str,
    discord: str = "",
    notes: str = "",
    expires_days: int = 14,
) -> dict:
    applicant_name = applicant_name.strip()
    email = email.strip().lower()
    discord = discord.strip()
    notes = notes.strip()
    expires_days = max(1, min(int(expires_days), 90))

    with SessionLocal() as db:
        code = ""
        code_hash = ""
        for _ in range(20):
            candidate = _generate_early_access_code()
            candidate_hash = _hash_early_access_code(candidate)
            exists = db.scalar(select(PrtEarlyAccessInviteRow).where(PrtEarlyAccessInviteRow.code_hash == candidate_hash))
            if exists is None:
                code = candidate
                code_hash = candidate_hash
                break
        if not code:
            raise RuntimeError("Could not generate a unique Early Access code.")

        parts = code.split("-")
        hint = "-".join(parts[:3]) + "-••••-••••-" + parts[-1]
        row = PrtEarlyAccessInviteRow(
            applicant_name=applicant_name,
            email=email,
            discord=discord,
            code_hash=code_hash,
            code_hint=hint,
            status="issued",
            tester_status="invited",
            notes=notes,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=expires_days)).isoformat(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        item = _early_access_dict(row)
        item["code"] = code
        return item


def list_early_access_invites(limit: int = 250) -> list[dict]:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        rows = list(db.scalars(
            select(PrtEarlyAccessInviteRow)
            .order_by(PrtEarlyAccessInviteRow.id.desc())
            .limit(max(1, min(int(limit), 500)))
        ).all())
        changed = False
        for row in rows:
            if row.status == "issued" and row.expires_at:
                try:
                    expiry = datetime.fromisoformat(row.expires_at.replace("Z", "+00:00"))
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if expiry < now:
                        row.status = "expired"
                        changed = True
                except ValueError:
                    pass
        if changed:
            db.commit()
        return [_early_access_dict(row) for row in rows]


def redeem_early_access_invite(code: str, device_id: str) -> dict:
    code_hash = _hash_early_access_code(code)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    with SessionLocal() as db:
        row = db.scalar(select(PrtEarlyAccessInviteRow).where(PrtEarlyAccessInviteRow.code_hash == code_hash))
        if row is None:
            raise LookupError("Early Access code not found.")
        if row.status == "revoked" or row.tester_status == "removed":
            raise PermissionError("This Early Access code has been revoked.")
        if row.expires_at and row.status != "redeemed":
            try:
                expiry = datetime.fromisoformat(row.expires_at.replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < now:
                    row.status = "expired"
                    db.commit()
                    raise TimeoutError("This Early Access code has expired.")
            except ValueError:
                pass
        if row.bound_device_id and row.bound_device_id != device_id:
            raise PermissionError("This Early Access code is already bound to another PRT device.")

        row.bound_device_id = device_id
        row.status = "redeemed"
        row.tester_status = "active"
        if not row.redeemed_at:
            row.redeemed_at = now_iso
        row.last_seen_at = now_iso
        db.commit()
        db.refresh(row)
        return _early_access_dict(row)


def touch_early_access_device(device_id: str) -> None:
    with SessionLocal() as db:
        row = db.scalar(
            select(PrtEarlyAccessInviteRow).where(
                PrtEarlyAccessInviteRow.bound_device_id == device_id,
                PrtEarlyAccessInviteRow.status == "redeemed",
            )
        )
        if row is None:
            return
        row.last_seen_at = _now_iso()
        db.commit()


def revoke_early_access_invite(invite_id: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessInviteRow, int(invite_id))
        if row is None:
            return None
        row.status = "revoked"
        row.tester_status = "removed"
        row.revoked_at = _now_iso()
        bound_device_id = row.bound_device_id
        if bound_device_id:
            entitlement = db.get(PrtEntitlementRow, bound_device_id)
            if entitlement is not None and entitlement.source == "early_access":
                entitlement.status = "inactive"
                entitlement.offline_grace_until = _now_iso()
                entitlement.updated_at = _now_iso()
        db.commit()
        db.refresh(row)
        return _early_access_dict(row)

