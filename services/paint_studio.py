from __future__ import annotations

import base64

import httpx

from utils.config import settings


class PaintStudioError(RuntimeError):
    pass


SUPPORTED_INPUT_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_INPUT_BYTES = 20 * 1024 * 1024


def configured() -> bool:
    return bool(settings.openai_api_key.strip() and settings.pitmark_image_model.strip())


def _paint_prompt(user_prompt: str, has_guide: bool = False) -> str:
    clean = (user_prompt or "").strip()
    if not clean:
        raise PaintStudioError("Describe the livery you want to create.")
    if len(clean) > 3000:
        raise PaintStudioError("Livery brief is too long.")

    guide_text = (
        "The SECOND supplied image is a protected UV/template guide from the original layered PSD. "
        "Treat it as authoritative geometry and alignment context only: do not move, redraw, restyle, paint over, or reproduce its guide lines in the finished artwork. "
        if has_guide
        else ""
    )
    return (
        "You are assisting an experienced racing graphic designer inside Pitmark Paint Studio. "
        "The FIRST supplied image is the editable paint raster for a real race-car UV template. "
        "Keep its canvas orientation, panel locations, body-part geometry, seams, and alignment stable. "
        + guide_text
        + "Create only the painted livery artwork. Do not redesign the UV/template geometry itself. "
        "Do not invent sponsor logos, brand marks, readable sponsor text, fake contingency decals, driver names, or car numbers; "
        "those are added later from exact uploaded assets. Preserve deliberate transparent/blank technical regions where practical. "
        "Any later supplied image is inspiration only for color, texture, composition, or style, not permission to copy third-party logos or text. "
        "Favor coherent real-world race-livery design with clean panel flow, intentional hierarchy, and production-ready shapes instead of an AI-art poster look. "
        "User livery brief: " + clean
    )


def _validate_optional_image(raw: bytes | None, content_type: str, label: str) -> None:
    if raw is None:
        return
    if content_type not in SUPPORTED_INPUT_TYPES:
        raise PaintStudioError(f"{label} image must be PNG, JPG, or WEBP.")
    if len(raw) > MAX_INPUT_BYTES:
        raise PaintStudioError(f"{label} image must be 20 MB or smaller.")


async def generate_livery_edit(
    *,
    template_bytes: bytes,
    template_name: str,
    template_content_type: str,
    prompt: str,
    guide_bytes: bytes | None = None,
    guide_name: str = "guide.png",
    guide_content_type: str = "image/png",
    reference_bytes: bytes | None = None,
    reference_name: str = "reference.png",
    reference_content_type: str = "image/png",
    quality: str = "medium",
) -> dict:
    if not configured():
        raise PaintStudioError("Pitmark image generation is not configured.")
    if template_content_type not in SUPPORTED_INPUT_TYPES:
        raise PaintStudioError("Use a PNG, JPG, or WEBP editable paint image.")
    if not template_bytes or len(template_bytes) > MAX_INPUT_BYTES:
        raise PaintStudioError("Editable paint image must be between 1 byte and 20 MB.")
    _validate_optional_image(guide_bytes, guide_content_type, "Guide")
    _validate_optional_image(reference_bytes, reference_content_type, "Reference")
    if quality not in {"low", "medium", "high"}:
        quality = "medium"

    files: list[tuple[str, tuple[str, bytes, str]]] = [
        (
            "image[]",
            (template_name or "paint.png", template_bytes, template_content_type),
        )
    ]
    if guide_bytes:
        files.append(
            (
                "image[]",
                (
                    guide_name or "guide.png",
                    guide_bytes,
                    guide_content_type,
                ),
            )
        )
    if reference_bytes:
        files.append(
            (
                "image[]",
                (
                    reference_name or "reference.png",
                    reference_bytes,
                    reference_content_type,
                ),
            )
        )

    data = {
        "model": settings.pitmark_image_model.strip(),
        "prompt": _paint_prompt(prompt, has_guide=bool(guide_bytes)),
        "quality": quality,
        "output_format": "png",
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}"}

    try:
        async with httpx.AsyncClient(timeout=max(60.0, settings.pitmark_image_timeout_seconds)) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/edits",
                headers=headers,
                data=data,
                files=files,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = str(exc.response.json().get("error", {}).get("message") or "")
        except Exception:
            pass
        raise PaintStudioError(detail or f"Image API returned HTTP {exc.response.status_code}.") from exc
    except Exception as exc:
        raise PaintStudioError(f"Livery generation failed: {exc}") from exc

    item = (payload.get("data") or [{}])[0]
    encoded = item.get("b64_json")
    if not encoded:
        raise PaintStudioError("Image API returned no edited image data.")
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise PaintStudioError("Image API returned invalid image data.") from exc
    if not raw:
        raise PaintStudioError("Generated livery was empty.")

    return {
        "data": raw,
        "mime_type": "image/png",
        "model": settings.pitmark_image_model.strip(),
        "revised_prompt": item.get("revised_prompt"),
    }
