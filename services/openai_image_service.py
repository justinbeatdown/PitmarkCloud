from __future__ import annotations

import base64
import httpx

from utils.config import settings


class PitmarkImageGenerationError(RuntimeError):
    pass


ALLOWED_SIZES = {"1024x1024", "1024x1536", "1536x1024"}
ALLOWED_QUALITIES = {"low", "medium", "high"}


def configured() -> bool:
    return bool(settings.openai_api_key.strip() and settings.pitmark_image_model.strip())


def generate_image(*, prompt: str, size: str = "1024x1024", quality: str = "medium") -> dict:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        raise PitmarkImageGenerationError("Describe the image you want Pitmark to generate.")
    if len(clean_prompt) > 4000:
        raise PitmarkImageGenerationError("Image prompt is too long.")
    if size not in ALLOWED_SIZES:
        raise PitmarkImageGenerationError("Unsupported image size.")
    if quality not in ALLOWED_QUALITIES:
        raise PitmarkImageGenerationError("Unsupported image quality.")
    if not configured():
        raise PitmarkImageGenerationError("OpenAI image generation is not configured.")

    # Keep Pitmark's visual identity consistent without inventing/recreating official logo art.
    pitmark_prompt = (
        "Create a polished motorsports marketing image for Pitmark Racing Co. "
        "Visual direction: dark charcoal/black, energetic racing-poster composition, gritty track texture, "
        "orange/white accents, authentic grassroots motorsports energy, strong depth and lighting. "
        "Do not invent, redraw, approximate, distort, or place the Pitmark logo or wordmark; leave branding-safe "
        "negative space so an official logo asset can be overlaid later if desired. Avoid generic slideshow design. "
        "No tiny unreadable text. User request: " + clean_prompt
    )
    payload = {
        "model": settings.pitmark_image_model.strip(),
        "prompt": pitmark_prompt,
        "size": size,
        "quality": quality,
        "n": 1,
        "output_format": "png",
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=max(45.0, settings.pitmark_image_timeout_seconds)) as client:
            response = client.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = str(exc.response.json().get("error", {}).get("message") or "")
        except Exception:
            pass
        raise PitmarkImageGenerationError(detail or f"Image API returned HTTP {exc.response.status_code}.") from exc
    except Exception as exc:
        raise PitmarkImageGenerationError(f"Image generation failed: {exc}") from exc

    item = (data.get("data") or [{}])[0]
    encoded = item.get("b64_json")
    if not encoded:
        raise PitmarkImageGenerationError("Image API returned no image data.")
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise PitmarkImageGenerationError("Image API returned invalid image data.") from exc
    if not raw:
        raise PitmarkImageGenerationError("Generated image was empty.")
    return {
        "data": raw,
        "mime_type": "image/png",
        "model": settings.pitmark_image_model.strip(),
        "size": size,
        "quality": quality,
        "revised_prompt": item.get("revised_prompt"),
    }
