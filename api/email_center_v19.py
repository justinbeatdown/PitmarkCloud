from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from services.control_auth import require_control_user
from services.database import SessionLocal
from services import pitmark_mail as base
from services.pitmark_mail_attachments import list_resend_attachments, stored_attachments
from services.pitmark_mail_preferences import get_preference, list_preferences, save_preference
from services.pitmark_mail_rich import draft_attachments, save_rich_draft, send_rich_message
from utils.security import enforce_rate_limit

router = APIRouter()


def auth(request: Request):
    return require_control_user(request, None)


class AttachmentPayload(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    content: str


class RichCompose(BaseModel):
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    reply_to: list[str] = Field(default_factory=list)
    from_identity: str = ""
    subject: str = ""
    text: str = ""
    html: str = ""
    reply_to_message_id: int | None = None
    attachments: list[AttachmentPayload] = Field(default_factory=list)


class RichDraft(BaseModel):
    id: int | None = None
    to: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    bcc: list[str] = Field(default_factory=list)
    from_identity: str = ""
    subject: str = ""
    text: str = ""
    html: str = ""
    attachments: list[AttachmentPayload] = Field(default_factory=list)


class SignatureUpdate(BaseModel):
    signature_html: str = ""
    signature_enabled: bool = True


@router.post("/send-rich")
def send_rich(req: RichCompose, request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-send-rich", 20, 300)
    try:
        return send_rich_message(
            to=req.to,
            cc=req.cc,
            bcc=req.bcc,
            reply_to=req.reply_to,
            from_identity=req.from_identity,
            subject=req.subject,
            text=req.text,
            html=req.html,
            reply_to_message_id=req.reply_to_message_id,
            attachments=[x.model_dump() for x in req.attachments],
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/drafts-rich")
def save_draft_rich(req: RichDraft, request: Request):
    auth(request)
    try:
        return save_rich_draft(
            to=req.to,
            cc=req.cc,
            bcc=req.bcc,
            from_identity=req.from_identity,
            subject=req.subject,
            text=req.text,
            html=req.html,
            draft_id=req.id,
            attachments=[x.model_dump() for x in req.attachments],
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/drafts/{message_id}/attachments")
def rich_draft_attachments(message_id: int, request: Request):
    auth(request)
    return draft_attachments(message_id)


@router.get("/preferences")
def preferences(request: Request):
    auth(request)
    return list_preferences()


@router.get("/preferences/{identity_key}")
def preference(identity_key: str, request: Request):
    auth(request)
    return get_preference(identity_key)


@router.put("/preferences/{identity_key}")
def update_preference(identity_key: str, req: SignatureUpdate, request: Request):
    auth(request)
    return save_preference(
        identity_key,
        signature_html=req.signature_html,
        signature_enabled=req.signature_enabled,
    )


@router.get("/messages/{message_id}/attachments")
def message_attachments(message_id: int, request: Request):
    auth(request)
    with SessionLocal() as db:
        message = db.get(base.MailMessage, message_id)
        if not message:
            raise HTTPException(404, "Mail message not found.")

        # Drafts are locally stored so the composer can restore them.
        if message.status == "draft":
            return [
                {
                    "filename": x.get("filename"),
                    "content_type": x.get("content_type"),
                    "size": x.get("size"),
                    "content": x.get("content"),
                }
                for x in stored_attachments(message)
            ]

        local = stored_attachments(message)
        if local:
            return [
                {
                    "filename": x.get("filename"),
                    "content_type": x.get("content_type"),
                    "size": x.get("size"),
                }
                for x in local
            ]

        return list_resend_attachments(
            message.provider_message_id or "",
            inbound=message.direction == "inbound",
        )
