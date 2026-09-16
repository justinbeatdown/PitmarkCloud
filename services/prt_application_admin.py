from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from services.database import SessionLocal
from services.prt_applications import (
    PrtEarlyAccessApplication,
    PrtFunnelEvent,
    _clean,
    _clean_email,
    utcnow,
)

log = logging.getLogger("pitmark.prt_application_admin")

_ALLOWED_STATUSES = {"new", "accepted", "hold", "declined"}
_EDITABLE_IDENTITY_STATUSES = {"new", "hold"}


def set_application_status(application_id: int, status: str) -> dict:
    normalized = (status or "").strip().lower()
    if normalized not in _ALLOWED_STATUSES:
        raise ValueError("Unsupported applicant status.")

    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessApplication, int(application_id))
        if row is None:
            raise LookupError("Application not found.")

        # Applicant state is the primary operation. Persist it independently so
        # a non-critical funnel/analytics event can never prevent Accept/Hold/Decline.
        row.status = normalized
        db.commit()
        db.refresh(row)

        result = {"ok": True, "application_id": row.id, "status": row.status}

        try:
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
        except SQLAlchemyError:
            db.rollback()
            log.exception(
                "Applicant %s status changed to %s, but funnel event recording failed.",
                application_id,
                normalized,
            )

        return result


def update_application_identity(application_id: int, full_name: str, email: str) -> dict:
    clean_name = _clean(full_name, 120)
    clean_email = _clean_email(email)
    if len(clean_name) < 2:
        raise ValueError("Enter the applicant's full name.")

    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessApplication, int(application_id))
        if row is None:
            raise LookupError("Application not found.")

        status = (row.status or "new").strip().lower()
        if status not in _EDITABLE_IDENTITY_STATUSES:
            raise ValueError("Applicant identity can only be corrected while the application is New or On Hold.")

        duplicate_id = db.scalar(
            select(PrtEarlyAccessApplication.id)
            .where(
                func.lower(PrtEarlyAccessApplication.email) == clean_email,
                PrtEarlyAccessApplication.id != row.id,
            )
            .limit(1)
        )
        if duplicate_id is not None:
            raise ValueError("That email already belongs to another application.")

        row.full_name = clean_name
        row.email = clean_email
        db.commit()
        db.refresh(row)
        return {
            "ok": True,
            "application_id": row.id,
            "full_name": row.full_name,
            "email": row.email,
            "status": row.status,
        }


def delete_application(application_id: int) -> dict:
    with SessionLocal() as db:
        row = db.get(PrtEarlyAccessApplication, int(application_id))
        if row is None:
            raise LookupError("Application not found.")
        deleted_id = row.id
        db.delete(row)
        db.commit()
        return {"ok": True, "application_id": deleted_id, "deleted": True}
