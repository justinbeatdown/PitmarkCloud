from __future__ import annotations

import random
import re
import secrets
from datetime import datetime, timezone

import httpx
from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal
from utils.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SocialAsset(Base):
    __tablename__ = "autopilot_social_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", index=True)
    source_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(40), default="image", index=True)
    tags: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SocialAssetUpload(Base):
    __tablename__ = "autopilot_social_asset_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(240))
    mime_type: Mapped[str] = mapped_column(String(80))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def store_uploaded_image(*, data: bytes, filename: str, mime_type: str) -> dict:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    clean_type = (mime_type or "").split(";", 1)[0].strip().lower()
    if clean_type not in allowed:
        raise ValueError("Upload must be a JPEG, PNG, or WebP image.")
    if not data:
        raise ValueError("Uploaded image is empty.")
    if len(data) > 6 * 1024 * 1024:
        raise ValueError("Uploaded image must be 6 MB or smaller.")
    token = secrets.token_urlsafe(32)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", (filename or "pitmark-upload").strip())[:220] or "pitmark-upload"
    with SessionLocal() as db:
        row = SocialAssetUpload(public_token=token, filename=safe_name, mime_type=clean_type, data=data)
        db.add(row); db.commit(); db.refresh(row)
        return {"id": row.id, "public_token": row.public_token, "filename": row.filename, "mime_type": row.mime_type, "size": len(data)}


def get_uploaded_image(public_token: str) -> dict | None:
    with SessionLocal() as db:
        row = db.scalar(select(SocialAssetUpload).where(SocialAssetUpload.public_token == public_token))
        if not row:
            return None
        return {"filename": row.filename, "mime_type": row.mime_type, "data": row.data}


def serialize_asset(a: SocialAsset) -> dict:
    return {
        "id": a.id,
        "url": a.url,
        "title": a.title,
        "source": a.source,
        "source_ref": a.source_ref,
        "asset_type": a.asset_type,
        "tags": [x.strip() for x in (a.tags or "").split(",") if x.strip()],
        "active": a.active,
        "use_count": a.use_count,
        "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
    }


def add_asset(*, url: str, title: str | None = None, source: str = "manual", source_ref: str | None = None, asset_type: str = "image", tags: list[str] | None = None) -> dict:
    clean_url = (url or "").strip()
    if not clean_url.startswith(("https://", "http://")):
        raise ValueError("Asset URL must be publicly reachable over http/https.")

    tag_text = ",".join(sorted({x.strip().lower() for x in (tags or []) if x.strip()}))
    with SessionLocal() as db:
        existing = db.scalar(select(SocialAsset).where(SocialAsset.url == clean_url))
        if existing:
            existing.title = title or existing.title
            existing.source = source or existing.source
            existing.source_ref = source_ref or existing.source_ref
            existing.asset_type = asset_type or existing.asset_type
            if tag_text:
                current = {x.strip() for x in (existing.tags or "").split(",") if x.strip()}
                current.update(x for x in tag_text.split(",") if x)
                existing.tags = ",".join(sorted(current))
            existing.active = True
            existing.updated_at = utcnow()
            db.commit(); db.refresh(existing)
            return serialize_asset(existing)

        asset = SocialAsset(url=clean_url, title=title, source=source, source_ref=source_ref, asset_type=asset_type, tags=tag_text, active=True)
        db.add(asset); db.commit(); db.refresh(asset)
        return serialize_asset(asset)


def list_assets(*, active_only: bool = True, limit: int = 200) -> list[dict]:
    with SessionLocal() as db:
        q = select(SocialAsset).order_by(SocialAsset.id.desc()).limit(max(1, min(limit, 500)))
        if active_only:
            q = q.where(SocialAsset.active.is_(True))
        return [serialize_asset(x) for x in db.scalars(q).all()]


def _words(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(x) >= 3}


def choose_asset(*, body: str = "", content_type: str = "", platform: str = "instagram") -> dict | None:
    with SessionLocal() as db:
        rows = list(db.scalars(select(SocialAsset).where(SocialAsset.active.is_(True), SocialAsset.asset_type == "image").order_by(SocialAsset.id.desc())).all())
        if not rows:
            return None
        target = _words(body + " " + content_type + " " + platform)
        ranked = []
        for asset in rows:
            haystack = _words(" ".join([asset.title or "", asset.tags or "", asset.source_ref or "", asset.source or ""]))
            overlap = len(target & haystack)
            freshness_bonus = 5 if asset.last_used_at is None else 0
            reuse_penalty = min(asset.use_count or 0, 20)
            ranked.append((overlap * 8 + freshness_bonus - reuse_penalty, asset))
        ranked.sort(key=lambda x: x[0], reverse=True)
        top_score = ranked[0][0]
        shortlist = [asset for score, asset in ranked if score >= top_score - 6][:8]
        return serialize_asset(random.choice(shortlist or [ranked[0][1]]))


def mark_used(asset_url: str) -> None:
    if not asset_url:
        return
    with SessionLocal() as db:
        asset = db.scalar(select(SocialAsset).where(SocialAsset.url == asset_url))
        if not asset:
            return
        asset.use_count = (asset.use_count or 0) + 1
        asset.last_used_at = utcnow()
        asset.updated_at = utcnow()
        db.commit()


def sync_shopify_images(limit_products: int = 250) -> dict:
    base = (settings.pitmark_public_store_url or "https://pitmarkracing.com").rstrip("/")
    url = f"{base}/products.json"
    try:
        response = httpx.get(url, params={"limit": max(1, min(limit_products, 250))}, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Could not read public Shopify product images: {exc}") from exc

    products = payload.get("products") or []
    added = 0
    seen = 0
    for product in products:
        title = product.get("title") or "Pitmark product"
        handle = product.get("handle") or ""
        tags_raw = product.get("tags") or []
        if isinstance(tags_raw, str):
            tags_raw = [x.strip() for x in tags_raw.split(",") if x.strip()]
        tags = ["shopify", "product", handle.replace("-", " "), *tags_raw]
        for image in product.get("images") or []:
            src = (image.get("src") or "").strip()
            if not src:
                continue
            seen += 1
            with SessionLocal() as db:
                existed = db.scalar(select(SocialAsset).where(SocialAsset.url == src)) is not None
            add_asset(url=src, title=title, source="shopify", source_ref=f"product:{handle}", tags=tags)
            if not existed:
                added += 1
    return {"ok": True, "products_scanned": len(products), "images_seen": seen, "assets_added": added, "pool_size": len(list_assets(limit=500))}
