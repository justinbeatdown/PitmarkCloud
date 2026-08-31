from __future__ import annotations

import html as html_lib
import logging
import re
from urllib.parse import urlparse

import httpx

from services.shield_ecosystem import inspect_external_url

log = logging.getLogger("pitmark.autopilot.research.pages")

MAX_PAGE_BYTES = 450_000
MAX_PAGE_TEXT = 14_000

BLOCK_TAGS = ("script", "style", "svg", "noscript", "template", "nav", "footer")


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


def fetch_page_excerpt(client: httpx.Client, url: str) -> str:
    verdict = inspect_external_url(url)
    if not verdict.get("safe"):
        return ""
    try:
        response = client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; PitmarkAutopilot/0.15.8; +https://pitmarkracing.com)"
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ""
        raw_bytes = response.content[:MAX_PAGE_BYTES]
        raw = raw_bytes.decode(response.encoding or "utf-8", errors="replace")
        desc = _meta_description(raw)
        body = _clean_html(raw)
        combined = "\n".join(x for x in (desc, body) if x)
        return combined[:MAX_PAGE_TEXT]
    except Exception as exc:
        log.info("Research page fetch failed for %s: %s", url, exc)
        return ""


def enrich_ranked_sources(items: list[dict], limit: int = 8) -> list[dict]:
    """Read a small number of the best safe source pages.

    Search results remain the discovery layer. This is the verification layer:
    it gives synthesis actual page content instead of asking it to infer a
    driver profile from headlines and snippets.
    """
    enriched = [dict(item) for item in items]
    fetched = 0
    with httpx.Client(timeout=12.0) as client:
        for item in enriched:
            if fetched >= limit:
                break
            url = str(item.get("url") or "")
            if not url.startswith(("http://", "https://")):
                continue
            excerpt = fetch_page_excerpt(client, url)
            if not excerpt:
                continue
            item["page_excerpt"] = excerpt
            item["page_read"] = True
            fetched += 1
    return enriched
