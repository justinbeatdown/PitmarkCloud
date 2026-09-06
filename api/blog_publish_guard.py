from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select

from services import shopify_service
from services.autonomy_control import enforce as enforce_autonomy
from services.blog_image_service import generate_and_stage_blog_image, resolve_staged_blog_image
from services.control_auth import require_control_user
from services.control_center import BlogDraft, ShopifyPublishRecord, serialize, utcnow
from services.database import SessionLocal

router = APIRouter()
FIELDS = "id title handle isPublished image { originalSrc }"


def _auth(request, key):
    return require_control_user(request, key)


def _errors(result, label):
    errors = result.get("userErrors") or []
    if errors:
        raise RuntimeError(label + ": " + "; ".join(str(x.get("message", "error")) for x in errors[:3]))


def _create(blog_id, title, body, image_url):
    q = f"""mutation P($a: ArticleCreateInput!) {{ articleCreate(article:$a) {{ article {{ {FIELDS} }} userErrors {{ message }} }} }}"""
    a = {"blogId": blog_id, "title": title, "author": {"name": "Pitmark Racing Co."}, "body": body,
         "isPublished": False, "image": {"url": image_url, "altText": title}}
    r = (shopify_service.graphql(q, {"a": a}).get("articleCreate") or {}); _errors(r, "Shopify create rejected")
    if not r.get("article"): raise RuntimeError("Shopify did not return the created article")
    return r["article"]


def _update(article_id, *, publish=None, image_url=None, alt="Pitmark Racing Co. blog image"):
    q = f"""mutation P($id:ID!,$a:ArticleUpdateInput!) {{ articleUpdate(id:$id,article:$a) {{ article {{ {FIELDS} }} userErrors {{ message }} }} }}"""
    a = {}
    if publish is not None: a["isPublished"] = bool(publish)
    if image_url: a["image"] = {"url": image_url, "altText": alt}
    r = (shopify_service.graphql(q, {"id": article_id, "a": a}).get("articleUpdate") or {}); _errors(r, "Shopify update rejected")
    if not r.get("article"): raise RuntimeError("Shopify did not return the updated article")
    return r["article"]


def _get(article_id):
    q = f"""query P($id:ID!) {{ node(id:$id) {{ ... on Article {{ {FIELDS} }} }} }}"""
    n = shopify_service.graphql(q, {"id": article_id}).get("node")
    return n if isinstance(n, dict) and n.get("id") else None


def _delete(article_id):
    q = """mutation P($id:ID!){articleDelete(id:$id){deletedArticleId userErrors{message}}}"""
    r = (shopify_service.graphql(q, {"id": article_id}).get("articleDelete") or {}); _errors(r, "Shopify delete rejected")


def _image(article):
    return (((article or {}).get("image") or {}).get("originalSrc") or "").strip() or None


def _durable(url):
    v = (url or "").lower()
    return bool(v and "/api/control/auth/blog/generated-image/" not in v)


def _blog():
    blogs = shopify_service.list_blogs()
    if not blogs: raise RuntimeError("No Shopify blog is available")
    return next((x for x in blogs if (x.get("handle") or "").lower() == "racing-culture"), blogs[0])


def _stage(request, draft):
    x = generate_and_stage_blog_image(title=draft.title, body_html=draft.body_html, content_type=draft.content_type)
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/control/auth/blog/generated-image/{x.token}"


@router.get("/auth/blog/generated-image/{token}", include_in_schema=False)
def generated_image(token: str):
    found = resolve_staged_blog_image(token)
    if not found: raise HTTPException(404, "Generated image unavailable or expired")
    path, media_type = found
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "public, max-age=900"})


@router.post("/blog/drafts/{draft_id}/shopify-publish")
def guarded_publish(draft_id: int, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    try: enforce_autonomy("blog_publish", allow_approval=True)
    except PermissionError as exc: raise HTTPException(403, str(exc))
    with SessionLocal() as db:
        d = db.get(BlogDraft, draft_id)
        if not d: raise HTTPException(404, "Draft not found")
        if d.status != "approved": raise HTTPException(409, "Approve the blog draft before publishing to Shopify.")
        if db.scalar(select(ShopifyPublishRecord).where(ShopifyPublishRecord.draft_id == draft_id)):
            raise HTTPException(409, "This draft already has a Shopify publish record.")
        image_url = (d.featured_image_url or "").strip()
        generated = False
        if not image_url:
            try: image_url = _stage(request, d); generated = True
            except Exception as exc: raise HTTPException(502, f"Hero image generation failed. Article not published: {exc}")
        article = None
        try:
            b = _blog(); article = _create(b["id"], d.title, d.body_html, image_url)
            durable = _image(article)
            if not _durable(durable): raise RuntimeError("Shopify did not ingest a durable hero image")
            article = _update(article["id"], publish=True)
            final = _image(article) or durable
            if not article.get("isPublished") or not _durable(final): raise RuntimeError("Shopify did not confirm image + publish")
        except Exception as exc:
            if article and article.get("id"):
                try: _delete(article["id"])
                except Exception: pass
            raise HTTPException(502, f"Shopify publish failed: {exc}")
        rec = ShopifyPublishRecord(draft_id=draft_id, shopify_article_id=article["id"], title=article.get("title") or d.title, url=None, status="published")
        db.add(rec); d.featured_image_url = final; d.status = "published"; d.updated_at = utcnow(); db.commit(); db.refresh(d)
        return {"ok": True, "draft": serialize(d), "shopify": article, "blog": b, "hero_image_generated": generated}


@router.post("/blog/drafts/{draft_id}/shopify-repair-image")
def repair_image(draft_id: int, request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        d = db.get(BlogDraft, draft_id)
        if not d: raise HTTPException(404, "Draft not found")
        rec = db.scalar(select(ShopifyPublishRecord).where(ShopifyPublishRecord.draft_id == draft_id))
        if not rec: raise HTTPException(409, "No Shopify publish record to repair")
        try:
            current = _get(rec.shopify_article_id)
            if not current: raise RuntimeError("Shopify article no longer exists")
            current_url = _image(current)
            if _durable(current_url):
                d.featured_image_url = current_url; d.updated_at = utcnow(); db.commit(); db.refresh(d)
                return {"ok": True, "repaired": False, "draft": serialize(d), "shopify": current}
            staged = _stage(request, d); updated = _update(rec.shopify_article_id, image_url=staged, alt=d.title); final = _image(updated)
            if not _durable(final): raise RuntimeError("Shopify did not ingest replacement hero image")
            d.featured_image_url = final; d.updated_at = utcnow(); db.commit(); db.refresh(d)
            return {"ok": True, "repaired": True, "draft": serialize(d), "shopify": updated}
        except Exception as exc: raise HTTPException(502, f"Shopify image repair failed: {exc}")


@router.post("/blog/shopify-repair-latest-missing-image")
def repair_latest(request: Request, x_pitmark_admin_key: str | None = Header(default=None)):
    _auth(request, x_pitmark_admin_key)
    target = None
    with SessionLocal() as db:
        rows = list(db.scalars(select(BlogDraft).where(BlogDraft.status == "published").order_by(BlogDraft.id.desc()).limit(25)).all())
        for d in rows:
            if (d.featured_image_url or "").strip(): continue
            if db.scalar(select(ShopifyPublishRecord).where(ShopifyPublishRecord.draft_id == d.id)):
                target = d.id; break
    if target is None: raise HTTPException(404, "No recent published draft with a missing hero image found")
    return repair_image(target, request, x_pitmark_admin_key)
