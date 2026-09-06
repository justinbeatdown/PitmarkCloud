from __future__ import annotations

import logging
import os

from services.first_party_content import process_pending
from services.first_party_media import reconcile_first_party_drafts
from services.first_party_sources import (
    scan_blogs,
    scan_outreach,
    scan_products,
    scan_prt_milestone,
    scan_prt_release,
    scan_street_milestone,
)

log = logging.getLogger("pitmark.autopilot.first_party")


def _enabled() -> bool:
    return (os.getenv("PITMARK_FIRST_PARTY_AUTOPILOT_ENABLED") or "true").strip().lower() in {"1", "true", "yes", "on"}


def _limit() -> int:
    try: value = int(os.getenv("PITMARK_FIRST_PARTY_EVENTS_PER_PASS") or 4)
    except (TypeError, ValueError): value = 4
    return max(1, min(12, value))


def scan_and_generate() -> dict:
    if not _enabled():
        return {"enabled": False, "queued": 0, "processed": {"attempted": 0, "results": []}}
    scanners = {
        "shopify_products": scan_products,
        "prt_release": scan_prt_release,
        "blogs": scan_blogs,
        "outreach": scan_outreach,
        "prt_milestone": scan_prt_milestone,
        "street_team_milestone": scan_street_milestone,
    }
    details, queued = {}, 0
    for name, scanner in scanners.items():
        try:
            result = scanner(); details[name] = result; queued += int(result.get("queued") or 0)
        except Exception as exc:
            log.exception("First-party scanner %s failed", name); details[name] = {"queued": 0, "error": str(exc)[:300]}
    processed = process_pending(_limit())
    try:
        reconciled = reconcile_first_party_drafts()
    except Exception as exc:
        log.exception("First-party draft reconciliation failed")
        reconciled = {"error": str(exc)[:300]}
    return {
        "enabled": True,
        "queued": queued,
        "sources": details,
        "processed": processed,
        "reconciled": reconciled,
    }
