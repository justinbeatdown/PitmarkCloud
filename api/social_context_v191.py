from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from services.control_access import require_permission
from services.control_center import AutopilotOpportunity, SocialPost, serialize, utcnow
from services.database import SessionLocal
from services.openai_image_service import PitmarkImageGenerationError, generate_image
from services.social_asset_pool import add_asset, store_uploaded_image
from utils.security import enforce_rate_limit

router = APIRouter()


def _story_context(db, post: SocialPost) -> str:
    source = str(post.source or "")
    if source.startswith("intelligence:"):
        try:
            oid = int(source.split(":", 1)[1])
            op = db.get(AutopilotOpportunity, oid)
            if op:
                return f"{op.headline}. {op.reason or ''}".strip()
        except Exception:
            pass
    return ""


@router.post("/posts/{post_id}/context-image")
def generate_context_image(post_id: int, request: Request):
    require_permission(request, "autopilot")
    enforce_rate_limit(request, "autopilot-context-image", 6, 300)

    with SessionLocal() as db:
        post = db.get(SocialPost, post_id)
        if not post:
            raise HTTPException(404, "Post not found.")
        context = _story_context(db, post)
        body = (post.body or "").strip()

    prompt = f"""
Create a vertical Instagram editorial image for this specific motorsports post.

POST:
{body}

SOURCE CONTEXT:
{context or "No additional verified context is available."}

Hard rules:
- The image must visually support THIS story, not advertise Pitmark merchandise.
- Do not use shirts, hoodies, storefront product mockups, shopping imagery, or generic Pitmark products.
- If the post discusses a real driver and no verified photograph is supplied, do NOT invent their face, exact car, number, livery, team branding, or identity.
- Instead use a tasteful neutral motorsports editorial scene appropriate to the known story: track atmosphere, grid/paddock, race car details without identifying marks, helmet/crew/pit-lane detail, grandstands, asphalt/dirt texture, or dramatic racing environment.
- Do not invent readable sponsor logos or race results.
- No fake quotation text and no prominent generated typography.
- Compose for 4:5 / Instagram feed cropping with the important visual content centered.
- Pitmark visual feel may use restrained charcoal, black, orange and white accents, but this is a story image first.
""".strip()

    try:
        result = generate_image(prompt=prompt, size="1024x1536", quality="medium")
        stored = store_uploaded_image(
            data=result["data"],
            filename=f"pitmark-context-post-{post_id}.png",
            mime_type=result["mime_type"],
        )
    except (PitmarkImageGenerationError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc

    base = str(request.base_url).rstrip("/")
    public_url = f"{base}/social-assets/{stored['public_token']}"
    asset = add_asset(
        url=public_url,
        title=f"Context image · post #{post_id}",
        source="openai_context",
        source_ref=f"post:{post_id}",
        tags=["generated", "contextual", "editorial", "instagram", "non-product"],
    )

    with SessionLocal() as db:
        post = db.get(SocialPost, post_id)
        if not post:
            raise HTTPException(404, "Post disappeared while generating image.")
        post.media_url = public_url
        post.updated_at = utcnow()
        db.commit()
        db.refresh(post)
        return {
            "ok": True,
            "post": serialize(post),
            "asset": asset,
            "url": public_url,
            "model": result["model"],
        }
