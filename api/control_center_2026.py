from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.control_auth import require_control_user
from services.founders_race import leaderboard
from services.prt_application_admin import set_application_status
from services.prt_applications import application_role_from_placement, application_summary, list_applications
from services.prt_feedback import list_feedback, summary as feedback_summary, update_status as update_feedback_status
from services.prt_licensing_store import list_early_access_invites
from utils.config import settings

router = APIRouter()


class StatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=32)


def _auth(request: Request):
    return require_control_user(request, None)


def _application_row(row: dict) -> dict:
    return {
        **row,
        "role": application_role_from_placement(row.get("placement")),
    }


def _tester_rollup(invites: list[dict]) -> dict:
    status_counts = Counter(str(row.get("status") or "unknown").lower() for row in invites)
    tester_counts = Counter(str(row.get("tester_status") or "unknown").lower() for row in invites)
    active = [
        row
        for row in invites
        if str(row.get("status") or "").lower() == "redeemed"
        and str(row.get("tester_status") or "").lower() in {"active", "completed"}
    ]
    return {
        "total_invites": len(invites),
        "active": len(active),
        "active_testers": len(active),
        "issued": status_counts.get("issued", 0),
        "redeemed": status_counts.get("redeemed", 0),
        "revoked": status_counts.get("revoked", 0),
        "expired": status_counts.get("expired", 0),
        "tester_status": dict(tester_counts),
    }


def _race_rollup(rows: list[dict]) -> dict:
    return {
        "racers": len(rows),
        "qualified": sum(int(row.get("qualified") or 0) for row in rows),
        "pending": sum(int(row.get("pending") or 0) for row in rows),
        "flagged": sum(int(row.get("flagged") or 0) for row in rows),
    }


@router.get("/api/control/ops/overview")
def ops_overview(request: Request):
    _auth(request)
    applications = list_applications(limit=200)
    invites = list_early_access_invites(limit=500)
    race = leaderboard()
    feedback = feedback_summary()
    app_counts = Counter(str(row.get("status") or "new").lower() for row in applications)
    app_summary = application_summary()
    return {
        "version": settings.app_version,
        "applications": {
            "total": len(applications),
            "new": app_counts.get("new", 0),
            "accepted": app_counts.get("accepted", 0),
            "hold": app_counts.get("hold", 0),
            "declined": app_counts.get("declined", 0),
            "last_application_at": app_summary.get("quick_apply_last_application_at"),
            "last_7d": app_summary.get("quick_apply_applications_7d", 0),
        },
        "testers": _tester_rollup(invites),
        "founders_race": _race_rollup(race),
        "feedback": feedback,
    }


@router.get("/api/control/ops/testers")
def ops_testers(request: Request, limit: int = 80):
    _auth(request)
    safe_limit = max(1, min(int(limit), 200))
    applications = [_application_row(row) for row in list_applications(limit=safe_limit)]
    invites = list_early_access_invites(limit=500)
    return {
        "applications": applications,
        "application_counts": dict(Counter(str(row.get("status") or "new").lower() for row in applications)),
        "invites": invites,
        "tester_summary": _tester_rollup(invites),
    }


@router.patch("/api/control/ops/testers/{application_id}/status")
def ops_tester_status(application_id: int, payload: StatusUpdate, request: Request):
    _auth(request)
    try:
        result = set_application_status(application_id, payload.status)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if str(payload.status or "").strip().lower() != "accepted":
        return result

    # Control Center acceptance is a complete onboarding action: status, code,
    # and acceptance email. The legacy Applicant Center remains available as a
    # fallback/admin view, but the owner should not need a second screen.
    from api.early_access_admin import _acceptance_message, _application_by_id, _has_invite_for_email
    from services.pitmark_mail_identities import send_message as send_mail
    from services.prt_licensing_store import PrtEarlyAccessInviteRow, create_early_access_invite
    from services.database import SessionLocal

    row = _application_by_id(application_id)
    if not row:
        raise HTTPException(404, "Application disappeared after acceptance.")
    email = str(row.get("email") or "").strip().lower()
    name = str(row.get("full_name") or "Applicant").strip()
    if not email:
        raise HTTPException(409, "Applicant was accepted but has no email address for onboarding.")
    if _has_invite_for_email(email):
        return {**result, "onboarding_status": "already_issued", "onboarding_sent": False}

    invite = create_early_access_invite(
        applicant_name=name,
        email=email,
        discord=str(row.get("discord_username") or "").strip(),
        notes=f"Issued automatically from Control Center application #{application_id}",
        expires_days=14,
    )
    try:
        send_mail(
            to=[email],
            subject="You’re In — Welcome to PRT Early Access 🏁",
            text=_acceptance_message(name, invite["code"], row.get("placement") or "quick-apply"),
            from_identity="justin",
        )
    except Exception as exc:
        # A generated activation code cannot be recovered from its stored hash.
        # Remove the unsent invite so pressing Accept again can safely retry with
        # a fresh code instead of leaving a stranded applicant.
        with SessionLocal() as db:
            doomed = db.get(PrtEarlyAccessInviteRow, int(invite["id"]))
            if doomed is not None:
                db.delete(doomed)
                db.commit()
        raise HTTPException(502, f"Applicant accepted, but onboarding email failed: {exc}") from exc

    return {
        **result,
        "onboarding_status": "sent",
        "onboarding_sent": True,
        "invite_id": invite["id"],
    }


@router.get("/api/control/ops/founders-race")
def ops_founders_race(request: Request):
    _auth(request)
    rows = leaderboard()
    return {
        "summary": _race_rollup(rows),
        "leaderboard": rows,
    }


@router.get("/api/control/ops/feedback")
def ops_feedback(request: Request, status: str | None = None, limit: int = 120):
    _auth(request)
    safe_limit = max(1, min(int(limit), 300))
    return {
        "summary": feedback_summary(),
        "items": list_feedback(limit=safe_limit, status=status),
    }


@router.patch("/api/control/ops/feedback/{feedback_id}/status")
def ops_feedback_status(feedback_id: int, payload: StatusUpdate, request: Request):
    _auth(request)
    try:
        result = update_feedback_status(feedback_id, payload.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "Feedback item not found.")
    return result
