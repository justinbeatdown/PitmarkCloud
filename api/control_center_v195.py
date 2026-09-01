from __future__ import annotations

import re
from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from services.control_auth import require_control_user
from services.control_center import BlogDraft, serialize, utcnow
from services.database import SessionLocal

router = APIRouter()


def _auth(request: Request, admin_key: str | None):
    return require_control_user(request, admin_key)


def normalize_blog_html(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return text

    # Common AI/Markdown artifacts that should never reach Shopify literally.
    text = re.sub(
        r'(?im)^\s*#{1,4}\s*(sources?|references?)\s*:?\s*$',
        r'<h3>Sources</h3>',
        text,
    )
    text = re.sub(
        r'(?is)<p>\s*(?:#{1,4}\s*)?(sources?|references?)\s*:?\s*</p>',
        r'<h3>Sources</h3>',
        text,
    )
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', text)

    # Process only text segments outside existing anchors.
    pieces = re.split(r'(<[^>]+>)', text)
    out: list[str] = []
    anchor_depth = 0
    md_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
    url_pattern = re.compile(r'(?<!["\'>])(https?://[^\s<]+)')

    for piece in pieces:
        if not piece:
            continue
        if piece.startswith("<") and piece.endswith(">"):
            lower = piece.lower()
            if re.match(r'<a\b', lower):
                anchor_depth += 1
            elif re.match(r'</a\s*>', lower):
                anchor_depth = max(0, anchor_depth - 1)
            out.append(piece)
            continue

        if anchor_depth:
            out.append(piece)
            continue

        placeholders: list[str] = []

        def md_replace(match: re.Match[str]) -> str:
            label = match.group(1)
            url = match.group(2).rstrip('.,;')
            token = f"__PM_LINK_{len(placeholders)}__"
            placeholders.append(
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
            )
            return token

        segment = md_pattern.sub(md_replace, piece)

        def url_replace(match: re.Match[str]) -> str:
            raw = match.group(1)
            trimmed = raw.rstrip('.,;)')
            suffix = raw[len(trimmed):]
            return f'<a href="{trimmed}" target="_blank" rel="noopener noreferrer">{trimmed}</a>{suffix}'

        segment = url_pattern.sub(url_replace, segment)
        for i, replacement in enumerate(placeholders):
            segment = segment.replace(f"__PM_LINK_{i}__", replacement)
        out.append(segment)

    text = "".join(out)
    text = re.sub(
        r'(?i)<h3>\s*(sources?|references?)\s*</h3>',
        r'<h3 style="margin:28px 0 10px;font-size:1.15em">Sources</h3>',
        text,
    )
    return text


@router.post('/blog/drafts/{draft_id}/normalize')
def normalize_blog_draft(
    draft_id: int,
    request: Request,
    x_pitmark_admin_key: str | None = Header(default=None),
):
    _auth(request, x_pitmark_admin_key)
    with SessionLocal() as db:
        draft = db.get(BlogDraft, draft_id)
        if not draft:
            raise HTTPException(404, 'Blog draft not found.')
        draft.body_html = normalize_blog_html(draft.body_html)
        if hasattr(draft, 'updated_at'):
            draft.updated_at = utcnow()
        db.commit()
        db.refresh(draft)
        return {'ok': True, 'draft': serialize(draft), 'body_html': draft.body_html}
