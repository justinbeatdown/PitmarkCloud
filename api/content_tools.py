from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel

from services.content_tools import generate_article_from_source
from services.control_access import access_from_request
from services.control_auth import require_control_user
from services.paint_studio import MAX_INPUT_BYTES, PaintStudioError, generate_livery_edit
from utils.security import enforce_rate_limit

router = APIRouter()
ASSET_DIR = Path(__file__).resolve().parent
PAINT_STUDIO_PATH = "/api/control/content/paint-studio"


class ArticleFromSourceRequest(BaseModel):
    source_url: str
    prompt: str = "Make our own story about this article."


def _require_paint_studio(request: Request):
    access = access_from_request(request)
    if not access or not access.active:
        raise HTTPException(401, "Control Center authentication required.")
    if access.role not in {"owner", "admin"}:
        raise HTTPException(403, "Pitmark Paint Studio is restricted to owner/admin accounts.")
    return access


@router.post("/article-from-source")
def article_from_source(req: ArticleFromSourceRequest, request: Request):
    require_control_user(request, None)
    enforce_rate_limit(request, "article-from-source", 8, 300)
    try:
        return generate_article_from_source(req.source_url.strip(), req.prompt.strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Article generation failed: {exc}") from exc


@router.get("/paint-studio", response_class=HTMLResponse, include_in_schema=False)
def paint_studio(request: Request):
    access = access_from_request(request)
    if not access or not access.active:
        return RedirectResponse(
            url=f"/control?next={PAINT_STUDIO_PATH.replace('/', '%2F')}",
            status_code=302,
            headers={"Cache-Control": "no-store"},
        )
    if access.role not in {"owner", "admin"}:
        raise HTTPException(403, "Pitmark Paint Studio is restricted to owner/admin accounts.")
    html = (ASSET_DIR / "paint-studio.html").read_text(encoding="utf-8")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/paint-studio.css", include_in_schema=False)
def paint_studio_css(request: Request):
    _require_paint_studio(request)
    return Response(
        (ASSET_DIR / "paint-studio.css").read_text(encoding="utf-8"),
        media_type="text/css",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/paint-studio.js", include_in_schema=False)
def paint_studio_js(request: Request):
    _require_paint_studio(request)
    return Response(
        (ASSET_DIR / "paint-studio.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/paint-studio/generate", include_in_schema=False)
async def paint_studio_generate(
    request: Request,
    template: UploadFile = File(...),
    prompt: str = Form(...),
    quality: str = Form("medium"),
    reference: UploadFile | None = File(default=None),
):
    _require_paint_studio(request)
    enforce_rate_limit(request, "paint-studio-generate", 8, 900)

    template_bytes = await template.read(MAX_INPUT_BYTES + 1)
    reference_bytes = await reference.read(MAX_INPUT_BYTES + 1) if reference else None
    try:
        result = await generate_livery_edit(
            template_bytes=template_bytes,
            template_name=template.filename or "template.png",
            template_content_type=(template.content_type or "application/octet-stream").lower(),
            prompt=prompt,
            reference_bytes=reference_bytes,
            reference_name=(reference.filename if reference else "reference.png") or "reference.png",
            reference_content_type=((reference.content_type if reference else "image/png") or "image/png").lower(),
            quality=quality,
        )
    except PaintStudioError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Paint Studio generation failed: {exc}") from exc

    return Response(
        result["data"],
        media_type=result["mime_type"],
        headers={
            "Cache-Control": "no-store",
            "X-Pitmark-Image-Model": result["model"],
        },
    )