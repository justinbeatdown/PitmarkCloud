from __future__ import annotations

"""Post newly published Pitmark Facebook/Instagram content to Discord HQ."""

import asyncio
import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from services import meta_publish_service, persistent_store
from services.discord_hq_common import DISCORD_API, discord_request
from utils.config import settings

log = logging.getLogger("pitmark.discord.social_media")

CHANNEL_NAME = "social-media"
STATE_PREFIX = "discord_social_media_feed_v1:"
POLL_LIMIT = 12
MAX_POSTS_PER_POLL = 3
FOLLOW_LINKS = {
    "facebook": "https://www.facebook.com/profile.php?id=61593441036636",
    "instagram": "https://www.instagram.com/pitmarkracing/",
}
PLATFORM_LABELS = {"facebook": "Facebook", "instagram": "Instagram"}
PLATFORM_EMOJIS = {"facebook": "📘", "instagram": "📸"}


def configured() -> bool:
    guild_id = str(settings.discord_hq_guild_id or "").strip()
    return bool(
        settings.discord_bot_token
        and guild_id
        and (meta_publish_service.facebook_configured() or meta_publish_service.instagram_configured())
    )


def _published_at(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _permalink(value: Any, platform: str) -> str:
    """Use only actual public post URLs returned by the platform."""
    url = str(value or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = (
        ("facebook.com", "fb.watch")
        if platform == "facebook"
        else ("instagram.com",)
    )
    if parsed.scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed):
        return ""
    return url if parsed.path not in {"", "/"} or parsed.query else ""


def _clean_caption(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:650]


def _fetch_published_posts() -> tuple[list[dict[str, Any]], list[str]]:
    """Read the public post permalinks, including posts published via Metricool."""
    posts: list[dict[str, Any]] = []
    errors: list[str] = []
    page_token = meta_publish_service._page_token()

    specs = [
        (
            "facebook",
            meta_publish_service.facebook_configured(),
            settings.meta_page_id,
            "published_posts",
            "id,message,created_time,permalink_url,full_picture",
        ),
        (
            "instagram",
            meta_publish_service.instagram_configured(),
            settings.meta_instagram_account_id,
            "media",
            "id,caption,timestamp,permalink,media_url,thumbnail_url,media_type",
        ),
    ]
    for platform, enabled, account_id, edge, fields in specs:
        if not enabled:
            continue
        try:
            response = httpx.get(
                meta_publish_service._graph_url(account_id, edge),
                params={"access_token": page_token, "fields": fields, "limit": POLL_LIMIT},
                timeout=20.0,
            )
            data = meta_publish_service._decode(response)
        except (httpx.HTTPError, ValueError, RuntimeError) as exc:
            # Do not log tokens or a complete provider response.
            log.warning("Discord social-media %s scan failed: %s", platform, type(exc).__name__)
            errors.append(platform)
            continue

        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            url = _permalink(item.get("permalink_url" if platform == "facebook" else "permalink"), platform)
            when = _published_at(item.get("created_time" if platform == "facebook" else "timestamp"))
            post_id = str(item.get("id") or "").strip()
            if not (post_id and url and when):
                continue
            image = item.get("full_picture") if platform == "facebook" else (
                item.get("thumbnail_url") or item.get("media_url")
            )
            image_url = str(image or "").strip()
            if not image_url.startswith("https://"):
                image_url = ""
            posts.append(
                {
                    "key": platform + ":" + post_id,
                    "platform": platform,
                    "url": url,
                    "caption": _clean_caption(item.get("message" if platform == "facebook" else "caption")),
                    "image": image_url,
                    "published_at": when,
                }
            )
    return posts, errors


def _payload(post: dict[str, Any]) -> dict[str, Any]:
    platform = post["platform"]
    label = PLATFORM_LABELS[platform]
    emoji = PLATFORM_EMOJIS[platform]
    description = post["caption"] or "Our newest Pitmark Racing Co. post is live. Check it out!"
    embed: dict[str, Any] = {
        "title": "New Pitmark post on " + label,
        "url": post["url"],
        "description": description,
        "color": 0xFF5500,
        "footer": {"text": "Pitmark Racing Co. • Leave Your Mark."},
        "timestamp": post["published_at"].isoformat(),
    }
    if post["image"]:
        embed["thumbnail"] = {"url": post["image"]}
    return {
        "content": emoji + " **NEW ON " + label.upper() + "** • Come show Pitmark some love! 🏁",
        "embeds": [embed],
        "components": [
            {
                "type": 1,
                "components": [
                    {"type": 2, "style": 5, "label": "View original post", "url": post["url"]},
                    {"type": 2, "style": 5, "label": "Follow Pitmark on " + label, "url": FOLLOW_LINKS[platform]},
                ],
            }
        ],
        "allowed_mentions": {"parse": []},
    }


async def _ensure_channel(guild_id: str) -> str:
    response = await discord_request("GET", f"{DISCORD_API}/guilds/{guild_id}/channels")
    channels = response.json()
    existing = next(
        (
            ch for ch in channels
            if int(ch.get("type") or 0) == 0
            and str(ch.get("name") or "").lower() == CHANNEL_NAME
        ),
        None,
    )
    if existing:
        return str(existing["id"])

    category = next(
        (
            ch for ch in channels
            if int(ch.get("type") or 0) == 4
            and "PITMARK CENTRAL" in str(ch.get("name") or "").upper()
        ),
        None,
    )
    payload: dict[str, Any] = {
        "name": CHANNEL_NAME,
        "type": 0,
        "topic": "Follow Pitmark Racing Co. across Facebook, Instagram and more. Direct links to our latest posts.",
        # Read-only for members, while the HQ bot has Administrator access.
        "permission_overwrites": [
            {"id": guild_id, "type": 0, "allow": "0", "deny": str(1 << 11)}
        ],
    }
    if category:
        payload["parent_id"] = str(category["id"])
    response = await discord_request(
        "POST", f"{DISCORD_API}/guilds/{guild_id}/channels",
        json=payload,
        reason="Set up Pitmark social-media announcement feed",
    )
    response.raise_for_status()
    return str(response.json()["id"])


async def _recent_link_history(channel_id: str) -> set[str]:
    response = await discord_request(
        "GET", f"{DISCORD_API}/channels/{channel_id}/messages", params={"limit": 100},
    )
    response.raise_for_status()
    result: set[str] = set()
    for message in response.json():
        for embed in message.get("embeds") or []:
            link = str(embed.get("url") or "")
            if link:
                result.add(link)
        for row in message.get("components") or []:
            for item in row.get("components") or []:
                link = str(item.get("url") or "")
                if link:
                    result.add(link)
    return result


def _load_state(key: str, now: datetime) -> tuple[datetime, set[str]]:
    raw = persistent_store.get_runtime_state(key)
    if not raw:
        # No historical flood on first rollout; only announce posts published
        # within the preceding 10 minutes.
        return now - timedelta(minutes=10), set()
    data = json.loads(raw)
    started = _published_at(data.get("started_at"))
    if started is None or not isinstance(data.get("seen"), list):
        raise ValueError("invalid Discord social-media feed state")
    return started, set(str(x) for x in data["seen"])


async def sync_social_media_feed() -> dict[str, Any]:
    if not configured():
        return {"configured": False, "posted": 0}

    now = datetime.now(timezone.utc)
    try:
        posts, source_errors = await asyncio.to_thread(_fetch_published_posts)
    except Exception:
        log.exception("Discord social-media scan failed")
        return {"configured": True, "posted": 0, "error": "source_scan_failed"}

    guild_id = str(settings.discord_hq_guild_id).strip()
    try:
        # Don't initialize the durable state until we have a usable channel.
        channel_id = await _ensure_channel(guild_id)
        state_key = STATE_PREFIX + guild_id
        started_at, seen = await asyncio.to_thread(_load_state, state_key, now)
        history = await _recent_link_history(channel_id)
    except Exception:
        log.exception("Discord social-media channel/state setup failed")
        return {"configured": True, "posted": 0, "error": "channel_or_state_failed"}

    # If one platform is temporarily unavailable, never infer post URLs.
    candidates = sorted(
        (
            post for post in posts
            if post["published_at"] >= started_at
            and post["published_at"] <= now + timedelta(minutes=2)
            and post["key"] not in seen
        ),
        key=lambda p: (p["published_at"], p["key"]),
    )[:MAX_POSTS_PER_POLL]

    # When a newly created feed channel has no history, showcase up to one
    # recently published post per platform. This permits a safe end-to-end
    # launch test without reposting to Facebook/Instagram or changing a queue.
    # Once a Discord post is present (and tracked), regular scheduling resumes.
    if not seen and not history and not source_errors:
        latest_by_platform: dict[str, dict[str, Any]] = {}
        sample_cutoff = now - timedelta(hours=3)
        for post in posts:
            if not (sample_cutoff <= post["published_at"] <= now + timedelta(minutes=2)):
                continue
            platform = post["platform"]
            current = latest_by_platform.get(platform)
            if current is None or post["published_at"] > current["published_at"]:
                latest_by_platform[platform] = post
        if latest_by_platform:
            sample = sorted(
                latest_by_platform.values(),
                key=lambda p: (p["published_at"], p["key"]),
            )
            candidates = sample[:2]
            log.info(
                "Seeding empty Discord #%s with %s recent verified post(s).",
                CHANNEL_NAME, len(candidates),
            )

    posted = 0
    for post in candidates:
        if post["url"] not in history:
            try:
                response = await discord_request(
                    "POST", f"{DISCORD_API}/channels/{channel_id}/messages",
                    json=_payload(post),
                )
                response.raise_for_status()
            except Exception:
                log.exception("Discord social-media announcement failed for %s", post["key"])
                continue
            posted += 1
            history.add(post["url"])
        seen.add(post["key"])
        # Persist after each success to avoid duplicate messages on restart.
        await asyncio.to_thread(
            persistent_store.set_runtime_state,
            state_key,
            json.dumps({
                "started_at": started_at.isoformat(),
                "seen": sorted(seen)[-1000:],
            }),
        )

    if not candidates:
        await asyncio.to_thread(
            persistent_store.set_runtime_state,
            state_key,
            json.dumps({"started_at": started_at.isoformat(), "seen": sorted(seen)[-1000:]}),
        )

    return {
        "configured": True,
        "posted": posted,
        "channel": CHANNEL_NAME,
        "source_errors": source_errors,
    }
