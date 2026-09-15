from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from services.content_tools import generate_article_from_source
from services.control_access import access_from_request
from services.control_auth import require_control_user
from services.paint_studio import MAX_ATTACHMENTS, MAX_INPUT_BYTES, PaintAttachment, PaintStudioError, generate_livery_edit
from services.paint_studio_psd import MAX_PSD_BYTES, PsdStudioError, parse_psd_template
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


async def _read_psd_upload(file: UploadFile) -> tuple[bytes, str]:
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".psd"):
        raise HTTPException(400, "Choose an original iRacing .psd template.")
    raw = await file.read(MAX_PSD_BYTES + 1)
    if not raw:
        raise HTTPException(400, "PSD file is empty.")
    if len(raw) > MAX_PSD_BYTES:
        raise HTTPException(400, "PSD file must be 80 MB or smaller.")
    return raw, filename


async def _read_attachment_uploads(files: list[UploadFile], roles: list[str]) -> list[PaintAttachment]:
    if len(files) > MAX_ATTACHMENTS:
        raise HTTPException(400, f"Use no more than {MAX_ATTACHMENTS} attachment images per generation.")
    result: list[PaintAttachment] = []
    for index, file in enumerate(files):
        raw = await file.read(MAX_INPUT_BYTES + 1)
        if not raw:
            continue
        if len(raw) > MAX_INPUT_BYTES:
            raise HTTPException(400, f"Attachment {file.filename or index + 1} must be 20 MB or smaller.")
        content_type = (file.content_type or "application/octet-stream").lower()
        role = roles[index] if index < len(roles) and roles[index] in {"reference", "logo"} else "reference"
        result.append(PaintAttachment(data=raw, name=(file.filename or f"attachment-{index + 1}.png"), content_type=content_type, role=role))
    return result


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
        return RedirectResponse(url=f"/control?next={PAINT_STUDIO_PATH.replace('/', '%2F')}", status_code=302, headers={"Cache-Control": "no-store"})
    if access.role not in {"owner", "admin"}:
        raise HTTPException(403, "Pitmark Paint Studio is restricted to owner/admin accounts.")
    html = (ASSET_DIR / "paint-studio.html").read_text(encoding="utf-8")
    engine = (ASSET_DIR / "paint-studio.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    html = html.replace("<!-- PAINT_STUDIO_ENGINE -->", f"<script>\n{engine}\n</script>")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@router.get("/paint-studio.css", include_in_schema=False)
def paint_studio_css(request: Request):
    _require_paint_studio(request)
    return Response((ASSET_DIR / "paint-studio.css").read_text(encoding="utf-8"), media_type="text/css", headers={"Cache-Control": "no-store"})


@router.get("/paint-studio.js", include_in_schema=False)
def paint_studio_js(request: Request):
    _require_paint_studio(request)
    return Response((ASSET_DIR / "paint-studio.js").read_text(encoding="utf-8"), media_type="application/javascript", headers={"Cache-Control": "no-store"})


@router.post("/paint-studio/psd/import", include_in_schema=False)
async def paint_studio_psd_import(request: Request, psd: UploadFile = File(...)):
    _require_paint_studio(request)
    enforce_rate_limit(request, "paint-studio-psd-import", 12, 900)
    raw, filename = await _read_psd_upload(psd)
    try:
        result = parse_psd_template(raw, filename)
    except PsdStudioError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Paint Studio PSD import failed: {exc}") from exc
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.post("/paint-studio/psd/render", include_in_schema=False)
async def paint_studio_psd_render(request: Request, psd: UploadFile = File(...), role_overrides_json: str = Form("{}")):
    _require_paint_studio(request)
    enforce_rate_limit(request, "paint-studio-psd-render", 20, 900)
    raw, filename = await _read_psd_upload(psd)
    try:
        parsed = json.loads(role_overrides_json or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Layer role overrides were invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(400, "Layer role overrides must be an object.")
    overrides = {str(key): str(value).lower() for key, value in parsed.items()}
    try:
        result = parse_psd_template(raw, filename, overrides)
    except PsdStudioError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Paint Studio PSD re-render failed: {exc}") from exc
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.post("/paint-studio/generate", include_in_schema=False)
async def paint_studio_generate(
    request: Request,
    template: UploadFile = File(...),
    prompt: str = Form(...),
    quality: str = Form("medium"),
    guide: UploadFile | None = File(default=None),
    assets: list[UploadFile] = File(default=[]),
    asset_roles_json: str = Form("[]"),
):
    _require_paint_studio(request)
    enforce_rate_limit(request, "paint-studio-generate", 8, 900)

    template_bytes = await template.read(MAX_INPUT_BYTES + 1)
    guide_bytes = await guide.read(MAX_INPUT_BYTES + 1) if guide else None
    try:
        parsed_roles = json.loads(asset_roles_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Attachment roles were invalid JSON.") from exc
    if not isinstance(parsed_roles, list):
        raise HTTPException(400, "Attachment roles must be a list.")
    roles = [str(role).lower() for role in parsed_roles]
    attachments = await _read_attachment_uploads(assets, roles)

    try:
        result = await generate_livery_edit(
            template_bytes=template_bytes,
            template_name=template.filename or "paint.png",
            template_content_type=(template.content_type or "application/octet-stream").lower(),
            prompt=prompt,
            guide_bytes=guide_bytes,
            guide_name=(guide.filename if guide else "guide.png") or "guide.png",
            guide_content_type=((guide.content_type if guide else "image/png") or "image/png").lower(),
            attachments=attachments,
            quality=quality,
        )
    except PaintStudioError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Paint Studio generation failed: {exc}") from exc

    return Response(result["data"], media_type=result["mime_type"], headers={"Cache-Control": "no-store", "X-Pitmark-Image-Model": result["model"]})
