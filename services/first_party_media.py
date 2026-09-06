from __future__ import annotations

import json
import logging
from urllib.parse import quote

import httpx
from sqlalchemy import select

from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.first_party_models import FirstPartyEvent
from utils.config import settings

log = logging.getLogger("pitmark.autopilot.first_party.media")

ACTIVE_DRAFT_STATUSES = ("pending", "approved", "scheduled")


def _normalize_image_url(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("src") or value.get("url")
    url = str(value or "").strip()
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    return url if url.startswith(("https://", "http://")) else None


def _product_handle(event: FirstPartyEvent) -> str:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:
        payload = {}
    return str(payload.get("handle") or "").strip()


def resolve_shopify_product_image(handle: str) -> str | None:
    """Resolve the actual storefront image for one Shopify product.

    First-party product campaigns should use the product art the customer sees on
    Pitmark's storefront. They should never silently substitute a generic/AI image.
    """
    clean_handle = str(handle or "").strip()
    if not clean_handle:
        return None

    base = (settings.pitmark_public_store_url or "https://pitmarkracing.com").rstrip("/")
    target = f"{base}/products/{quote(clean_handle, safe='')}.js"
    try:
        response = httpx.get(
            target,
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "PitmarkAutopilot-ProductMedia/1.0"},
        )
        response.raise_for_status()
        product = response.json() or {}
    except Exception as exc:
        log.warning("Could not resolve Shopify media for %s: %s", clean_handle, exc)
        return None

    featured = _normalize_image_url(product.get("featured_image"))
    if featured:
        return featured

    for image in product.get("images") or []:
        found = _normalize_image_url(image)
        if found:
            return found
    return None


def resolve_product_media_for_source(source: str | None) -> tuple[bool, str | None]:
    """Return (is_first_party_product, exact_product_image_url)."""
    raw = str(source or "").strip()
    if not raw.startswith("firstparty:"):
        return False, None
    try:
        event_id = int(raw.split(":", 1)[1])
    except (TypeError, ValueError):
        return False, None

    with SessionLocal() as db:
        event = db.get(FirstPartyEvent, event_id)
        if not event or event.event_type != "shopify_product":
            return False, None

        media = _normalize_image_url(event.media_url)
        if media:
            return True, media

        handle = _product_handle(event)
        media = resolve_shopify_product_image(handle)
        if media:
            event.media_url = media
            event.updated_at = utcnow()
            db.commit()
        return True, media


def reconcile_first_party_drafts(limit: int = 100) -> dict:
    """Repair existing first-party drafts after a scan.

    - Product Instagram drafts are pinned to the exact Shopify product image.
    - Old first-party TikTok copy-only drafts are archived now that automatic
      TikTok generation is paused until Pitmark has a real video workflow.
    """
    repaired_images = 0
    images_missing = 0
    tiktok_archived = 0

    with SessionLocal() as db:
        product_events = list(
            db.scalars(
                select(FirstPartyEvent)
                .where(FirstPartyEvent.event_type == "shopify_product")
                .order_by(FirstPartyEvent.id.desc())
                .limit(max(1, min(int(limit), 250)))
            ).all()
        )

        for event in product_events:
            media = _normalize_image_url(event.media_url)
            if not media:
                media = resolve_shopify_product_image(_product_handle(event))
                if media:
                    event.media_url = media
                    event.updated_at = utcnow()

            posts = list(
                db.scalars(
                    select(SocialPost).where(
                        SocialPost.source == f"firstparty:{event.id}",
                        SocialPost.platform == "instagram",
                        SocialPost.status.in_(ACTIVE_DRAFT_STATUSES),
                    )
                ).all()
            )
            if not media:
                images_missing += len(posts)
                continue

            for post in posts:
                if (post.media_url or "").strip() != media:
                    post.media_url = media
                    post.updated_at = utcnow()
                    repaired_images += 1

        tiktok_rows = list(
            db.scalars(
                select(SocialPost).where(
                    SocialPost.source.like("firstparty:%"),
                    SocialPost.platform == "tiktok",
                    SocialPost.status.in_(ACTIVE_DRAFT_STATUSES),
                )
            ).all()
        )
        for post in tiktok_rows:
            post.status = "archived"
            post.updated_at = utcnow()
            tiktok_archived += 1

        if repaired_images or tiktok_archived or any(
            _normalize_image_url(event.media_url) for event in product_events
        ):
            db.commit()

    return {
        "product_instagram_images_repaired": repaired_images,
        "product_instagram_images_missing": images_missing,
        "tiktok_first_party_drafts_archived": tiktok_archived,
    }
