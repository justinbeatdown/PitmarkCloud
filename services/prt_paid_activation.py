from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets

from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from services import prt_licensing_store


_ACTIVATION_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PrtPaidActivationRow(Base):
    __tablename__ = "prt_paid_activation_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(80), index=True, default="")
    order_name: Mapped[str] = mapped_column(String(80), default="")
    customer_id: Mapped[str] = mapped_column(String(80), index=True, default="")
    email: Mapped[str] = mapped_column(String(254), index=True, default="")
    plan: Mapped[str] = mapped_column(String(32), index=True, default="pro")
    billing_interval: Mapped[str] = mapped_column(String(32), default="monthly")
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_hint: Mapped[str] = mapped_column(String(64), default="")
    # Plaintext exists only until the initial delivery succeeds. After that, only
    # the one-way hash and a masked hint remain in Pitmark Cloud.
    pending_code: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="issued")
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending")
    delivery_error: Mapped[str] = mapped_column(String(500), default="")
    bound_device_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    created_at: Mapped[str] = mapped_column(String(64), default=_now_iso)
    delivered_at: Mapped[str] = mapped_column(String(64), default="")
    redeemed_at: Mapped[str] = mapped_column(String(64), default="")
    revoked_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default=_now_iso)


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "")


def _hash_code(code: str) -> str:
    return hashlib.sha256(_normalize_code(code).encode("utf-8")).hexdigest()


def _prefix_for_plan(plan: str) -> str:
    return "PRT-TEAM" if (plan or "").strip().lower() == "league_team" else "PRT-PRO"


def _generate_code(plan: str) -> str:
    groups = [
        "".join(secrets.choice(_ACTIVATION_ALPHABET) for _ in range(4))
        for _ in range(3)
    ]
    return _prefix_for_plan(plan) + "-" + "-".join(groups)


def _hint_for_code(code: str) -> str:
    parts = _normalize_code(code).split("-")
    if len(parts) < 5:
        return "PRT-••••"
    return "-".join(parts[:3] + ["••••", parts[-1]])


def looks_like_paid_code(code: str) -> bool:
    value = _normalize_code(code)
    return value.startswith("PRT-PRO-") or value.startswith("PRT-TEAM-")


def _row_dict(row: PrtPaidActivationRow, *, include_pending_code: bool = False) -> dict:
    result = {
        "id": row.id,
        "order_id": row.order_id,
        "order_name": row.order_name,
        "customer_id": row.customer_id,
        "email": row.email,
        "plan": row.plan,
        "billing_interval": row.billing_interval,
        "code_hint": row.code_hint,
        "status": row.status,
        "delivery_status": row.delivery_status,
        "delivery_error": row.delivery_error,
        "bound_device_id": row.bound_device_id,
        "created_at": row.created_at,
        "delivered_at": row.delivered_at,
        "redeemed_at": row.redeemed_at,
        "revoked_at": row.revoked_at,
        "updated_at": row.updated_at,
    }
    if include_pending_code and row.pending_code:
        result["code"] = row.pending_code
    return result


def _existing_shopify_entitlement(db, customer_id: str, email: str = "") -> bool:
    customer_id = (customer_id or "").strip()
    email = (email or "").strip().lower()
    rows = db.scalars(
        select(prt_licensing_store.PrtEntitlementRow).where(
            prt_licensing_store.PrtEntitlementRow.source == "shopify"
        )
    ).all()
    for row in rows:
        if str(row.status or "").strip().lower() not in {"active", "trialing", "grace"}:
            continue
        if customer_id and str(row.shopify_customer_id or "") == customer_id:
            return True
        if not customer_id and email and str(row.customer_id or "").strip().lower() == email:
            return True
    return False


def ensure_for_purchase(purchase: dict) -> dict | None:
    """Return one idempotent activation for an unbound paid PRT purchase.

    Existing Shopify-entitled customers are renewals/upgrades and do not need a new
    activation code. Outstanding delivered codes are reused without being re-emailed;
    outstanding failed/pending deliveries return their original pending plaintext so a
    retried Shopify webhook can safely retry delivery without creating duplicates.
    """
    order_id = str(purchase.get("order_id") or "").strip()
    if not order_id:
        return None
    order_name = str(purchase.get("order_name") or order_id).strip()
    customer_id = str(purchase.get("customer_id") or "").strip()
    email = str(purchase.get("email") or "").strip().lower()
    plan = str(purchase.get("plan") or "pro").strip().lower()
    billing_interval = str(purchase.get("billing_interval") or "monthly").strip().lower()

    with SessionLocal() as db:
        if _existing_shopify_entitlement(db, customer_id, email):
            return None

        filters = [
            PrtPaidActivationRow.status == "issued",
            PrtPaidActivationRow.plan == plan,
        ]
        if customer_id:
            filters.append(PrtPaidActivationRow.customer_id == customer_id)
        else:
            filters.append(PrtPaidActivationRow.email == email)

        existing = db.scalar(
            select(PrtPaidActivationRow)
            .where(*filters)
            .order_by(PrtPaidActivationRow.id.desc())
        )
        if existing is not None:
            return _row_dict(
                existing,
                include_pending_code=existing.delivery_status != "delivered",
            )

        code = ""
        code_hash = ""
        for _ in range(24):
            candidate = _generate_code(plan)
            candidate_hash = _hash_code(candidate)
            found = db.scalar(
                select(PrtPaidActivationRow).where(
                    PrtPaidActivationRow.code_hash == candidate_hash
                )
            )
            if found is None:
                code = candidate
                code_hash = candidate_hash
                break
        if not code:
            raise RuntimeError("Could not generate a unique PRT paid activation code.")

        row = PrtPaidActivationRow(
            order_id=order_id,
            order_name=order_name,
            customer_id=customer_id,
            email=email,
            plan=plan,
            billing_interval=billing_interval,
            code_hash=code_hash,
            code_hint=_hint_for_code(code),
            pending_code=code,
            status="issued",
            delivery_status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _row_dict(row, include_pending_code=True)


def mark_delivery_success(activation_id: int) -> dict | None:
    now = _now_iso()
    with SessionLocal() as db:
        row = db.get(PrtPaidActivationRow, int(activation_id))
        if row is None:
            return None
        row.delivery_status = "delivered"
        row.delivery_error = ""
        row.delivered_at = row.delivered_at or now
        row.pending_code = ""
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return _row_dict(row)


def mark_delivery_failure(activation_id: int, error: str) -> dict | None:
    with SessionLocal() as db:
        row = db.get(PrtPaidActivationRow, int(activation_id))
        if row is None:
            return None
        row.delivery_status = "failed"
        row.delivery_error = (error or "Activation email delivery failed.")[:500]
        row.updated_at = _now_iso()
        # Keep pending_code so Shopify's webhook retry can resend the exact same code.
        db.commit()
        db.refresh(row)
        return _row_dict(row, include_pending_code=True)


def redeem_paid_activation(code: str, device_id: str) -> dict:
    code_hash = _hash_code(code)
    device_id = (device_id or "").strip()
    now = _now_iso()

    with SessionLocal() as db:
        row = db.scalar(
            select(PrtPaidActivationRow).where(
                PrtPaidActivationRow.code_hash == code_hash
            )
        )
        if row is None:
            raise LookupError("Paid activation code not found.")
        if row.status == "revoked":
            raise PermissionError("This paid activation code has been revoked.")
        if row.bound_device_id and row.bound_device_id != device_id:
            raise PermissionError(
                "This paid activation code is already bound to another PRT device."
            )

        purchase = prt_licensing_store.get_shopify_purchase(row.order_id, row.email)
        if purchase is None:
            raise LookupError("The purchase linked to this activation code was not found.")
        if str(purchase.get("status") or "").strip().lower() not in {"active", "paid"}:
            raise PermissionError("The subscription linked to this activation code is not active.")

        row.bound_device_id = device_id
        row.status = "redeemed"
        row.redeemed_at = row.redeemed_at or now
        row.updated_at = now
        db.commit()
        db.refresh(row)
        return _row_dict(row)


def revoke_for_order(order_id: str) -> int:
    order_id = (order_id or "").strip()
    if not order_id:
        return 0
    now = _now_iso()
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtPaidActivationRow).where(
                PrtPaidActivationRow.order_id == order_id,
                PrtPaidActivationRow.status != "revoked",
            )
        ).all()
        for row in rows:
            row.status = "revoked"
            row.pending_code = ""
            row.revoked_at = now
            row.updated_at = now
        db.commit()
        return len(rows)


def revoke_issued_for_customer(customer_id: str) -> int:
    customer_id = (customer_id or "").strip()
    if not customer_id:
        return 0
    now = _now_iso()
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtPaidActivationRow).where(
                PrtPaidActivationRow.customer_id == customer_id,
                PrtPaidActivationRow.status == "issued",
            )
        ).all()
        for row in rows:
            row.status = "revoked"
            row.pending_code = ""
            row.revoked_at = now
            row.updated_at = now
        db.commit()
        return len(rows)


def list_paid_activations(limit: int = 250) -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(PrtPaidActivationRow)
            .order_by(PrtPaidActivationRow.id.desc())
            .limit(max(1, min(int(limit), 500)))
        ).all()
        return [_row_dict(row) for row in rows]
