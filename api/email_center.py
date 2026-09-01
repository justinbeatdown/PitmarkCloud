from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services import google_gmail
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
from services.pitmark_mail_auto_reply import (
    list_auto_reply_settings,
    process_auto_replies,
    save_auto_reply_setting,
)
from services.shield_mail import (
    decorate_thread,
    decorate_threads,
    mark_thread_spam,
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


class MailAutoReplyUpdate(BaseModel):
    enabled: bool = True
    body: str = ""


class MailBulkDelete(BaseModel):
    thread_ids: list[int] = Field(default_factory=list, min_length=1, max_length=200)


@router.get("/status")
def mail_status(request: Request):
    auth(request)
    result = status()
    # IMPORTANT: normal UI reads must stay fast. Gmail synchronization and
    # Shield scanning are handled by Pitmark Cloud's background sync worker;
    # they must not block the Control Center status request.
    result["workspace_setup"] = google_gmail.workspace_setup_status()
    return result


@router.post("/workspace/setup")
def mail_workspace_setup(request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-workspace-setup", 5, 300)
    return google_gmail.ensure_workspace_setup(force=True)


@router.get("/auto-replies")
def mail_auto_replies(request: Request):
    auth(request)
    return list_auto_reply_settings()


@router.put("/auto-replies/{department}")
def mail_auto_reply_update(department: str, req: MailAutoReplyUpdate, request: Request):
    auth(request)
    try:
        return save_auto_reply_setting(department, enabled=req.enabled, body=req.body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/auto-replies/run")
def mail_auto_reply_run(request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-auto-reply-run", 10, 300)
    return process_auto_replies()


@router.get("/identities")
def mail_identities(request: Request):
    auth(request)
    return list_identities()


@router.get("/threads")
def mail_threads(request: Request, folder: str = "inbox", limit: int = 100):
    auth(request)
    # Read the already-synchronized Cloud mailbox only. Previous builds forced
    # a Gmail sync + Shield rescan here, making every inbox refresh wait on
    # remote API work and a mailbox-wide security pass.
    return decorate_threads(list_threads(folder=folder, limit=limit))


@router.get("/threads/{thread_id}")
def mail_thread(thread_id: int, request: Request):
    auth(request)
    # Opening a conversation must never trigger a mailbox-wide sync/rescan.
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


@router.post("/threads/bulk-delete")
def mail_bulk_delete(req: MailBulkDelete, request: Request):
    auth(request)
    enforce_rate_limit(request, "mail-bulk-delete", 20, 300)
    unique_ids = list(dict.fromkeys(int(value) for value in req.thread_ids if int(value) > 0))
    if not unique_ids:
        raise HTTPException(400, "No valid mail conversations were selected.")

    deleted: list[int] = []
    missing: list[int] = []
    failed: list[dict] = []
    for thread_id in unique_ids:
        try:
            if delete_thread(thread_id):
                deleted.append(thread_id)
            else:
                missing.append(thread_id)
        except RuntimeError as exc:
            failed.append({"thread_id": thread_id, "error": str(exc)})

    if failed and not deleted:
        raise HTTPException(502, f"Bulk delete failed for {len(failed)} conversation(s).")
    return {
        "ok": not failed,
        "requested": len(unique_ids),
        "deleted": deleted,
        "deleted_count": len(deleted),
        "missing": missing,
        "failed": failed,
    }


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
