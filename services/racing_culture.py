from __future__ import annotations

import logging
import os
import threading
import time
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("pitmark.race_center.racing_culture")

DEFAULT_FEED_URL = "https://pitmarkracing.com/blogs/racing-culture.atom"
DEFAULT_SOURCE_URL = "https://pitmarkracing.com/blogs/racing-culture"
_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_cache: dict[str, object] = {
    "at": 0.0,
    "stories": [],
    "error": None,
}


def _clean_text(value: object, limit: int = 320) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _entry_text(entry: ET.Element, ns: dict[str, str], tag: str) -> str:
    node = entry.find(f"a:{tag}", ns)
    return (node.text or "").strip() if node is not None and node.text else ""


def _entry_link(entry: ET.Element, ns: dict[str, str]) -> str:
    links = entry.findall("a:link", ns)
    for link in links:
        if (link.attrib.get("rel") or "alternate") == "alternate" and link.attrib.get("href"):
            return str(link.attrib["href"]).strip()
    for link in links:
        if link.attrib.get("href"):
            return str(link.attrib["href"]).strip()
    return ""


def _story_from_entry(entry: ET.Element, ns: dict[str, str], source_url: str) -> dict:
    title = _entry_text(entry, ns, "title")
    url = _entry_link(entry, ns)
    published = _entry_text(entry, ns, "published") or _entry_text(entry, ns, "updated")
    author = ""
    author_node = entry.find("a:author/a:name", ns)
    if author_node is not None and author_node.text:
        author = _clean_text(author_node.text, 120)

    html_value = ""
    for tag in ("content", "summary"):
        node = entry.find(f"a:{tag}", ns)
        if node is not None and node.text:
            html_value = node.text
            if html_value.strip():
                break

    soup = BeautifulSoup(html_value or "", "html.parser")
    image_url = ""
    image = soup.find("img")
    if image and image.get("src"):
        image_url = urljoin(source_url, str(image.get("src")).strip())
    summary = _clean_text(soup.get_text(" ", strip=True), 360)
    if not summary:
        summary = _clean_text(_entry_text(entry, ns, "summary"), 360)

    categories = []
    for category in entry.findall("a:category", ns):
        term = _clean_text(category.attrib.get("term"), 80)
        if term and term not in categories:
            categories.append(term)

    key = url.rstrip("/").split("/")[-1] if url else _clean_text(title.lower().replace(" ", "-"), 180)
    return {
        "key": key,
        "title": title or "Pitmark Racing Culture",
        "url": url or source_url,
        "published_at": published or None,
        "summary": summary,
        "image_url": image_url or None,
        "author": author or "Pitmark Racing Co.",
        "categories": categories[:8],
        "source_name": "Pitmark Racing Culture",
        "source_url": source_url,
    }


def _fetch_stories() -> list[dict]:
    feed_url = (os.getenv("PITMARK_RACING_CULTURE_FEED_URL") or DEFAULT_FEED_URL).strip()
    source_url = (os.getenv("PITMARK_RACING_CULTURE_URL") or DEFAULT_SOURCE_URL).strip()
    headers = {
        "User-Agent": "PitmarkRaceCenter/1.0 (+https://racecenter.pitmarkracing.com)",
        "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.5",
    }
    with httpx.Client(timeout=4.5, follow_redirects=True, headers=headers) as client:
        response = client.get(feed_url)
        response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    return [
        _story_from_entry(entry, ns, source_url)
        for entry in entries
        if _entry_text(entry, ns, "title")
    ]


def get_racing_culture_feed(*, limit: int = 12, force: bool = False) -> dict:
    safe_limit = max(1, min(int(limit or 12), 30))
    now = time.monotonic()
    with _cache_lock:
        cached_at = float(_cache.get("at") or 0.0)
        cached_stories = list(_cache.get("stories") or [])
        cached_error = _cache.get("error")
        if not force and cached_stories and now - cached_at <= _CACHE_TTL_SECONDS:
            return {
                "generated_at": cached_at,
                "source_name": "Pitmark Racing Culture",
                "source_url": DEFAULT_SOURCE_URL,
                "stories": cached_stories[:safe_limit],
                "stale": False,
                "error": cached_error,
            }

    try:
        stories = _fetch_stories()
    except Exception as exc:
        log.warning("Race Center Racing Culture feed refresh failed: %s", exc)
        with _cache_lock:
            cached_stories = list(_cache.get("stories") or [])
            _cache["error"] = str(exc)[:240]
            if cached_stories:
                return {
                    "generated_at": _cache.get("at"),
                    "source_name": "Pitmark Racing Culture",
                    "source_url": DEFAULT_SOURCE_URL,
                    "stories": cached_stories[:safe_limit],
                    "stale": True,
                    "error": str(exc)[:240],
                }
        return {
            "generated_at": None,
            "source_name": "Pitmark Racing Culture",
            "source_url": DEFAULT_SOURCE_URL,
            "stories": [],
            "stale": True,
            "error": str(exc)[:240],
        }

    with _cache_lock:
        _cache["at"] = now
        _cache["stories"] = stories
        _cache["error"] = None

    return {
        "generated_at": now,
        "source_name": "Pitmark Racing Culture",
        "source_url": DEFAULT_SOURCE_URL,
        "stories": stories[:safe_limit],
        "stale": False,
        "error": None,
    }
