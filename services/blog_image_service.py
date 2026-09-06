from __future__ import annotations

import base64
import html
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from utils.config import settings

_STAGE_DIR = Path('/tmp/pitmark_blog_images')
_TOKEN_RE = re.compile(r'^[A-Za-z0-9_-]{20,96}$')
_ALLOWED_SUFFIXES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}


@dataclass(frozen=True)
class StagedBlogImage:
    token: str
    path: Path
    media_type: str
    model: str
    attempts: int


def _clean_text(value: str | None, limit: int) -> str:
    raw = html.unescape(value or '')
    raw = re.sub(r'<[^>]+>', ' ', raw)
    raw = re.sub(r'\s+', ' ', raw).strip()
    return raw[:limit]


def build_blog_image_prompt(*, title: str, body_html: str, content_type: str) -> str:
    title_text = _clean_text(title, 240)
    context = _clean_text(body_html, 1200)
    return f"""Create one original landscape editorial hero image for a Pitmark Racing Co. blog article.

Article title: {title_text}
Content type: {_clean_text(content_type, 80)}
Article context: {context}

Visual direction: authentic grassroots American motorsports, short-track and race-paddock atmosphere, premium editorial photography, dramatic but believable track lighting, gritty mechanical detail, energetic composition, black/charcoal environment with restrained orange accents where natural. The image should feel appropriate for a racing news or post-race feature and should visually match the subject without inventing a specific factual event that is not supported by the context.

Important restrictions: no readable words, no typography, no logos, no sponsor marks, no manufacturer trademarks, no copyrighted team liveries, no watermarks, and no UI. Do not recreate any real brand logo. Keep cars and people generic when the article context does not establish exact visual details. Compose for a wide blog header with the main action centered and safe crop room around the edges."""


def _cleanup_old_files() -> None:
    try:
        _STAGE_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - max(300, int(settings.pitmark_blog_image_ttl_seconds))
        for path in _STAGE_DIR.iterdir():
            if not path.is_file() or path.suffix.lower() not in _ALLOWED_SUFFIXES:
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass


def _detect_image_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg', 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png', 'image/png'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp', 'image/webp'
    raise RuntimeError('Image provider returned an unsupported image format')


def _request_image_bytes(prompt: str) -> bytes:
    if not settings.openai_api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured for blog image generation')

    payload = {
        'model': settings.pitmark_image_model,
        'prompt': prompt,
        'size': settings.pitmark_image_size,
        'quality': settings.pitmark_image_quality,
        'output_format': 'jpeg',
        'n': 1,
    }
    attempts = max(1, min(3, int(settings.pitmark_image_max_attempts)))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=float(settings.pitmark_image_timeout_seconds)) as client:
                response = client.post(
                    'https://api.openai.com/v1/images/generations',
                    headers={
                        'Authorization': f'Bearer {settings.openai_api_key}',
                        'Content-Type': 'application/json',
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                detail = ''
                try:
                    message = ((response.json().get('error') or {}).get('message') or '').strip()
                    if message:
                        detail = f': {message[:240]}'
                except Exception:
                    pass
                raise RuntimeError(f'OpenAI image generation failed ({response.status_code}){detail}')

            body = response.json()
            items = body.get('data') or []
            if not items:
                raise RuntimeError('OpenAI image generation returned no image data')
            item = items[0] or {}
            encoded = item.get('b64_json')
            if encoded:
                return base64.b64decode(encoded)

            remote_url = (item.get('url') or '').strip()
            if remote_url:
                with httpx.Client(timeout=float(settings.pitmark_image_timeout_seconds), follow_redirects=True) as client:
                    remote = client.get(remote_url)
                if remote.status_code >= 400:
                    raise RuntimeError(f'Generated image download failed ({remote.status_code})')
                return remote.content

            raise RuntimeError('OpenAI image generation returned no usable image payload')
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2.0, 0.6 * attempt))

    assert last_error is not None
    raise last_error


def generate_and_stage_blog_image(*, title: str, body_html: str, content_type: str) -> StagedBlogImage:
    _cleanup_old_files()
    prompt = build_blog_image_prompt(title=title, body_html=body_html, content_type=content_type)
    data = _request_image_bytes(prompt)
    if len(data) < 2048:
        raise RuntimeError('Generated blog image payload was unexpectedly small')

    suffix, media_type = _detect_image_type(data)
    _STAGE_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path = _STAGE_DIR / f'{token}{suffix}'
    path.write_bytes(data)
    return StagedBlogImage(
        token=token,
        path=path,
        media_type=media_type,
        model=settings.pitmark_image_model,
        attempts=max(1, min(3, int(settings.pitmark_image_max_attempts))),
    )


def resolve_staged_blog_image(token: str) -> tuple[Path, str] | None:
    _cleanup_old_files()
    if not _TOKEN_RE.fullmatch(token or ''):
        return None
    for suffix, media_type in _ALLOWED_SUFFIXES.items():
        candidate = _STAGE_DIR / f'{token}{suffix}'
        try:
            if candidate.is_file():
                age = time.time() - candidate.stat().st_mtime
                if age <= max(300, int(settings.pitmark_blog_image_ttl_seconds)):
                    return candidate, media_type
        except OSError:
            continue
    return None
