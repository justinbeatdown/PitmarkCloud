from __future__ import annotations

from sqlalchemy import select

from services.control_center import ShieldEvent
from services.database import SessionLocal
from services.pitmark_mail import MailMessage


def source_id_for_message(message: MailMessage) -> str:
    return f"pitmark-mail:{message.provider_message_id or message.id}"


def purge_events_for_messages(db, messages: list[MailMessage]) -> int:
    source_ids = [source_id_for_message(message) for message in messages]
    if not source_ids:
        return 0
    events = list(
        db.scalars(
            select(ShieldEvent).where(ShieldEvent.source_message_id.in_(source_ids))
        ).all()
    )
    for event in events:
        db.delete(event)
    return len(events)


def purge_orphaned_mail_events() -> dict:
    """Remove live-queue Shield records whose Pitmark Mail message no longer exists.

    SecurityAuditEvent records are intentionally retained as historical audit data.
    """
    with SessionLocal() as db:
        live_messages = list(
            db.scalars(
                select(MailMessage).where(MailMessage.direction == "inbound")
            ).all()
        )
        live_source_ids = {source_id_for_message(message) for message in live_messages}
        events = list(
            db.scalars(
                select(ShieldEvent).where(
                    ShieldEvent.source_message_id.like("pitmark-mail:%")
                )
            ).all()
        )
        orphaned = [
            event for event in events
            if event.source_message_id not in live_source_ids
        ]
        for event in orphaned:
            db.delete(event)
        if orphaned:
            db.commit()
        return {
            "checked": len(events),
            "live_messages": len(live_source_ids),
            "deleted": len(orphaned),
        }
