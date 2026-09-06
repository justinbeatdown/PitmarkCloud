from __future__ import annotations

import json
import logging
import re

from sqlalchemy import select

from services.autopilot_ai import compose_with_ai
from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.first_party_models import FirstPartyEvent, GOALS, PLATFORMS, existing_platforms, pending_ids, snapshot

log = logging.getLogger("pitmark.autopilot.first_party.content")


def _clean(value: str | None, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()[:limit]


def _prompt(event: dict, platform: str) -> str:
    special = ""
    if platform == "discord":
        special = "Use clean Discord Markdown and a concise changelog/update format. Do not invent patch notes."
    elif event["event_type"] == "shopify_product":
        special = "This is a real new product drop. Promote it without fake urgency or invented specs."
    elif event["event_type"] == "blog_publish":
        special = "Promote the published article without inventing claims about what it contains."
    elif event["event_type"] in {"partnership", "street_team"}:
        special = "The supplied relationship/status is confirmed, but do not invent deliverables or quotes."
    return f"""Create a Pitmark Racing Co. post from a verified first-party Pitmark event.
Event type: {event['event_type']}
Title: {event['title']}
Details: {event['summary'] or 'No additional details supplied.'}
Public URL: {event['url'] or 'none supplied'}
Verified payload: {json.dumps(event.get('payload') or {}, ensure_ascii=False, default=str)[:5000]}
Use only these facts. {special}
If a public URL is supplied, include it naturally when appropriate. Return finished copy only."""


def _fallback(event: dict, platform: str) -> str:
    title, summary, url = event["title"], _clean(event.get("summary")), (event.get("url") or "").strip()
    et = event["event_type"]
    if et == "shopify_product":
        text = f"New Pitmark drop: {title}.{f' {url}' if url else ''} 🏁"
        return text[:275] if platform == "x" else f"New drop from Pitmark Racing Co. 🏁\n\n{title} is live now.{f'\n\n{url}' if url else ''}\n\nLeave Your Mark."
    if et == "prt_release":
        if platform == "discord":
            return f"## 🏁 {title}\n\n{summary or 'A new Pitmark Racing Tools build is live.'}{f'\n\n**PRT:** {url}' if url else ''}"
        text = f"🏁 {title}. {summary} {url}".strip()
        return text[:275] if platform == "x" else f"🏁 {title}\n\n{summary}{f'\n\n{url}' if url else ''}"
    if et == "blog_publish":
        return f"New on Pitmark: {title}\n\n{summary}{f'\n\nRead it here: {url}' if url else ''}"
    if et == "partnership":
        return f"Pitmark Racing Co. community update 🏁\n\n{summary or title}\n\nRacing grows when the community grows together."
    if et == "street_team":
        return f"The Pitmark Street Team keeps growing. 🏁\n\n{summary or title}\n\nLeave Your Mark."
    return f"A Pitmark milestone worth celebrating. 🏁\n\n{summary or title}{f'\n\n{url}' if url else ''}"


def process_event(event_id: int) -> dict:
    event = snapshot(event_id)
    if not event:
        return {"ok": False, "event_id": event_id, "error": "event not found"}
    desired = PLATFORMS.get(event["event_type"], ("facebook", "instagram", "x"))
    goal = GOALS.get(event["event_type"], "community")
    existing = existing_platforms(event_id)
    generated, warnings = [], []
    for platform in desired:
        if platform in existing:
            continue
        try:
            body = compose_with_ai(platform=platform, goal=goal, prompt=_prompt(event, platform), tone="pitmark").body.strip()
        except Exception as exc:
            warnings.append(f"{platform}:{type(exc).__name__}")
            body = _fallback(event, platform)
        if body:
            generated.append((platform, body))

    with SessionLocal() as db:
        row = db.get(FirstPartyEvent, event_id)
        if not row:
            return {"ok": False, "event_id": event_id, "error": "event disappeared"}
        source = f"firstparty:{event_id}"
        current = set(db.scalars(select(SocialPost.platform).where(SocialPost.source == source)).all())
        created = 0
        for platform, body in generated:
            if platform in current:
                continue
            db.add(SocialPost(
                platform=platform, title=row.title[:180], body=body, content_type=goal, source=source,
                risk="copy_only" if platform == "discord" else "low", status="pending", media_url=row.media_url,
            ))
            current.add(platform); created += 1
        row.attempts = (row.attempts or 0) + 1
        row.draft_count = len(current); row.status = "processed"; row.processed_at = utcnow(); row.updated_at = utcnow()
        row.last_error = ("AI fallback used: " + "; ".join(warnings))[:1000] if warnings else None
        db.commit()
    return {"ok": True, "event_id": event_id, "created": created, "platforms": sorted(current), "fallbacks": warnings}


def process_pending(limit: int = 4) -> dict:
    results = []
    for event_id in pending_ids(limit):
        try:
            results.append(process_event(event_id))
        except Exception as exc:
            log.exception("First-party content event %s failed", event_id)
            with SessionLocal() as db:
                row = db.get(FirstPartyEvent, event_id)
                if row:
                    row.attempts = (row.attempts or 0) + 1; row.status = "failed"; row.last_error = str(exc)[:1000]; row.updated_at = utcnow(); db.commit()
            results.append({"ok": False, "event_id": event_id, "error": str(exc)[:240]})
    return {"attempted": len(results), "results": results}
