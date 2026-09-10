from __future__ import annotations

from services.database import SessionLocal
from services.prt_applications import PrtEarlyAccessApplication, PrtFunnelEvent, utcnow

_ALLOWED_STATUSES = {"new", "accepted", "hold", "declined"}


def set_application_status(application_id: int, status: str) -> dict:
    normalized = (status or "").strip().lower()
    if normalized not in _ALLOWED_STATUSES:
        raise ValueError("Unsupported applicant status.")

    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessApplication, int(application_id))
        if row is None:
            raise LookupError("Application not found.")
        row.status = normalized
        db.add(
            PrtFunnelEvent(
                stage=f"application_{normalized}",
                placement="applicant-center",
                campaign=row.campaign,
                source=row.source,
                asset=row.asset,
                created_at=utcnow(),
            )
        )
        db.commit()
        return {"ok": True, "application_id": row.id, "status": row.status}


def delete_application(application_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessApplication, int(application_id))
        if row is None:
            raise LookupError("Application not found.")
        deleted_id = row.id
        db.delete(row)
        db.commit()
        return {"ok": True, "application_id": deleted_id, "deleted": True}
