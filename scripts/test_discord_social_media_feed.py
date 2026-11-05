from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from services import discord_social_media_feed as feed


class PostedResponse:
    def raise_for_status(self):
        return None


class SocialMediaFeedTests(unittest.IsolatedAsyncioTestCase):
    def test_only_real_provider_permalinks_are_accepted(self):
        self.assertEqual(
            feed._permalink("https://www.instagram.com/p/C12345/", "instagram"),
            "https://www.instagram.com/p/C12345/",
        )
        self.assertEqual(
            feed._permalink("https://www.facebook.com/123/posts/456", "facebook"),
            "https://www.facebook.com/123/posts/456",
        )
        self.assertEqual(feed._permalink("https://example.com/p/123", "instagram"), "")
        self.assertEqual(feed._permalink("http://instagram.com/p/123", "instagram"), "")
        self.assertEqual(feed._permalink("https://instagram.com.evil.test/p/123", "instagram"), "")
        self.assertEqual(feed._permalink("https://www.instagram.com/", "instagram"), "")

    def test_discord_message_links_to_the_individual_post(self):
        item = {
            "key": "instagram:1",
            "platform": "instagram",
            "url": "https://www.instagram.com/p/C12345/",
            "caption": "The newest Pitmark driver feature!",
            "image": "",
            "published_at": datetime.now(timezone.utc),
        }
        payload = feed._payload(item)
        self.assertEqual(payload["embeds"][0]["url"], item["url"])
        self.assertEqual(payload["components"][0]["components"][0]["url"], item["url"])
        self.assertIn("instagram.com/pitmarkracing", payload["components"][0]["components"][1]["url"])
        self.assertEqual(payload["allowed_mentions"]["parse"], [])

    async def test_sends_only_new_posts_and_persists_deduplication(self):
        now = datetime.now(timezone.utc)
        recent = {
            "key": "facebook:77",
            "platform": "facebook",
            "url": "https://www.facebook.com/123/posts/77",
            "caption": "Race day!",
            "image": "",
            "published_at": now - timedelta(minutes=2),
        }
        old = {
            "key": "facebook:76",
            "platform": "facebook",
            "url": "https://www.facebook.com/123/posts/76",
            "caption": "Old news",
            "image": "",
            "published_at": now - timedelta(days=1),
        }
        with (
            patch.object(feed, "configured", return_value=True),
            patch.object(feed.settings, "discord_hq_guild_id", "123456789"),
            patch.object(feed, "_fetch_published_posts", return_value=([old, recent], [])),
            patch.object(feed, "_ensure_channel", new=AsyncMock(return_value="987654321")),
            patch.object(feed, "_load_state", return_value=(now - timedelta(minutes=10), set())),
            patch.object(feed, "_recent_link_history", new=AsyncMock(return_value=set())),
            patch.object(feed, "discord_request", new=AsyncMock(return_value=PostedResponse())) as send,
            patch.object(feed.persistent_store, "set_runtime_state") as persist,
        ):
            result = await feed.sync_social_media_feed()
        self.assertEqual(result["posted"], 1)
        self.assertEqual(send.await_count, 1)
        self.assertIn("View original post", str(send.await_args))
        self.assertEqual(persist.call_count, 1)
        self.assertIn("facebook:77", persist.call_args.args[1])

    async def test_history_prevents_repost_after_successful_discord_send(self):
        now = datetime.now(timezone.utc)
        url = "https://www.instagram.com/p/C12345/"
        post = {
            "key": "instagram:77", "platform": "instagram", "url": url,
            "caption": "New feature", "image": "", "published_at": now,
        }
        with (
            patch.object(feed, "configured", return_value=True),
            patch.object(feed.settings, "discord_hq_guild_id", "123456789"),
            patch.object(feed, "_fetch_published_posts", return_value=([post], [])),
            patch.object(feed, "_ensure_channel", new=AsyncMock(return_value="987654321")),
            patch.object(feed, "_load_state", return_value=(now - timedelta(minutes=5), set())),
            patch.object(feed, "_recent_link_history", new=AsyncMock(return_value={url})),
            patch.object(feed, "discord_request", new=AsyncMock()) as send,
            patch.object(feed.persistent_store, "set_runtime_state") as persist,
        ):
            result = await feed.sync_social_media_feed()
        self.assertEqual(result["posted"], 0)
        send.assert_not_awaited()
        self.assertIn("instagram:77", persist.call_args.args[1])


    async def test_empty_channel_seeds_one_latest_recent_post_per_platform(self):
        now = datetime.now(timezone.utc)
        def post(platform: str, marker: str, age: int) -> dict:
            host = "www.instagram.com" if platform == "instagram" else "www.facebook.com"
            return {
                "key": f"{platform}:{marker}",
                "platform": platform,
                "url": f"https://{host}/p/{marker}/",
                "caption": "Pitmark social test",
                "image": "",
                "published_at": now - timedelta(minutes=age),
            }

        fb_old = post("facebook", "fb-old", 110)
        fb_new = post("facebook", "fb-new", 30)
        ig_new = post("instagram", "ig-new", 25)
        too_old = post("instagram", "ig-old", 300)
        sent = []
        async def fake_request(method, url, *, json=None):
            sent.append(json)
            return PostedResponse()

        with (
            patch.object(feed, "configured", return_value=True),
            patch.object(feed.settings, "discord_hq_guild_id", "123456789"),
            patch.object(feed, "_fetch_published_posts", return_value=([fb_old, fb_new, ig_new, too_old], [])),
            patch.object(feed, "_ensure_channel", new=AsyncMock(return_value="987654321")),
            patch.object(feed, "_load_state", return_value=(now - timedelta(minutes=10), set())),
            patch.object(feed, "_recent_link_history", new=AsyncMock(return_value=set())),
            patch.object(feed, "discord_request", side_effect=fake_request),
            patch.object(feed.persistent_store, "set_runtime_state") as persist,
        ):
            result = await feed.sync_social_media_feed()

        self.assertEqual(result["posted"], 2)
        self.assertEqual(
            {item["embeds"][0]["url"] for item in sent},
            {fb_new["url"], ig_new["url"]},
        )
        self.assertEqual(persist.call_count, 2)

    async def test_existing_channel_with_history_does_not_backfill_old_content(self):
        now = datetime.now(timezone.utc)
        old = {
            "key": "facebook:old", "platform": "facebook",
            "url": "https://www.facebook.com/test/posts/old",
            "caption": "Already past", "image": "",
            "published_at": now - timedelta(minutes=50),
        }
        with (
            patch.object(feed, "configured", return_value=True),
            patch.object(feed.settings, "discord_hq_guild_id", "123456789"),
            patch.object(feed, "_fetch_published_posts", return_value=([old], [])),
            patch.object(feed, "_ensure_channel", new=AsyncMock(return_value="987654321")),
            patch.object(feed, "_load_state", return_value=(now - timedelta(minutes=10), set())),
            patch.object(feed, "_recent_link_history", new=AsyncMock(return_value={"https://www.facebook.com/existing/posts/1"})),
            patch.object(feed, "discord_request", new=AsyncMock()) as send,
            patch.object(feed.persistent_store, "set_runtime_state"),
        ):
            result = await feed.sync_social_media_feed()
        self.assertEqual(result["posted"], 0)
        send.assert_not_awaited()

if __name__ == "__main__":
    unittest.main()
