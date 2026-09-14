from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from services import shopify_service
from utils.config import settings

log = logging.getLogger("pitmark.discord.racing_culture")

DISCORD_API = "https://discord.com/api/v10"
BLOG_HANDLE = "racing-culture"
CHANNEL_NAME = "racing-culture"
FALLBACK_CHANNEL_NAME = "community-events"
CATEGORY_MATCH = "RACING COMMUNITY"


def configured() -> bool:
    guild_id = (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()
    return bool(settings.discord_bot_token and guild_id)


def _guild_id() -> str:
    return (settings.discord_hq_guild_id or settings.discord_guild_id or "").strip()


def _clean(value: str | None, limit: int = 900) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _snowflake_created_at(value: str) -> datetime:
    milliseconds = (int(value) >> 22) + 1420070400000
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def _recent_articles(limit: int = 12) -> list[dict[str, Any]]:
    data = shopify_service.graphql(
        """
        query PitmarkDiscordRacingCulture {
          articles(first: 30, sortKey: PUBLISHED_AT, reverse: true) {
            nodes {
              id
              title
              handle
              summary
              body
              isPublished
              publishedAt
              image { originalSrc }
              blog { handle title }
            }
          }
        }
        """
    )
    base = (settings.pitmark_public_store_url or "https://pitmarkracing.com").rstrip("/")
    articles: list[dict[str, Any]] = []
    for article in ((data.get("articles") or {}).get("nodes") or []):
        blog = article.get("blog") or {}
        if str(blog.get("handle") or "").strip().lower() != BLOG_HANDLE:
            continue
        if not bool(article.get("isPublished")):
            continue
        handle = str(article.get("handle") or "").strip()
        title = _clean(article.get("title"), 256)
        if not handle or not title:
            continue
        image = str(((article.get("image") or {}).get("originalSrc") or "")).strip()
        articles.append(
            {
                "id": str(article.get("id") or ""),
                "title": title,
                "url": f"{base}/blogs/{BLOG_HANDLE}/{handle}",
                "summary": _clean(article.get("summary") or article.get("body"), 700),
                "image": image,
                "published_at": _parse_dt(article.get("publishedAt")),
            }
        )
        if len(articles) >= max(1, limit):
            break
    return articles


async def _ensure_channel(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    guild_id: str,
) -> tuple[dict[str, Any] | None, bool, bool]:
    response = await client.get(f"{DISCORD_API}/guilds/{guild_id}/channels", headers=headers)
    response.raise_for_status()
    channels = response.json()

    existing = next(
        (
            channel
            for channel in channels
            if int(channel.get("type") or 0) == 0
            and str(channel.get("name") or "").strip().lower() == CHANNEL_NAME
        ),
        None,
    )
    if existing:
        return existing, False, False

    category = next(
        (
            channel
            for channel in channels
            if int(channel.get("type") or 0) == 4
            and CATEGORY_MATCH in str(channel.get("name") or "").upper()
        ),
        None,
    )
    payload: dict[str, Any] = {
        "name": CHANNEL_NAME,
        "type": 0,
        "topic": (
            "Pitmark Racing Co. Racing Culture articles, track news, "
            "race coverage, and real-world motorsports updates."
        ),
    }
    if category:
        payload["parent_id"] = str(category.get("id"))

    create = await client.post(
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        headers=headers,
        json=payload,
    )
    if create.is_success:
        channel = create.json()
        log.info(
            "Created Discord #%s%s.",
            CHANNEL_NAME,
            f" under {category.get('name')}" if category else "",
        )
        return channel, True, False

    log.warning(
        "Could not create Discord #%s (%s); falling back to #%s.",
        CHANNEL_NAME,
        create.status_code,
        FALLBACK_CHANNEL_NAME,
    )
    fallback = next(
        (
            channel
            for channel in channels
            if int(channel.get("type") or 0) == 0
            and str(channel.get("name") or "").strip().lower() == FALLBACK_CHANNEL_NAME
        ),
        None,
    )
    return fallback, False, True


async def _seen_urls(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    channel_id: str,
) -> set[str]:
    response = await client.get(
        f"{DISCORD_API}/channels/{channel_id}/messages",
        headers=headers,
        params={"limit": 100},
    )
    response.raise_for_status()
    seen: set[str] = set()
    for message in response.json():
        content = str(message.get("content") or "")
        seen.update(re.findall(r"https?://[^\s>]+", content))
        for embed in message.get("embeds") or []:
            url = str(embed.get("url") or "").strip()
            if url:
                seen.add(url)
    return seen


def _article_payload(article: dict[str, Any]) -> dict[str, Any]:
    embed: dict[str, Any] = {
        "title": article["title"][:256],
        "url": article["url"],
        "description": article["summary"][:700]
        or "A new Racing Culture story is live on Pitmark Racing Co.",
        "color": 0xFF5500,
        "fields": [
            {
                "name": "Read the full story",
                "value": f"[Open on PitmarkRacing.com]({article['url']})",
                "inline": False,
            }
        ],
        "footer": {"text": "Pitmark Racing Co. • Racing Culture • Leave Your Mark."},
    }
    if article.get("image"):
        embed["image"] = {"url": article["image"]}
    published_at = article.get("published_at")
    if isinstance(published_at, datetime):
        embed["timestamp"] = published_at.astimezone(timezone.utc).isoformat()
    return {
        "content": "🏁 **NEW FROM RACING CULTURE**",
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }


async def sync_racing_culture_feed() -> dict[str, Any]:
    if not configured():
        return {"configured": False, "posted": 0}

    try:
        articles = await asyncio.to_thread(_recent_articles, 12)
    except Exception as exc:
        log.warning("Racing Culture Shopify scan failed: %s", exc)
        return {"configured": True, "posted": 0, "error": "shopify_scan_failed"}

    if not articles:
        return {"configured": True, "posted": 0, "articles": 0}

    guild_id = _guild_id()
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        try:
            channel, created, fallback = await _ensure_channel(client, headers, guild_id)
        except Exception as exc:
            log.warning("Racing Culture Discord channel sync failed: %s", exc)
            return {"configured": True, "posted": 0, "error": "channel_sync_failed"}

        if not channel:
            log.warning(
                "Racing Culture feed has nowhere to post: neither #%s nor #%s is available.",
                CHANNEL_NAME,
                FALLBACK_CHANNEL_NAME,
            )
            return {"configured": True, "posted": 0, "error": "channel_missing"}

        channel_id = str(channel.get("id") or "")
        try:
            seen = await _seen_urls(client, headers, channel_id)
        except Exception as exc:
            log.warning("Could not read Racing Culture Discord history: %s", exc)
            seen = set()

        if created:
            candidates = [article for article in articles[:1] if article["url"] not in seen]
        elif fallback:
            candidates = [article for article in articles[:1] if article["url"] not in seen]
        else:
            created_at = _snowflake_created_at(channel_id) - timedelta(minutes=2)
            candidates = [
                article
                for article in reversed(articles)
                if article["url"] not in seen
                and isinstance(article.get("published_at"), datetime)
                and article["published_at"] >= created_at
            ][-3:]

        posted = 0
        for article in candidates:
            response = await client.post(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                headers=headers,
                json=_article_payload(article),
            )
            if response.is_success:
                posted += 1
                log.info("Posted Racing Culture article to #%s: %s", channel.get("name"), article["title"])
            else:
                log.warning(
                    "Discord rejected Racing Culture post (%s): %s",
                    response.status_code,
                    response.text[:300],
                )

    return {
        "configured": True,
        "posted": posted,
        "channel": str(channel.get("name") or ""),
        "created_channel": created,
        "fallback": fallback,
        "articles": len(articles),
    }
