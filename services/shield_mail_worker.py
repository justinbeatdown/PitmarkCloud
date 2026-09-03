"""Lean background Gmail -> Shield worker.

Control Center no longer acts as an inbox, so the always-on worker should do only
what Shield and mail automation need. Interactive/manual mail APIs continue to use
the existing mail services unchanged.
"""
from __future__ import annotations

from services.pitmark_mail import sync_gmail_inbox
from services.shield_mail import protect_message


def sync_gmail_shield_worker(limit: int = 25) -> dict:
    result = sync_gmail_inbox(limit=max(5, min(int(limit), 25)))
    new_message_ids = [int(value) for value in (result.get("new_message_ids") or [])]

    protected = 0
    for message_id in new_message_ids:
        if protect_message(message_id):
            protected += 1
    result["shield_protected"] = protected

    # The old mail-client worker scanned a large set of historical messages for
    # auto-replies every single poll, even when Gmail had nothing new. Only run
    # the auto-reply pass when new mail was actually ingested, and keep its scan
    # proportional to the new batch.
    if new_message_ids:
        from services.pitmark_mail_auto_reply import process_auto_replies

        reply_limit = max(2, min(len(new_message_ids) * 2, 12))
        result["auto_replies"] = process_auto_replies(limit=reply_limit)
    else:
        result["auto_replies"] = {"sent": 0, "skipped": 0, "errors": 0}

    return result
