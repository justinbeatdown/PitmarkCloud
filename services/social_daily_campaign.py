from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from services import persistent_store
from services.control_center import SocialPost, utcnow
from services.database import Base, SessionLocal
from services.first_party_models import FirstPartyEvent, get_state
from services.prt_versions import compare_versions, extract_version, newest_version
from utils.config import settings

log = logging.getLogger("pitmark.social.daily_campaign")

REQUIRED_COPY_PLATFORMS = ("facebook", "instagram", "x", "discord", "tiktok_reels")
REQUIRED_IG_SLIDES = 6
REQUIRED_VERTICAL_ASSETS = 4
ELIGIBLE_EVENT_TYPES = (
    "prt_release",
    "blog_publish",
    "shopify_product",
    "partnership",
    "prt_milestone",
    "street_team",
    "street_team_milestone",
)
_EVENT_PRIORITY = {
    "prt_release": 100,
    "blog_publish": 90,
    "partnership": 80,
    "prt_milestone": 75,
    "shopify_product": 70,
    "street_team": 60,
    "street_team_milestone": 55,
}
_FALLBACKS = (
    {
        "title": "Track Roll Call",
        "summary": "Ask the Pitmark community to share their home track, state, and the one race there everyone should see.",
    },
    {
        "title": "Build the Ultimate Race Track",
        "summary": "Let the community build a race track one choice at a time: length, banking, surface, headline class, location, and race-night essentials.",
    },
    {
        "title": "One Change for Grassroots Racing",
        "summary": "Ask racers and fans for one realistic rule, facility, promotion, or race-night change that would make grassroots racing better.",
    },
    {
        "title": "What Keeps You Coming Back?",
        "summary": "Ask the racing community what a track, league, team, or event does that instantly makes them want to come back.",
    },
)


class DailyCampaign(Base):
    __tablename__ = "social_daily_campaigns"
    __table_args__ = (UniqueConstraint("day_key", name="uq_social_daily_campaign_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_key: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    topic_type: Mapped[str] = mapped_column(String(60), index=True)
    topic_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    package_json: Mapped[str] = mapped_column(Text, default="{}")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailyCampaignAsset(Base):
    __tablename__ = "social_daily_campaign_assets"
    __table_args__ = (
        UniqueConstraint("campaign_id", "platform", "slot", name="uq_social_daily_asset_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, index=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    slot: Mapped[int] = mapped_column(Integer)
    aspect: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _zone(name: str | None = None):
    try:
        return ZoneInfo(name or settings.pitmark_timezone)
    except Exception:
        return timezone.utc


def _aware(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo else current.replace(tzinfo=timezone.utc)


def campaign_day_key(now: datetime | None = None, *, timezone_name: str | None = None) -> str:
    return _aware(now).astimezone(_zone(timezone_name)).date().isoformat()


def fallback_topic(day_key: str) -> dict:
    digest = hashlib.sha256(day_key.encode("utf-8")).digest()
    item = _FALLBACKS[int.from_bytes(digest[:4], "big") % len(_FALLBACKS)]
    return {
        "topic_type": "community_growth",
        "topic_ref": f"fallback:{day_key}",
        "title": item["title"],
        "summary": item["summary"],
        "url": None,
    }


def _event_payload(row: FirstPartyEvent) -> dict:
    return {
        "topic_type": row.event_type,
        "topic_ref": f"firstparty:{row.id}",
        "title": row.title,
        "summary": row.summary or "",
        "url": row.url,
        "created_at": row.created_at,
    }


def _accepted_prt_version() -> str | None:
    local = get_state("prt_manifest_version")
    try:
        announced = persistent_store.get_runtime_state("prt_release_last_announced_version")
    except Exception:
        announced = None
    return newest_version(local, announced)


def _prt_event_version(row: FirstPartyEvent) -> str | None:
    try:
        payload = json.loads(row.payload_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    if isinstance(payload, dict):
        version = str(payload.get("version") or "").strip()
        if version:
            return version.lstrip("vV")
    return extract_version(row.event_key) or extract_version(row.title)


def _drop_stale_prt_events(rows: list[FirstPartyEvent]) -> list[FirstPartyEvent]:
    baseline = _accepted_prt_version()
    if not baseline:
        return rows
    current_rows: list[FirstPartyEvent] = []
    for row in rows:
        if row.event_type != "prt_release":
            current_rows.append(row)
            continue
        comparison = compare_versions(_prt_event_version(row), baseline)
        if comparison is not None and comparison >= 0:
            current_rows.append(row)
    return current_rows


def _campaign_prt_version(row: DailyCampaign) -> str | None:
    return extract_version(row.title) or extract_version(row.topic_ref)


def _campaign_is_stale_prt_release(row: DailyCampaign) -> bool:
    if row.topic_type != "prt_release":
        return False
    baseline = _accepted_prt_version()
    campaign_version = _campaign_prt_version(row)
    comparison = compare_versions(campaign_version, baseline)
    return comparison is not None and comparison < 0


def _campaign_repeats_prior_topic(row: DailyCampaign) -> bool:
    topic_ref = str(row.topic_ref or "").strip()
    if not topic_ref:
        return False
    with SessionLocal() as db:
        prior_id = db.scalar(
            select(DailyCampaign.id)
            .where(
                DailyCampaign.topic_ref == topic_ref,
                DailyCampaign.id != row.id,
            )
            .limit(1)
        )
    return prior_id is not None


def _reset_campaign_bundle(campaign_id: int) -> None:
    from services.social_asset_pool import SocialAsset, SocialAssetUpload

    source_prefix = f"dailycampaign:{campaign_id}:"
    source = f"dailycampaign:{campaign_id}"
    with SessionLocal() as db:
        generated_assets = list(
            db.scalars(select(SocialAsset).where(SocialAsset.source_ref.like(f"{source_prefix}%"))).all()
        )
        upload_tokens: set[str] = set()
        for asset in generated_assets:
            url = str(asset.url or "")
            marker = "/social-assets/"
            if marker in url:
                token = url.rsplit(marker, 1)[-1].split("?", 1)[0].strip()
                if token:
                    upload_tokens.add(token)
        db.execute(delete(SocialPost).where(SocialPost.source == source))
        db.execute(delete(DailyCampaignAsset).where(DailyCampaignAsset.campaign_id == campaign_id))
        db.execute(delete(SocialAsset).where(SocialAsset.source_ref.like(f"{source_prefix}%")))
        if upload_tokens:
            db.execute(delete(SocialAssetUpload).where(SocialAssetUpload.public_token.in_(upload_tokens)))
        db.execute(delete(DailyCampaign).where(DailyCampaign.id == campaign_id))
        db.commit()


def select_campaign_topic(now: datetime | None = None) -> dict:
    current = _aware(now)
    cutoff = current - timedelta(hours=72)
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(FirstPartyEvent).where(
                    FirstPartyEvent.event_type.in_(ELIGIBLE_EVENT_TYPES),
                    FirstPartyEvent.status.in_(["queued", "processed"]),
                    FirstPartyEvent.created_at >= cutoff,
                )
            ).all()
        )
        used_topic_refs = set(
            db.scalars(
                select(DailyCampaign.topic_ref).where(DailyCampaign.topic_ref.is_not(None))
            ).all()
        )
    rows = _drop_stale_prt_events(rows)
    rows = [row for row in rows if f"firstparty:{row.id}" not in used_topic_refs]
    if not rows:
        return fallback_topic(campaign_day_key(current))
    rows.sort(
        key=lambda row: (
            _EVENT_PRIORITY.get(row.event_type, 0),
            _aware(row.created_at).timestamp(),
            row.id,
        ),
        reverse=True,
    )
    return _event_payload(rows[0])


def _decode_package(value: str | None) -> dict:
    try:
        payload = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_package_progress(package: dict | None) -> dict:
    payload = package or {}
    copy = payload.get("copy") if isinstance(payload.get("copy"), dict) else {}
    ig_assets = payload.get("instagram_assets") if isinstance(payload.get("instagram_assets"), list) else []
    vertical = payload.get("vertical_assets") if isinstance(payload.get("vertical_assets"), list) else []
    copy_ready = sum(1 for name in REQUIRED_COPY_PLATFORMS if str(copy.get(name) or "").strip())
    ig_ready = sum(1 for item in ig_assets if item)
    vertical_ready = sum(1 for item in vertical if item)
    return {
        "copy_ready": copy_ready,
        "copy_total": len(REQUIRED_COPY_PLATFORMS),
        "ig_assets_ready": ig_ready,
        "ig_assets_total": REQUIRED_IG_SLIDES,
        "vertical_assets_ready": vertical_ready,
        "vertical_assets_total": REQUIRED_VERTICAL_ASSETS,
        "complete": (
            copy_ready == len(REQUIRED_COPY_PLATFORMS)
            and ig_ready >= REQUIRED_IG_SLIDES
            and vertical_ready >= REQUIRED_VERTICAL_ASSETS
        ),
    }


def serialize_campaign(row: DailyCampaign) -> dict:
    package = _decode_package(row.package_json)
    return {
        "id": row.id,
        "day_key": row.day_key,
        "topic_type": row.topic_type,
        "topic_ref": row.topic_ref,
        "title": row.title,
        "summary": row.summary or "",
        "url": row.url,
        "status": row.status,
        "package": package,
        "progress": summarize_package_progress(package),
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def get_campaign(campaign_id: int) -> dict | None:
    with SessionLocal() as db:
        row = db.get(DailyCampaign, campaign_id)
        return serialize_campaign(row) if row else None


def suppress_campaign_platform(campaign_id: int, platform: str) -> dict | None:
    name = str(platform or "").strip().lower()
    if not name:
        return get_campaign(campaign_id)
    with SessionLocal() as db:
        row = db.get(DailyCampaign, campaign_id)
        if not row:
            return None
        package = _decode_package(row.package_json)
        suppressed = {
            str(item or "").strip().lower()
            for item in (package.get("suppressed_platforms") or [])
            if str(item or "").strip()
        }
        suppressed.add(name)
        package["suppressed_platforms"] = sorted(suppressed)
        row.package_json = json.dumps(package, ensure_ascii=False, default=str)
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return serialize_campaign(row)


def ensure_daily_campaign(now: datetime | None = None) -> dict:
    current = _aware(now)
    day_key = campaign_day_key(current)
    reset_campaign_id: int | None = None
    reset_title: str | None = None
    reset_reason: str | None = None
    with SessionLocal() as db:
        existing = db.scalar(select(DailyCampaign).where(DailyCampaign.day_key == day_key))
        if existing:
            if _campaign_is_stale_prt_release(existing):
                reset_campaign_id = existing.id
                reset_title = existing.title
                reset_reason = f"stale PRT release; trusted baseline is v{_accepted_prt_version() or 'unknown'}"
            elif _campaign_repeats_prior_topic(existing):
                reset_campaign_id = existing.id
                reset_title = existing.title
                reset_reason = f"topic {existing.topic_ref or 'unknown'} was already used by an earlier Daily Campaign"
            else:
                return serialize_campaign(existing)

    if reset_campaign_id is not None:
        log.warning(
            "Resetting invalid Daily Campaign %s (%s): %s.",
            reset_campaign_id,
            reset_title,
            reset_reason or "invalid campaign state",
        )
        _reset_campaign_bundle(reset_campaign_id)

    topic = select_campaign_topic(current)
    with SessionLocal() as db:
        row = DailyCampaign(
            day_key=day_key,
            topic_type=topic["topic_type"],
            topic_ref=topic.get("topic_ref"),
            title=topic["title"][:240],
            summary=(topic.get("summary") or "")[:6000],
            url=(topic.get("url") or "").strip() or None,
            status="planned",
            package_json="{}",
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return serialize_campaign(row)
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(DailyCampaign).where(DailyCampaign.day_key == day_key))
            if not existing:
                raise
            return serialize_campaign(existing)


def update_campaign_package(
    campaign_id: int,
    package: dict,
    *,
    status: str | None = None,
    error: str | None = None,
) -> dict | None:
    with SessionLocal() as db:
        row = db.get(DailyCampaign, campaign_id)
        if not row:
            return None
        row.package_json = json.dumps(package or {}, ensure_ascii=False, default=str)
        if status:
            row.status = status[:30]
        row.last_error = (error or "")[:1000] or None
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return serialize_campaign(row)


def ensure_asset_slot(
    *,
    campaign_id: int,
    platform: str,
    slot: int,
    aspect: str,
    prompt: str,
) -> dict:
    with SessionLocal() as db:
        row = db.scalar(
            select(DailyCampaignAsset).where(
                DailyCampaignAsset.campaign_id == campaign_id,
                DailyCampaignAsset.platform == platform,
                DailyCampaignAsset.slot == slot,
            )
        )
        if row is None:
            row = DailyCampaignAsset(
                campaign_id=campaign_id,
                platform=platform,
                slot=slot,
                aspect=aspect,
                prompt=prompt,
                status="planned",
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        return serialize_asset(row)


def serialize_asset(row: DailyCampaignAsset) -> dict:
    return {
        "id": row.id,
        "campaign_id": row.campaign_id,
        "platform": row.platform,
        "slot": row.slot,
        "aspect": row.aspect,
        "prompt": row.prompt,
        "url": row.url,
        "status": row.status,
        "last_error": row.last_error,
    }


def update_asset(
    asset_id: int,
    *,
    url: str | None = None,
    status: str,
    error: str | None = None,
) -> dict | None:
    with SessionLocal() as db:
        row = db.get(DailyCampaignAsset, asset_id)
        if not row:
            return None
        if url is not None:
            row.url = url
        row.status = status[:30]
        row.last_error = (error or "")[:1000] or None
        row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return serialize_asset(row)


def campaign_assets(campaign_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(DailyCampaignAsset)
                .where(DailyCampaignAsset.campaign_id == campaign_id)
                .order_by(DailyCampaignAsset.platform.asc(), DailyCampaignAsset.slot.asc())
            ).all()
        )
    return [serialize_asset(row) for row in rows]


def campaign_status(now: datetime | None = None) -> dict | None:
    day_key = campaign_day_key(now)
    with SessionLocal() as db:
        row = db.scalar(select(DailyCampaign).where(DailyCampaign.day_key == day_key))
        if not row:
            return None
        payload = serialize_campaign(row)
        posts = list(
            db.scalars(
                select(SocialPost).where(SocialPost.source == f"dailycampaign:{row.id}")
            ).all()
        )
    payload["assets"] = campaign_assets(payload["id"])
    payload["queue"] = {
        post.platform: {
            "status": post.status,
            "scheduled_for": post.scheduled_for,
            "media_url": post.media_url,
        }
        for post in posts
    }
    return payload