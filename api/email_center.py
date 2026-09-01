from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.control_auth import require_control_user
from services.pitmark_mail import (
    get_thread,
    list_threads,
)
from services.pitmark_mail_delete import delete_draft, delete_thread
from services.pitmark_mail_identities import (
    list_identities,
    save_draft,
    send_message,
    status,
)
from services.shield_mail import (
    decorate_thread,
    decorate_threads,
    mark_thread_spam,
    rescan_pitmark_mail,
    sync_unprotected_mail,
)
from utils.security import enforce_rate_limit

router = APIRouter()


def auth(request: Request):
    return require_control_user(request, None)


class MailCompose(BaseModel):
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    reply_to: list[str] = Field(default_factory=list)
    from_identity: str = ""
    subject: str = ""
    text: str = ""
    html: str = ""
    reply_to_message_id: int | None = None


class MailDraft(BaseModel):
    id: int | None = None
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    from_identity: str = ""
    subject: str = ""
    text: str = ""
    html: str = ""


@router.get("/status")
def mail_status(request: Request):
    auth(request)
    result = status()
    protection = sync_unprotected_mail()
    result["shield_rescan"] = rescan_pitmark_mail()
    result["shield_protection"] = protection
    return result


@router.get("/identities")
def mail_identities(request: Request):
    auth(request)
    return list_identities()


@router.get("/threads")
def mail_threads(request: Request, folder: str = "inbox", limit: int = 100):
    auth(request)
    # Backfill older inbound messages once so Shield covers the mailbox that
    # existed before this integration release.
    if (folder or "inbox").lower().strip() == "inbox":
        sync_unprotected_mail()
        rescan_pitmark_mail()
    return decorate_threads(list_threads(folder=folder, limit=limit))


@router.get("/threads/{thread_id}")
def mail_thread(thread_id: int, request: Request):
    auth(request)
    sync_unprotected_mail()
    rescan_pitmark_mail()
    result = decorate_thread(get_thread(thread_id, mark_read=True))
    if not result:
        raise HTTPException(404, "Mail thread not found.")
    return result


@router.post("/threads/{thread_id}/spam")
def mail_mark_thread_spam(thread_id: int, request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-spam-training", 30, 300)
    try:
        return mark_thread_spam(thread_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/threads/{thread_id}")
def mail_delete_thread(thread_id: int, request: Request):
    auth(request)
    try:
        if not delete_thread(thread_id):
            raise HTTPException(404, "Mail thread not found.")
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "deleted_thread_id": thread_id}


@router.delete("/drafts/{message_id}")
def mail_delete_draft(message_id: int, request: Request):
    auth(request)
    try:
        if not delete_draft(message_id):
            raise HTTPException(404, "Mail draft not found.")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "deleted_draft_id": message_id}


@router.post("/send")
def mail_send(req: MailCompose, request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-send", 20, 300)
    try:
        return send_message(
            to=req.to,
            cc=req.cc,
            bcc=req.bcc,
            reply_to=req.reply_to,
            from_identity=req.from_identity,
            subject=req.subject,
            text=req.text,
            html=req.html,
            reply_to_message_id=req.reply_to_message_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/drafts")
def mail_save_draft(req: MailDraft, request: Request):
    auth(request)
    try:
        return save_draft(
            to=req.to,
            cc=req.cc,
            bcc=req.bcc,
            from_identity=req.from_identity,
            subject=req.subject,
            text=req.text,
            html=req.html,
            draft_id=req.id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
