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

    had_block_html = bool(re.search(
        r'<(?:p|h[1-6]|ul|ol|li|blockquote|section|div|figure|table)\b',
        text,
        flags=re.I,
    ))

    # Markdown headings -> actual semantic article headings.
    text = re.sub(r'(?im)^\s*####\s+(.+?)\s*$', r'<h3>\1</h3>', text)
    text = re.sub(r'(?im)^\s*###\s+(.+?)\s*$', r'<h3>\1</h3>', text)
    text = re.sub(r'(?im)^\s*##\s+(.+?)\s*$', r'<h2>\1</h2>', text)
    text = re.sub(r'(?im)^\s*#\s+(.+?)\s*$', r'<h2>\1</h2>', text)
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', text)

    # If the generator returned plain/Markdown text, build real paragraphs/lists.
    if not had_block_html:
        blocks = [x.strip() for x in re.split(r'\n\s*\n+', text) if x.strip()]
        formatted: list[str] = []
        for block in blocks:
            if re.match(r'^<h[1-6]\b', block, flags=re.I):
                formatted.append(block)
                continue

            lines = [x.strip() for x in block.splitlines() if x.strip()]
            if lines and all(re.match(r'^[-*]\s+', line) for line in lines):
                items = ''.join(
                    f'<li>{re.sub(r"^[-*]\s+", "", line)}</li>'
                    for line in lines
                )
                formatted.append(f'<ul>{items}</ul>')
                continue

            if lines and all(re.match(r'^\d+[.)]\s+', line) for line in lines):
                items = ''.join(
                    f'<li>{re.sub(r"^\d+[.)]\s+", "", line)}</li>'
                    for line in lines
                )
                formatted.append(f'<ol>{items}</ol>')
                continue

            formatted.append(f'<p>{"<br>".join(lines)}</p>')
        text = '\n'.join(formatted)

    # Process URLs only in text outside existing <a> tags.
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
            return (
                f'<a href="{trimmed}" target="_blank" '
                f'rel="noopener noreferrer">{trimmed}</a>{suffix}'
            )

        segment = url_pattern.sub(url_replace, segment)
        for i, replacement in enumerate(placeholders):
            segment = segment.replace(f"__PM_LINK_{i}__", replacement)
        out.append(segment)

    text = "".join(out)

    # Keep sources consistent and clean.
    text = re.sub(
        r'(?i)<p>\s*(sources?|references?)\s*:?\s*</p>',
        r'<h3>Sources</h3>',
        text,
    )
    text = re.sub(
        r'(?i)<h[1-6]>\s*(sources?|references?)\s*:?\s*</h[1-6]>',
        r'<h3>Sources</h3>',
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
