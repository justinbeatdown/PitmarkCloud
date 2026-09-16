from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from services import discord_racing_culture_feed as feed


class FakeResponse:
    is_success = True


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, **kwargs):
        self.posts.append({"url": url, **kwargs})
        return FakeResponse()


class RacingCultureImageGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_feed_holds_article_until_featured_image_exists(self):
        article = {
            "id": "gid://shopify/Article/1",
            "title": "Test Racing Story",
            "url": "https://pitmarkracing.com/blogs/racing-culture/test-racing-story",
            "summary": "Test summary.",
            "image": "",
            "published_at": datetime.now(timezone.utc),
        }
        clients = []

        def client_factory(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            clients.append(client)
            return client

        with (
            patch.object(feed, "configured", return_value=True),
            patch.object(feed, "_guild_id", return_value="123"),
            patch.object(feed, "_recent_articles", return_value=[article]),
            patch.object(
                feed,
                "_ensure_channel",
                new=AsyncMock(
                    return_value=(
                        {"id": "123456789012345678", "name": "racing-culture"},
                        True,
                        False,
                    )
                ),
            ),
            patch.object(feed, "_seen_urls", new=AsyncMock(return_value=set())),
            patch.object(feed.httpx, "AsyncClient", side_effect=client_factory),
        ):
            held = await feed.sync_racing_culture_feed()
            self.assertEqual(held["posted"], 0)
            self.assertEqual(clients[0].posts, [])

            article["image"] = "https://cdn.shopify.com/test-racing-story.jpg"
            posted = await feed.sync_racing_culture_feed()
            self.assertEqual(posted["posted"], 1)
            self.assertEqual(len(clients[1].posts), 1)
            embed = clients[1].posts[0]["json"]["embeds"][0]
            self.assertEqual(embed["image"]["url"], article["image"])


if __name__ == "__main__":
    unittest.main()
