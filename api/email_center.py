from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.control_auth import require_control_user
from services.pitmark_mail import (
    get_thread,
    ingest_resend_event,
    list_threads,
    save_draft,
    send_message,
    status,
    verify_svix_signature,
)
from utils.security import enforce_rate_limit

router = APIRouter()
public_router = APIRouter()


def auth(request: Request):
    return require_control_user(request, None)


class MailCompose(BaseModel):
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    reply_to: list[str] = Field(default_factory=list)
    subject: str = ""
    text: str = ""
    html: str = ""
    reply_to_message_id: int | None = None


class MailDraft(BaseModel):
    id: int | None = None
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    subject: str = ""
    text: str = ""
    html: str = ""


@router.get("/status")
def mail_status(request: Request):
    auth(request)
    return status()


@router.get("/threads")
def mail_threads(request: Request, folder: str = "inbox", limit: int = 100):
    auth(request)
    return list_threads(folder=folder, limit=limit)


@router.get("/threads/{thread_id}")
def mail_thread(thread_id: int, request: Request):
    auth(request)
    result = get_thread(thread_id, mark_read=True)
    if not result:
        raise HTTPException(404, "Mail thread not found.")
    return result


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
            subject=req.subject,
            text=req.text,
            html=req.html,
            draft_id=req.id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@public_router.post("/api/webhooks/resend")
async def resend_webhook(request: Request):
    raw = await request.body()
    if not verify_svix_signature(raw, request.headers):
        raise HTTPException(401, "Invalid Resend webhook signature.")
    try:
        event = await request.json()
        return ingest_resend_event(event)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
