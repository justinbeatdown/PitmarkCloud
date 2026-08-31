from __future__ import annotations

from sqlalchemy import select

from services.database import SessionLocal
from services.pitmark_mail import MailMessage, MailThread, utcnow


def _repair_thread(db, thread_id: int) -> None:
    thread = db.get(MailThread, thread_id)
    if not thread:
        return
    messages = list(
        db.scalars(
            select(MailMessage)
            .where(MailMessage.thread_id == thread_id)
            .order_by(MailMessage.created_at.asc())
        ).all()
    )
    if not messages:
        db.delete(thread)
        return
    latest = messages[-1]
    thread.last_message_at = latest.created_at or utcnow()
    thread.updated_at = utcnow()
    thread.unread_count = sum(
        1 for msg in messages
        if msg.direction == "inbound" and not bool(msg.is_read)
    )


def delete_thread(thread_id: int) -> bool:
    with SessionLocal() as db:
        thread = db.get(MailThread, thread_id)
        if not thread:
            return False
        messages = list(
            db.scalars(
                select(MailMessage).where(MailMessage.thread_id == thread_id)
            ).all()
        )
        for msg in messages:
            db.delete(msg)
        db.delete(thread)
        db.commit()
        return True


def delete_draft(message_id: int) -> bool:
    with SessionLocal() as db:
        msg = db.get(MailMessage, message_id)
        if not msg:
            return False
        if msg.status != "draft":
            raise ValueError("Only draft messages can be deleted from the draft endpoint.")
        thread_id = msg.thread_id
        db.delete(msg)
        db.flush()
        _repair_thread(db, thread_id)
        db.commit()
        return True
