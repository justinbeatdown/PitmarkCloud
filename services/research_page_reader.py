from __future__ import annotations

import html as html_lib
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from services.shield_ecosystem import inspect_external_url

log = logging.getLogger("pitmark.autopilot.research.pages")

MAX_PAGE_BYTES = 450_000
MAX_PAGE_TEXT = 14_000
MAX_REDIRECTS = 6

BLOCK_TAGS = ("script", "style", "svg", "noscript", "template", "nav", "footer")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/144.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@dataclass(frozen=True)
class PageReadResult:
    ok: bool
    excerpt: str = ""
    reason: str = ""
    category: str = "fetch"
    status_code: int | None = None
    final_url: str | None = None


def _clean_html(raw: str) -> str:
    text = raw or ""
    for tag in BLOCK_TAGS:
        text = re.sub(fr"<{tag}\b[^>]*>.*?</{tag}>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(?:p|div|li|h[1-6]|tr|section|article)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _meta_description(raw: str) -> str:
    patterns = (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    )
    for pattern in patterns:
        m = re.search(pattern, raw or "", re.I | re.S)
        if m:
            return _clean_html(m.group(1))[:1200]
    return ""


def _excerpt_from_html(raw: str) -> str:
    desc = _meta_description(raw)
    body = _clean_html(raw)
    combined = "\n".join(x for x in (desc, body) if x)
    return combined[:MAX_PAGE_TEXT]


def _decode_response(response: httpx.Response) -> str:
    raw_bytes = response.content[:MAX_PAGE_BYTES]
    return raw_bytes.decode(response.encoding or "utf-8", errors="replace")


def _safe_get(client: httpx.Client, url: str) -> tuple[httpx.Response | None, PageReadResult | None]:
    """GET a public URL while re-running Shield on every redirect target."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        verdict = inspect_external_url(current)
        if not verdict.get("safe"):
            return None, PageReadResult(
                ok=False,
                reason=str(verdict.get("reason") or "URL blocked by Shield"),
                category="shield",
                final_url=current,
            )
        try:
            response = client.get(current, headers=BROWSER_HEADERS, follow_redirects=False)
        except httpx.HTTPError as exc:
            return None, PageReadResult(
                ok=False,
                reason=f"{type(exc).__name__}: {exc}",
                category="fetch",
                final_url=current,
            )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                return None, PageReadResult(
                    ok=False,
                    reason="redirect response did not include a Location header",
                    category="fetch",
                    status_code=response.status_code,
                    final_url=current,
                )
            current = urljoin(current, location)
            continue
        return response, None
    return None, PageReadResult(
        ok=False,
        reason=f"too many redirects (>{MAX_REDIRECTS})",
        category="fetch",
        final_url=current,
    )


def _wordpress_api_url(source_url: str) -> str | None:
    """Build a same-origin WordPress REST fallback for normal post permalinks."""
    parsed = urlparse(source_url)
    slug = parsed.path.rstrip("/").split("/")[-1]
    if not slug or "." in slug:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return f"{origin}/wp-json/wp/v2/posts?slug={slug}&_fields=link,title,excerpt,content"


def _wordpress_fallback(client: httpx.Client, source_url: str) -> PageReadResult:
    api_url = _wordpress_api_url(source_url)
    if not api_url:
        return PageReadResult(ok=False, reason="no compatible article fallback was available", category="fetch", final_url=source_url)
    response, failure = _safe_get(client, api_url)
    if failure:
        return failure
    assert response is not None
    if response.status_code != 200:
        return PageReadResult(
            ok=False,
            reason=f"WordPress fallback returned HTTP {response.status_code}",
            category="fetch",
            status_code=response.status_code,
            final_url=str(response.url),
        )
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" not in content_type:
        return PageReadResult(ok=False, reason=f"WordPress fallback returned {content_type or 'unknown content type'}", category="content", final_url=str(response.url))
    try:
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return PageReadResult(ok=False, reason="WordPress fallback did not find that article slug", category="content", final_url=str(response.url))
        row = rows[0] if isinstance(rows[0], dict) else {}
        parts = []
        for key in ("title", "excerpt", "content"):
            value = row.get(key) or {}
            rendered = value.get("rendered") if isinstance(value, dict) else value
            if rendered:
                parts.append(str(rendered))
        excerpt = _excerpt_from_html("\n".join(parts))
        if not excerpt:
            return PageReadResult(ok=False, reason="WordPress fallback returned no readable article text", category="content", final_url=str(response.url))
        return PageReadResult(ok=True, excerpt=excerpt, category="ok", status_code=200, final_url=str(response.url))
    except Exception as exc:
        return PageReadResult(ok=False, reason=f"WordPress fallback parse failed: {type(exc).__name__}", category="content", final_url=str(response.url))


def read_page_excerpt(client: httpx.Client, url: str) -> PageReadResult:
    """Read a public article with Shield-safe redirects and useful diagnostics.

    A normal browser-like request is used because some public publishers reject
    self-identifying automation user agents. If the HTML endpoint is blocked by
    publisher bot protection, a same-origin WordPress REST post endpoint is
    attempted when the URL shape supports it.
    """
    response, failure = _safe_get(client, url)
    if failure:
        log.info("Research page read failed for %s [%s]: %s", url, failure.category, failure.reason)
        return failure
    assert response is not None

    if response.status_code == 200:
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" in content_type or "application/xhtml" in content_type:
            excerpt = _excerpt_from_html(_decode_response(response))
            if excerpt:
                return PageReadResult(ok=True, excerpt=excerpt, category="ok", status_code=200, final_url=str(response.url))
            primary = PageReadResult(ok=False, reason="page returned HTML but no readable article text", category="content", status_code=200, final_url=str(response.url))
        else:
            primary = PageReadResult(ok=False, reason=f"page returned unsupported content type: {content_type or 'unknown'}", category="content", status_code=200, final_url=str(response.url))
    else:
        primary = PageReadResult(ok=False, reason=f"publisher returned HTTP {response.status_code}", category="fetch", status_code=response.status_code, final_url=str(response.url))

    # Public WordPress publishers frequently expose the post through wp-json
    # even when their front-end WAF challenges server-side readers.
    if primary.status_code in {202, 401, 403, 406, 429, 503} or primary.category == "content":
        fallback = _wordpress_fallback(client, url)
        if fallback.ok:
            log.info("Research page used WordPress fallback for %s after %s", url, primary.reason)
            return fallback
        combined = PageReadResult(
            ok=False,
            reason=f"{primary.reason}; fallback failed: {fallback.reason}",
            category=fallback.category,
            status_code=fallback.status_code or primary.status_code,
            final_url=fallback.final_url or primary.final_url,
        )
        log.info("Research page read failed for %s [%s]: %s", url, combined.category, combined.reason)
        return combined

    log.info("Research page read failed for %s [%s]: %s", url, primary.category, primary.reason)
    return primary


def fetch_page_excerpt(client: httpx.Client, url: str) -> str:
    """Compatibility wrapper used by Research Agent enrichment."""
    result = read_page_excerpt(client, url)
    return result.excerpt if result.ok else ""


def enrich_ranked_sources(items: list[dict], limit: int = 8) -> list[dict]:
    """Read a small number of the best safe source pages."""
    enriched = [dict(item) for item in items]
    fetched = 0
    with httpx.Client(timeout=12.0) as client:
        for item in enriched:
            if fetched >= limit:
                break
            url = str(item.get("url") or "")
            if not url.startswith(("http://", "https://")):
                continue
            result = read_page_excerpt(client, url)
            if not result.ok:
                item["page_read"] = False
                item["page_read_reason"] = result.reason
                item["page_read_category"] = result.category
                continue
            item["page_excerpt"] = result.excerpt
            item["page_read"] = True
            item["page_read_via"] = result.final_url
            fetched += 1
    return enriched
