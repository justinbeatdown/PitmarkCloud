from __future__ import annotations

import io
import logging
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from services.autopilot_ai import compose_with_ai
from services.control_center import SocialPost, utcnow
from services.database import SessionLocal
from services.openai_image_service import generate_image
from services.social_asset_pool import add_asset, get_uploaded_image, store_uploaded_image
from services.social_daily_campaign import (
    REQUIRED_IG_SLIDES,
    REQUIRED_VERTICAL_ASSETS,
    campaign_assets,
    ensure_asset_slot,
    get_campaign,
    summarize_package_progress,
    update_asset,
    update_campaign_package,
)
from utils.config import settings

log = logging.getLogger("pitmark.social.daily_package")

COPY_PLATFORMS = ("facebook", "instagram", "x", "discord", "tiktok_reels")
QUEUE_PLATFORMS = ("facebook", "instagram", "x", "discord")
IG_OUTPUT_SIZE = (1080, 1350)
VERTICAL_OUTPUT_SIZE = (1080, 1920)

_PLATFORM_SLOTS = {
    "facebook": (11, 15),
    "instagram": (12, 30),
    "x": (10, 45),
}


def _clean(value: str | None, limit: int = 6000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _campaign_context(campaign: dict) -> str:
    url = campaign.get("url") or "No public URL supplied."
    return (
        f"Verified Pitmark topic type: {campaign.get('topic_type')}\n"
        f"Title: {campaign.get('title')}\n"
        f"Details: {campaign.get('summary') or 'No additional details.'}\n"
        f"Public URL: {url}\n"
        "Use only these supplied facts. Do not invent results, people, dates, car numbers, "
        "partnerships, discounts, or product specifications."
    )


def _fallback_copy(campaign: dict, platform: str) -> str:
    title = _clean(campaign.get("title"), 240)
    summary = _clean(campaign.get("summary"), 500)
    url = (campaign.get("url") or "").strip()
    if campaign.get("topic_type") == "community_growth":
        base = f"{title} 🏁\n\n{summary}\n\nWhat’s your answer?"
    else:
        base = f"{title} 🏁\n\n{summary}"
        if url:
            base += f"\n\n{url}"
    if platform == "x":
        return base[:25000]
    if platform == "discord":
        return f"## 🏁 {title}\n\n{summary}" + (f"\n\n{url}" if url else "")
    if platform == "tiktok_reels":
        return f"{title} 🏁 {summary}"[:300]
    return base


def compose_platform_copy(campaign: dict, platform: str) -> str:
    ai_platform = "tiktok" if platform == "tiktok_reels" else platform
    goal = "community" if campaign.get("topic_type") == "community_growth" else "authority"
    prompt = (
        "Create the finished daily Pitmark Racing Co. campaign copy for this verified topic. "
        "This is one platform variant in a coordinated daily package, so preserve the same core "
        "story while writing natively for the platform. Do not label the output or mention that it "
        "is automated. " + _campaign_context(campaign)
    )
    if platform == "discord":
        prompt += "\nUse concise Discord Markdown with a natural community tone."
    elif platform == "tiktok_reels":
        prompt += "\nWrite a compact caption for a vertical TikTok/Reels slide sequence with a fast hook."
    try:
        return compose_with_ai(platform=ai_platform, goal=goal, prompt=prompt, tone="pitmark").body.strip()
    except Exception as exc:
        log.warning("Daily campaign copy fallback for %s: %s", platform, exc)
        return _fallback_copy(campaign, platform)


def visual_prompt(*, campaign: dict, headline: str, beat: str, aspect: str) -> str:
    return (
        f"Create a distinct editorial motorsports background for a Pitmark Racing Co. social {aspect} asset. "
        f"Campaign: {campaign.get('title')}. Story beat: {beat}. "
        "Authentic race-track, garage, pits, grandstands, sim-racing rig, tools, helmets, crews, "
        "or racing-atmosphere imagery is preferred when supported by the supplied topic. "
        "Do not invent a real person's likeness, a car number, team livery, sponsor, race result, "
        "racing class, or specific vehicle that is not supplied. "
        "Do not draw, recreate, approximate, distort, or include the Pitmark logo or wordmark in the "
        "generated image; the official Pitmark logo is overlaid later by code. "
        "Do not render readable text in the image. Leave strong text-safe negative space for an exact "
        f"headline overlay and branding. Headline that will be overlaid later: {headline}. "
        + _campaign_context(campaign)
    )


def build_slide_plan(campaign: dict) -> dict:
    title = _clean(campaign.get("title"), 90) or "Pitmark Racing"
    summary = _clean(campaign.get("summary"), 500)
    url = (campaign.get("url") or "").strip()
    ig = [
        {"headline": title, "beat": "Opening hook: establish the campaign topic with the strongest relevant racing atmosphere."},
        {"headline": "Why It Matters", "beat": f"Show the human racing-community context behind this topic. {summary}"},
        {"headline": "Inside the Story", "beat": f"Editorial detail frame grounded only in this supplied context: {summary}"},
        {"headline": "Built Around Racing", "beat": "Connect the verified topic to grassroots motorsports, sim racing, race teams, fans, tracks, garages, or leagues without inventing specifics."},
        {"headline": "Your Turn", "beat": "Create a discussion-driving visual frame that invites the racing community to react or share their perspective."},
        {"headline": "Leave Your Mark.", "beat": f"Closing campaign frame with strong branding-safe negative space. Public destination: {url or 'Pitmark links/site'}."},
    ]
    vertical = [
        {"headline": title, "beat": "Vertical opening hook with immediate racing energy and central subject safety."},
        {"headline": "The Story", "beat": f"Vertical editorial frame based only on: {summary}"},
        {"headline": "Racing Community", "beat": "Vertical community-focused frame with authentic track/garage/sim atmosphere and no invented identities."},
        {"headline": "Leave Your Mark.", "beat": f"Vertical closing frame with clean CTA-safe space. Destination: {url or 'Pitmark links/site'}."},
    ]
    for item in ig:
        item["visual_prompt"] = visual_prompt(
            campaign=campaign, headline=item["headline"], beat=item["beat"], aspect="4:5"
        )
    for item in vertical:
        item["visual_prompt"] = visual_prompt(
            campaign=campaign, headline=item["headline"], beat=item["beat"], aspect="9:16"
        )
    return {"instagram": ig[:REQUIRED_IG_SLIDES], "vertical": vertical[:REQUIRED_VERTICAL_ASSETS]}


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_text(draw, text: str, *, max_width: int, start_size: int, min_size: int = 34):
    for size in range(start_size, min_size - 1, -2):
        font = _font(size, bold=True)
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            proposed = f"{current} {word}".strip()
            box = draw.textbbox((0, 0), proposed, font=font)
            if box[2] - box[0] <= max_width or not current:
                current = proposed
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        line_height = int(size * 1.15)
        if len(lines) <= 4:
            return font, lines, line_height
    font = _font(min_size, bold=True)
    return font, textwrap.wrap(text, width=26)[:4], int(min_size * 1.15)


def render_final_asset(*, source: bytes, output_size: tuple[int, int], headline: str, topic_type: str) -> bytes:
    from PIL import Image, ImageDraw, ImageOps

    image = Image.open(io.BytesIO(source)).convert("RGB")
    image = ImageOps.fit(image, output_size, method=Image.Resampling.LANCZOS)
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", output_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = output_size
    draw.rectangle((0, 0, w, int(h * 0.22)), fill=(0, 0, 0, 100))
    draw.rectangle((0, int(h * 0.57), w, h), fill=(0, 0, 0, 160))

    logo_path = Path(__file__).resolve().parents[1] / "api" / "pitmark_logo_wide.png"
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            max_logo_w = int(w * 0.38)
            scale = max_logo_w / max(1, logo.width)
            logo = logo.resize(
                (max_logo_w, max(1, int(logo.height * scale))),
                Image.Resampling.LANCZOS,
            )
            overlay.alpha_composite(logo, (int(w * 0.055), int(h * 0.055)))
        except Exception:
            pass

    kicker_font = _font(max(24, int(w * 0.027)), bold=True)
    kicker = (topic_type or "PITMARK").replace("_", " ").upper()
    draw.text(
        (int(w * 0.06), int(h * 0.62)),
        kicker,
        font=kicker_font,
        fill=(255, 85, 0, 255),
    )

    font, lines, line_height = _fit_text(
        draw,
        headline,
        max_width=int(w * 0.88),
        start_size=max(62, int(w * 0.075)),
        min_size=max(38, int(w * 0.045)),
    )
    y = int(h * 0.675)
    for line in lines:
        draw.text(
            (int(w * 0.06), y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 210),
        )
        y += line_height

    footer_font = _font(max(24, int(w * 0.026)), bold=True)
    draw.text(
        (int(w * 0.06), int(h * 0.94)),
        "LEAVE YOUR MARK.",
        font=footer_font,
        fill=(255, 255, 255, 235),
    )

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    out = io.BytesIO()
    final.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _public_asset_url(token: str) -> str:
    base = (
        getattr(settings, "pitmark_cloud_public_url", "")
        or "https://pcc.pitmarkracing.com"
    ).rstrip("/")
    return f"{base}/social-assets/{token}"


def _stored_bytes(url: str | None) -> bytes | None:
    marker = "/social-assets/"
    if not url or marker not in url:
        return None
    token = url.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0]
    item = get_uploaded_image(token)
    return item.get("data") if item else None


def _background_prompt(campaign: dict, item: dict, slot: int) -> str:
    return (
        visual_prompt(
            campaign=campaign,
            headline=item["headline"],
            beat=item["beat"],
            aspect="master portrait",
        )
        + f" This is unique master background {slot} of {REQUIRED_IG_SLIDES}; make the composition visibly distinct from the other campaign frames."
    )


def _ensure_background(campaign: dict, *, slot: int, prompt: str, allow_generate: bool) -> dict:
    existing = ensure_asset_slot(
        campaign_id=campaign["id"],
        platform="background",
        slot=slot,
        aspect="master",
        prompt=prompt,
    )
    if existing.get("status") == "ready" and _stored_bytes(existing.get("url")):
        return existing
    if not allow_generate:
        return existing
    try:
        generated = generate_image(
            prompt=prompt,
            size="1024x1536",
            quality=settings.pitmark_image_quality or "low",
        )
        stored = store_uploaded_image(
            data=generated["data"],
            filename=f"daily-campaign-{campaign['id']}-background-{slot}.png",
            mime_type=generated["mime_type"],
        )
        return (
            update_asset(
                existing["id"],
                url=_public_asset_url(stored["public_token"]),
                status="ready",
            )
            or existing
        )
    except Exception as exc:
        log.exception(
            "Daily campaign background generation failed: campaign=%s slot=%s",
            campaign["id"],
            slot,
        )
        return update_asset(existing["id"], status="failed", error=str(exc)) or existing


def _ensure_final_variant(
    campaign: dict,
    *,
    platform: str,
    slot: int,
    aspect: str,
    headline: str,
    source: bytes,
    output_size: tuple[int, int],
) -> dict:
    existing = ensure_asset_slot(
        campaign_id=campaign["id"],
        platform=platform,
        slot=slot,
        aspect=aspect,
        prompt=f"Rendered from campaign master background {slot}.",
    )
    if existing.get("status") == "ready" and existing.get("url"):
        return existing
    try:
        final = render_final_asset(
            source=source,
            output_size=output_size,
            headline=headline,
            topic_type=campaign.get("topic_type") or "pitmark",
        )
        stored = store_uploaded_image(
            data=final,
            filename=f"daily-campaign-{campaign['id']}-{platform}-{slot}.png",
            mime_type="image/png",
        )
        url = _public_asset_url(stored["public_token"])
        add_asset(
            url=url,
            title=f"{campaign.get('title') or 'Pitmark daily campaign'} — {platform} {slot}",
            source="daily_campaign",
            source_ref=f"dailycampaign:{campaign['id']}:{platform}:{slot}",
            tags=[
                "pitmark",
                "daily-campaign",
                platform,
                aspect,
                campaign.get("topic_type") or "community",
            ],
        )
        return update_asset(existing["id"], url=url, status="ready") or existing
    except Exception as exc:
        log.exception(
            "Daily campaign render failed: campaign=%s platform=%s slot=%s",
            campaign["id"],
            platform,
            slot,
        )
        return update_asset(existing["id"], status="failed", error=str(exc)) or existing


def _schedule_for(platform: str) -> str | None:
    if platform not in _PLATFORM_SLOTS:
        return None
    try:
        zone = ZoneInfo(settings.pitmark_timezone)
    except Exception:
        zone = timezone.utc
    now = datetime.now(zone)
    hour, minute = _PLATFORM_SLOTS[platform]
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now + timedelta(minutes=15):
        candidate = (now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    return candidate.isoformat()


def sync_campaign_queue(campaign: dict, package: dict) -> dict:
    source = f"dailycampaign:{campaign['id']}"
    copy = package.get("copy") or {}
    lead_image = next(
        (x for x in package.get("instagram_assets") or [] if x),
        None,
    )
    created = 0
    with SessionLocal() as db:
        existing = {
            row.platform: row
            for row in db.scalars(
                select(SocialPost).where(SocialPost.source == source)
            ).all()
        }
        for platform in QUEUE_PLATFORMS:
            body = str(copy.get(platform) or "").strip()
            if not body or platform in existing:
                continue
            autopublish = bool(
                settings.social_operator_autopublish_low_risk
                and platform in _PLATFORM_SLOTS
            )
            post = SocialPost(
                platform=platform,
                title=(campaign.get("title") or "Pitmark daily campaign")[:180],
                body=body,
                content_type=(
                    "community"
                    if campaign.get("topic_type") == "community_growth"
                    else "authority"
                ),
                source=source,
                risk="copy_only" if platform == "discord" else "low",
                status="scheduled" if autopublish else "pending",
                media_url=lead_image if platform == "instagram" else None,
                scheduled_for=_schedule_for(platform) if autopublish else None,
            )
            db.add(post)
            created += 1
        if created:
            db.commit()

        instagram = existing.get("instagram")
        if instagram and not (instagram.media_url or "").strip() and lead_image:
            instagram.media_url = lead_image
            instagram.updated_at = utcnow()
            db.commit()

        rows = list(
            db.scalars(select(SocialPost).where(SocialPost.source == source)).all()
        )
    return {
        "created": created,
        "items": {
            row.platform: {
                "id": row.id,
                "status": row.status,
                "scheduled_for": row.scheduled_for,
                "media_url": row.media_url,
            }
            for row in rows
        },
    }


def generate_daily_package(campaign_id: int) -> dict:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"ok": False, "campaign_id": campaign_id, "error": "campaign not found"}

    package = dict(campaign.get("package") or {})
    copy = dict(package.get("copy") or {})
    for platform in COPY_PLATFORMS:
        if not str(copy.get(platform) or "").strip():
            copy[platform] = compose_platform_copy(campaign, platform)
    package["copy"] = copy

    plan = (
        package.get("slide_plan")
        if isinstance(package.get("slide_plan"), dict)
        else build_slide_plan(campaign)
    )
    package["slide_plan"] = plan

    image_enabled = bool(
        getattr(settings, "social_daily_image_generation_enabled", True)
    )
    if image_enabled:
        batch_limit = max(
            1,
            min(
                REQUIRED_IG_SLIDES,
                int(getattr(settings, "social_daily_image_batch_size", 2) or 2),
            ),
        )
        assets_before = campaign_assets(campaign_id)
        ready_background_slots = {
            int(asset["slot"])
            for asset in assets_before
            if asset.get("platform") == "background"
            and asset.get("status") == "ready"
            and _stored_bytes(asset.get("url"))
        }
        generated_this_pass = 0

        for slot, item in enumerate(
            plan["instagram"][:REQUIRED_IG_SLIDES],
            start=1,
        ):
            allow = (
                slot in ready_background_slots
                or generated_this_pass < batch_limit
            )
            background = _ensure_background(
                campaign,
                slot=slot,
                prompt=_background_prompt(campaign, item, slot),
                allow_generate=allow,
            )
            if (
                slot not in ready_background_slots
                and background.get("status") == "ready"
            ):
                generated_this_pass += 1
                ready_background_slots.add(slot)

        refreshed_assets = campaign_assets(campaign_id)
        backgrounds = {
            int(asset["slot"]): asset
            for asset in refreshed_assets
            if asset.get("platform") == "background"
            and asset.get("status") == "ready"
        }

        for slot, item in enumerate(
            plan["instagram"][:REQUIRED_IG_SLIDES],
            start=1,
        ):
            source = _stored_bytes((backgrounds.get(slot) or {}).get("url"))
            if source:
                _ensure_final_variant(
                    campaign,
                    platform="instagram",
                    slot=slot,
                    aspect="4:5",
                    headline=item["headline"],
                    source=source,
                    output_size=IG_OUTPUT_SIZE,
                )

        for slot, item in enumerate(
            plan["vertical"][:REQUIRED_VERTICAL_ASSETS],
            start=1,
        ):
            source = _stored_bytes((backgrounds.get(slot) or {}).get("url"))
            if source:
                _ensure_final_variant(
                    campaign,
                    platform="tiktok_reels",
                    slot=slot,
                    aspect="9:16",
                    headline=item["headline"],
                    source=source,
                    output_size=VERTICAL_OUTPUT_SIZE,
                )

    assets = campaign_assets(campaign_id)
    ig_by_slot = {
        int(asset["slot"]): asset.get("url")
        for asset in assets
        if asset.get("platform") == "instagram"
        and asset.get("status") == "ready"
        and asset.get("url")
    }
    vertical_by_slot = {
        int(asset["slot"]): asset.get("url")
        for asset in assets
        if asset.get("platform") == "tiktok_reels"
        and asset.get("status") == "ready"
        and asset.get("url")
    }
    package["instagram_assets"] = [
        ig_by_slot.get(slot) for slot in range(1, REQUIRED_IG_SLIDES + 1)
    ]
    package["vertical_assets"] = [
        vertical_by_slot.get(slot)
        for slot in range(1, REQUIRED_VERTICAL_ASSETS + 1)
    ]
    package["tiktok_reels_publish_mode"] = "ready_to_post"

    progress = summarize_package_progress(package)
    package["progress"] = progress
    state = "ready" if progress["complete"] else "building"
    update_campaign_package(campaign_id, package, status=state)

    queue = sync_campaign_queue(campaign, package)
    latest = get_campaign(campaign_id) or campaign
    return {
        "ok": True,
        "campaign": latest,
        "progress": progress,
        "queue": queue,
        "assets": campaign_assets(campaign_id),
    }
