from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select

from services import shopify_service
from services.control_center import BlogDraft, OutreachContact, ShopifyPublishRecord
from services.database import SessionLocal
from services.first_party_models import get_state, queue_event, set_state
from utils.config import settings

log = logging.getLogger("pitmark.autopilot.first_party.sources")
PARTNER_STAGES = {"partner", "partnered", "active_partner", "supporter", "accepted", "confirmed", "live"}
STREET_STAGES = {"accepted", "active", "confirmed", "approved", "member", "live"}
PRT_MILESTONES = (5, 10, 25, 50, 100, 250, 500, 1000)
STREET_MILESTONES = (5, 10, 25, 50, 100, 250)


def env_int(name: str, default: int, low: int = 1, high: int = 720) -> int:
    try: value = int(os.getenv(name) or default)
    except (TypeError, ValueError): value = default
    return max(low, min(high, value))


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def clean(value: str | None, limit: int = 700) -> str:
    text = html.unescape(str(value or "")); text = re.sub(r"<[^>]+>", " ", text); text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError: return None


def recent(value: Any, hours: int) -> bool:
    dt = parse_dt(value)
    if not dt: return False
    age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600
    return -1 <= age <= hours


def recent_products() -> tuple[list[dict], str]:
    try:
        data = shopify_service.graphql("""
        query PitmarkAutopilotRecentProducts {
          products(first: 60, sortKey: CREATED_AT, reverse: true, query: "status:active") {
            nodes { id title handle createdAt updatedAt publishedAt productType tags featuredMedia { preview { image { url } } } }
          }
        }""")
        out = []
        for p in ((data.get("products") or {}).get("nodes") or []):
            image = ((((p.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url") or "").strip()
            out.append({"id": p.get("id"), "title": p.get("title"), "handle": p.get("handle"), "created_at": p.get("createdAt"),
                        "updated_at": p.get("updatedAt"), "published_at": p.get("publishedAt"), "product_type": p.get("productType"), "tags": p.get("tags") or [],
                        "images": [{"src": image}] if image else [], "body_html": ""})
        if out: return out, "shopify_admin"
    except Exception as exc:
        log.warning("Admin product scan failed; public fallback: %s", exc)

    base = (settings.pitmark_public_store_url or "https://pitmarkracing.com").rstrip("/")
    products, seen = [], set()
    for page in range(1, 4):
        r = httpx.get(f"{base}/products.json", params={"limit": 250, "page": page}, timeout=25, follow_redirects=True,
                      headers={"User-Agent": "PitmarkAutopilot-FirstParty/1.0"})
        r.raise_for_status(); batch = (r.json() or {}).get("products") or []
        if not batch: break
        new = 0
        for p in batch:
            key = str(p.get("id") or p.get("handle") or "")
            if key and key not in seen: seen.add(key); products.append(p); new += 1
        if len(batch) < 250 or new == 0: break
    return products, "public_catalog"


def scan_products() -> dict:
    base = (settings.pitmark_public_store_url or "https://pitmarkracing.com").rstrip("/"); hours = env_int("PITMARK_FIRST_PARTY_PRODUCT_BACKFILL_HOURS", 72, 1, 336)
    products, source = recent_products(); queued = 0
    for p in products:
        when = p.get("published_at") or p.get("created_at") or p.get("updated_at")
        if not recent(when, hours): continue
        pid, title, handle = str(p.get("id") or p.get("handle") or "").strip(), clean(p.get("title"), 240), str(p.get("handle") or "").strip()
        if not pid or not title or not handle: continue
        images = p.get("images") or []; media = (images[0].get("src") or "").strip() if images and isinstance(images[0], dict) else None
        tags = p.get("tags") or []; tag_text = ", ".join(str(x) for x in tags[:8]) if isinstance(tags, list) else str(tags)
        summary = " | ".join(x for x in [clean(p.get("product_type"), 120), clean(p.get("body_html"), 500), f"Tags: {tag_text}" if tag_text else ""] if x)
        _, created = queue_event(event_key=f"shopify_product:{pid}", event_type="shopify_product", title=title, summary=summary,
                                 url=f"{base}/products/{handle}", media_url=media,
                                 payload={"product_id": pid, "handle": handle, "published_at": when, "product_type": p.get("product_type"), "tags": tags, "catalog_source": source})
        queued += int(created)
    return {"scanned": len(products), "queued": queued, "source": source, "window_hours": hours}


def r2_manifest_url() -> str:
    if not bool(getattr(settings, "prt_r2_enabled", False)): return ""
    base = (getattr(settings, "prt_r2_public_base_url", "") or "").strip().rstrip("/")
    key = (getattr(settings, "prt_r2_installer_key", "prt/PRT-Setup-Latest.exe") or "").strip().lstrip("/")
    prefix = key.rsplit("/", 1)[0] if "/" in key else ""
    return f"{base}/{prefix + '/' if prefix else ''}latest.json" if base else ""


def load_manifest() -> tuple[dict, str]:
    target = r2_manifest_url()
    if target:
        try:
            r = httpx.get(target, timeout=15, follow_redirects=True, headers={"User-Agent": "PitmarkAutopilot-FirstParty/1.0"}); r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and data.get("version"): return data, "r2"
        except Exception as exc: log.warning("R2 manifest scan failed: %s", exc)
    local = Path(__file__).resolve().parents[1] / "api" / "downloads" / "latest.json"
    if not local.exists(): raise RuntimeError("PRT update manifest unavailable")
    return json.loads(local.read_text(encoding="utf-8-sig")), "local"


def scan_prt_release() -> dict:
    manifest, source = load_manifest(); version = clean(str(manifest.get("version") or ""), 40)
    if not version: return {"queued": 0, "source": source}
    previous = get_state("prt_manifest_version"); notes = clean(str(manifest.get("notes") or ""), 1200)
    if previous is None:
        set_state("prt_manifest_version", version)
        if source != "r2" or not env_bool("PITMARK_FIRST_PARTY_PRT_BOOTSTRAP_DRAFT", True):
            return {"queued": 0, "version": version, "source": source, "bootstrapped": True}
    elif previous == version:
        return {"queued": 0, "version": version, "source": source}
    _, created = queue_event(event_key=f"prt_release:{version}", event_type="prt_release", title=f"PRT v{version} released",
                             summary=notes or "A new Pitmark Racing Tools build is live for Early Access testers.",
                             url="https://prt.pitmarkracing.com", media_url="https://prt.pitmarkracing.com/prt-app-preview.png",
                             payload={"version": version, "notes": notes, "required": manifest.get("required"), "manifest_source": source})
    set_state("prt_manifest_version", version)
    return {"queued": int(created), "version": version, "source": source, "previous": previous}


def article_details(article_id: str) -> dict:
    data = shopify_service.graphql("""query P($id:ID!){node(id:$id){... on Article{id title handle blog{handle} image{originalSrc}}}}""", {"id": article_id})
    node = data.get("node"); return node if isinstance(node, dict) else {}


def scan_blogs() -> dict:
    hours = env_int("PITMARK_FIRST_PARTY_BLOG_BACKFILL_HOURS", 72, 1, 336)
    with SessionLocal() as db: rows = list(db.scalars(select(BlogDraft).where(BlogDraft.status == "published").order_by(BlogDraft.id.desc()).limit(30)).all())
    queued = 0
    for d in rows:
        if not recent(d.updated_at, hours): continue
        with SessionLocal() as db: rec = db.scalar(select(ShopifyPublishRecord).where(ShopifyPublishRecord.draft_id == d.id))
        if not rec: continue
        url, media = (rec.url or "").strip() or None, (d.featured_image_url or "").strip() or None
        if (not url or not media) and rec.shopify_article_id:
            try:
                a = article_details(rec.shopify_article_id); bh = ((a.get("blog") or {}).get("handle") or "").strip(); ah = (a.get("handle") or "").strip()
                if not url and bh and ah: url = f"{(settings.pitmark_public_store_url or 'https://pitmarkracing.com').rstrip('/')}/blogs/{bh}/{ah}"
                if not media: media = (((a.get("image") or {}).get("originalSrc") or "").strip() or None)
            except Exception as exc: log.warning("Blog URL/image resolve failed: %s", exc)
        _, created = queue_event(event_key=f"blog_publish:{d.id}", event_type="blog_publish", title=d.title,
                                 summary=clean(d.seo_description or d.body_html, 700), url=url, media_url=media,
                                 payload={"draft_id": d.id, "shopify_article_id": rec.shopify_article_id})
        queued += int(created)
    return {"scanned": len(rows), "queued": queued, "window_hours": hours}


def is_street(row: OutreachContact) -> bool:
    text = " ".join([str(row.contact_type or ""), str(row.name or ""), str(row.organization or "")]).lower()
    return any(x in text for x in ("street team", "street_team", "street-team"))


def scan_outreach() -> dict:
    hours = env_int("PITMARK_FIRST_PARTY_OUTREACH_BACKFILL_HOURS", 72, 1, 336)
    with SessionLocal() as db: rows = list(db.scalars(select(OutreachContact).order_by(OutreachContact.id.desc()).limit(150)).all())
    queued = 0
    for row in rows:
        if not recent(row.updated_at, hours): continue
        stage = str(row.stage or "").strip().lower(); street = is_street(row)
        if street:
            if stage not in STREET_STAGES: continue
            et, title, summary = "street_team", "Pitmark Street Team update", f"A Street Team member reached {stage.replace('_',' ')} status in Pitmark's outreach system."
        else:
            if stage not in PARTNER_STAGES: continue
            display = clean(row.organization or row.name, 180) or "Pitmark community partner"
            et, title, summary = "partnership", f"Pitmark partnership update: {display}", f"{display} reached {stage.replace('_',' ')} status in Pitmark's partnership/outreach system."
        _, created = queue_event(event_key=f"outreach:{row.id}:{stage}", event_type=et, title=title, summary=summary,
                                 payload={"outreach_id": row.id, "stage": stage, "contact_type": row.contact_type})
        queued += int(created)
    return {"scanned": len(rows), "queued": queued, "window_hours": hours}


def threshold(count: int, values: tuple[int, ...]) -> int:
    return max((x for x in values if count >= x), default=0)


def scan_prt_milestone() -> dict:
    from services.prt_analytics import PrtInstallEvent
    with SessionLocal() as db: count = int(db.scalar(select(func.count()).select_from(PrtInstallEvent)) or 0)
    current = threshold(count, PRT_MILESTONES); state = get_state("prt_install_milestone")
    if state is None: set_state("prt_install_milestone", str(current)); return {"count": count, "queued": 0, "bootstrapped": True}
    if current <= int(state or 0) or current <= 0: return {"count": count, "queued": 0}
    _, created = queue_event(event_key=f"prt_milestone:{current}", event_type="prt_milestone", title=f"PRT reaches {current} installs",
                             summary=f"Pitmark Racing Tools has recorded at least {current} unique installs in Pitmark Cloud.",
                             url="https://prt.pitmarkracing.com", media_url="https://prt.pitmarkracing.com/prt-app-preview.png",
                             payload={"install_count": count, "milestone": current})
    set_state("prt_install_milestone", str(current)); return {"count": count, "queued": int(created)}


def scan_street_milestone() -> dict:
    with SessionLocal() as db: rows = list(db.scalars(select(OutreachContact)).all())
    count = len([r for r in rows if is_street(r) and str(r.stage or "").strip().lower() in STREET_STAGES]); current = threshold(count, STREET_MILESTONES)
    state = get_state("street_team_milestone")
    if state is None: set_state("street_team_milestone", str(current)); return {"count": count, "queued": 0, "bootstrapped": True}
    if current <= int(state or 0) or current <= 0: return {"count": count, "queued": 0}
    _, created = queue_event(event_key=f"street_team_milestone:{current}", event_type="street_team_milestone", title=f"Pitmark Street Team reaches {current} members",
                             summary=f"Pitmark's Street Team has reached at least {current} active or accepted members in the outreach system.",
                             payload={"member_count": count, "milestone": current})
    set_state("street_team_milestone", str(current)); return {"count": count, "queued": int(created)}
