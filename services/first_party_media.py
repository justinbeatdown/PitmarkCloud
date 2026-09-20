from __future__ import annotations

import json
import logging
from urllib.parse import quote

import httpx
from sqlalchemy import select

from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services import shopify_service
from services.openai_image_service import generate_image
from services.social_asset_pool import add_asset, store_uploaded_image
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


def _event_payload(event: FirstPartyEvent) -> dict:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _public_asset_url(token: str) -> str:
    base = (
        getattr(settings, "pitmark_cloud_public_url", "")
        or "https://pcc.pitmarkracing.com"
    ).rstrip("/")
    return f"{base}/social-assets/{token}"


def _resolve_shopify_article_image(event: FirstPartyEvent) -> str | None:
    payload = _event_payload(event)
    article_id = str(payload.get("shopify_article_id") or "").strip()
    if not article_id:
        return None
    try:
        data = shopify_service.graphql(
            "query PitmarkArticleMedia($id: ID!) { node(id: $id) { ... on Article { id image { url } } } }",
            {"id": article_id},
        )
        node = data.get("node") or {}
        return _normalize_image_url((node.get("image") or {}).get("url"))
    except Exception as exc:
        log.warning("Could not resolve Shopify article media for %s: %s", article_id, exc)
        return None


def _generate_blog_image(event: FirstPartyEvent) -> str | None:
    title = str(event.title or "Pitmark racing story").strip()
    summary = str(event.summary or "").strip()
    prompt = (
        "Create a high-quality editorial motorsports social image for Pitmark Racing Co. "
        f"Story title: {title}. "
        f"Story context: {summary[:1200] or 'Motorsports editorial story.'} "
        "Make the main subject match the racing story: track, race cars, pits, grandstands, "
        "garage, or authentic motorsports atmosphere as appropriate. "
        "Do not show shirts, hoodies, hats, product mockups, ecommerce merchandise, or storefront imagery. "
        "Do not invent readable sponsor logos, driver names, car numbers, race results, or identifiable real people. "
        "Do not render the Pitmark logo or readable text; Pitmark branding can be overlaid separately. "
        "Use a polished human-designed editorial composition suitable for Facebook, Instagram, and X."
    )
    try:
        generated = generate_image(
            prompt=prompt,
            size="1024x1024",
            quality=getattr(settings, "pitmark_image_quality", None) or "low",
        )
        data = generated.get("data")
        if not data:
            return None
        stored = store_uploaded_image(
            data=data,
            filename=f"firstparty-blog-{event.id}.png",
            mime_type="image/png",
        )
        url = _public_asset_url(stored["public_token"])
        add_asset(
            url=url,
            title=title,
            source="firstparty_blog",
            source_ref=f"firstparty:{event.id}",
            tags=["pitmark", "editorial", "racing", "blog"],
        )
        return url
    except Exception as exc:
        log.exception("Could not generate first-party blog image for event %s: %s", event.id, exc)
        return None


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
    """Repair media for active first-party social drafts.

    Product campaigns use the exact Shopify product image. Blog/article campaigns
    use the real Shopify article image when available and generate one editorial
    racing visual only when the article has no usable image.
    """
    repaired_images = 0
    images_missing = 0
    generated_blog_images = 0
    article_images_resolved = 0
    tiktok_archived = 0

    with SessionLocal() as db:
        events = list(
            db.scalars(
                select(FirstPartyEvent)
                .where(FirstPartyEvent.event_type.in_(["shopify_product", "blog_publish"]))
                .order_by(FirstPartyEvent.id.desc())
                .limit(max(1, min(int(limit), 250)))
            ).all()
        )

        # Keep generation bounded per reconciliation pass. The background operator
        # will continue healing remaining events on later passes.
        generation_budget = 2

        for event in events:
            media = _normalize_image_url(event.media_url)

            if event.event_type == "shopify_product":
                if not media:
                    media = resolve_shopify_product_image(_product_handle(event))
            elif event.event_type == "blog_publish":
                if not media:
                    media = _resolve_shopify_article_image(event)
                    if media:
                        article_images_resolved += 1
                if not media and generation_budget > 0:
                    media = _generate_blog_image(event)
                    if media:
                        generated_blog_images += 1
                        generation_budget -= 1

            if media and _normalize_image_url(event.media_url) != media:
                event.media_url = media
                event.updated_at = utcnow()

            posts = list(
                db.scalars(
                    select(SocialPost).where(
                        SocialPost.source == f"firstparty:{event.id}",
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

        if repaired_images or generated_blog_images or article_images_resolved or tiktok_archived:
            db.commit()

    return {
        "first_party_images_repaired": repaired_images,
        "images_missing": images_missing,
        "blog_images_generated": generated_blog_images,
        "article_images_resolved": article_images_resolved,
        "tiktok_first_party_drafts_archived": tiktok_archived,
    }

