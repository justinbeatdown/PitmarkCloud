from __future__ import annotations

import asyncio
import os
import unittest

from services import persistent_store
from services.database import engine


class RuntimeStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        persistent_store.RuntimeStateRow.__table__.create(bind=engine, checkfirst=True)

    def test_runtime_state_round_trip(self):
        key = f"test_prt_release_state_{os.getpid()}"
        persistent_store.set_runtime_state(key, "0.16.999")
        self.assertEqual(persistent_store.get_runtime_state(key), "0.16.999")


class FakeChannel:
    def __init__(self, *, name: str = "prt-announcements", channel_type: str = "text", fail: bool = False):
        self.name = name
        self.type = channel_type
        self.fail = fail
        self.sent = []

    async def send(self, **kwargs):
        if self.fail:
            raise RuntimeError("Discord send failed")
        self.sent.append(kwargs)
        return object()


class FakeGuild:
    def __init__(self, guild_id: str, channels: list[FakeChannel]):
        self.id = int(guild_id)
        self.channels = channels


class FakeBot:
    def __init__(self, guilds: list[FakeGuild]):
        self.guilds = guilds


class ReleaseParsingTests(unittest.TestCase):
    def test_normalize_release_accepts_changes_list(self):
        from services.prt_release_announcements import normalize_release

        release = normalize_release({
            "version": "0.16.82",
            "summary": "Radar and overlay fixes.",
            "changes": ["Fixed radar flashing.", "Improved track-map sizing."],
            "required": True,
        })
        self.assertEqual(release["version"], "0.16.82")
        self.assertEqual(release["changes"], ["Fixed radar flashing.", "Improved track-map sizing."])
        self.assertTrue(release["required"])

    def test_normalize_release_accepts_notes_string(self):
        from services.prt_release_announcements import normalize_release

        release = normalize_release({
            "version": "v0.16.82",
            "notes": "- Fixed radar flashing.\n• Improved track-map sizing.",
        })
        self.assertEqual(release["version"], "0.16.82")
        self.assertEqual(release["changes"], [
            "Fixed radar flashing.",
            "Improved track-map sizing.",
        ])

    def test_normalize_release_rejects_missing_notes(self):
        from services.prt_release_announcements import normalize_release

        with self.assertRaises(ValueError):
            normalize_release({"version": "0.16.82"})

    def test_normalize_release_rejects_notes_version_mismatch(self):
        from services.prt_release_announcements import normalize_release

        with self.assertRaises(ValueError):
            normalize_release({
                "version": "0.16.82",
                "releaseNotes": {
                    "version": "0.16.81",
                    "changes": ["Wrong build notes."],
                },
            })

    def test_embed_contains_branding_and_release_changes(self):
        from services.prt_release_announcements import build_release_embed, normalize_release

        release = normalize_release({
            "version": "0.16.82",
            "notes": "Fixed @everyone radar spam.",
        })
        payload = build_release_embed(release).to_dict()
        self.assertIn("PRT v0.16.82 IS LIVE", payload["title"])
        self.assertIn("Fixed @everyone radar spam.", payload["fields"][0]["value"])
        self.assertIn("Pitmark Racing Co. • Leave Your Mark.", payload["footer"]["text"])


class ReleaseDecisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from services import prt_release_announcements as release_service

        self.release_service = release_service
        self.old_hq = release_service.settings.discord_hq_guild_id
        self.old_guild = release_service.settings.discord_guild_id
        self.old_channel = release_service.settings.prt_release_announcement_channel
        release_service.settings.discord_hq_guild_id = "123"
        release_service.settings.discord_guild_id = ""
        release_service.settings.prt_release_announcement_channel = "prt-announcements"

    def tearDown(self):
        self.release_service.settings.discord_hq_guild_id = self.old_hq
        self.release_service.settings.discord_guild_id = self.old_guild
        self.release_service.settings.prt_release_announcement_channel = self.old_channel

    async def _fetch(self, version: str = "0.16.82"):
        return {
            "version": version,
            "summary": "Release summary.",
            "changes": ["Fixed radar stability."],
        }

    async def test_first_run_bootstraps_without_posting(self):
        channel = FakeChannel()
        bot = FakeBot([FakeGuild("123", [channel])])
        state = {}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "bootstrapped")
        self.assertEqual(state[self.release_service.STATE_KEY], "0.16.82")
        self.assertEqual(channel.sent, [])

    async def test_same_version_does_not_post(self):
        channel = FakeChannel()
        bot = FakeBot([FakeGuild("123", [channel])])
        state = {self.release_service.STATE_KEY: "0.16.82"}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "unchanged")
        self.assertEqual(channel.sent, [])

    async def test_new_version_posts_once_and_persists(self):
        channel = FakeChannel()
        bot = FakeBot([FakeGuild("123", [channel])])
        state = {self.release_service.STATE_KEY: "0.16.81"}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "posted")
        self.assertEqual(state[self.release_service.STATE_KEY], "0.16.82")
        self.assertEqual(len(channel.sent), 1)
        self.assertIn("embed", channel.sent[0])
        self.assertIn("allowed_mentions", channel.sent[0])

        second = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )
        self.assertEqual(second, "unchanged")
        self.assertEqual(len(channel.sent), 1)

    async def test_missing_channel_does_not_persist(self):
        bot = FakeBot([FakeGuild("123", [FakeChannel(name="general")])])
        state = {self.release_service.STATE_KEY: "0.16.81"}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "no-channel")
        self.assertEqual(state[self.release_service.STATE_KEY], "0.16.81")

    async def test_send_failure_does_not_persist(self):
        channel = FakeChannel(fail=True)
        bot = FakeBot([FakeGuild("123", [channel])])
        state = {self.release_service.STATE_KEY: "0.16.81"}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "failed")
        self.assertEqual(state[self.release_service.STATE_KEY], "0.16.81")

    async def test_forum_channel_is_rejected(self):
        channel = FakeChannel(channel_type="forum")
        bot = FakeBot([FakeGuild("123", [channel])])
        state = {self.release_service.STATE_KEY: "0.16.81"}

        status = await self.release_service.run_once(
            bot,
            fetcher=self._fetch,
            get_state=lambda key: state.get(key),
            set_state=lambda key, value: state.__setitem__(key, value),
        )

        self.assertEqual(status, "no-channel")
        self.assertEqual(channel.sent, [])


class ReleaseWatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_watcher_does_not_run_cycle(self):
        from services import prt_release_announcements as release_service

        old_enabled = release_service.settings.prt_release_announcements_enabled
        release_service.settings.prt_release_announcements_enabled = False
        try:
            await release_service.watch(FakeBot([]))
        finally:
            release_service.settings.prt_release_announcements_enabled = old_enabled

    async def test_poll_interval_is_clamped_to_thirty_seconds(self):
        from services import prt_release_announcements as release_service

        old_enabled = release_service.settings.prt_release_announcements_enabled
        old_interval = release_service.settings.prt_release_poll_seconds
        release_service.settings.prt_release_announcements_enabled = True
        release_service.settings.prt_release_poll_seconds = 1
        slept = []
        cycles = 0

        async def fake_run_once(_bot):
            nonlocal cycles
            cycles += 1
            if cycles > 1:
                raise asyncio.CancelledError()
            return "unchanged"

        async def fake_sleep(seconds):
            slept.append(seconds)
            raise asyncio.CancelledError()

        original_run_once = release_service.run_once
        original_sleep = release_service.asyncio.sleep
        release_service.run_once = fake_run_once
        release_service.asyncio.sleep = fake_sleep
        try:
            with self.assertRaises(asyncio.CancelledError):
                await release_service.watch(FakeBot([]))
        finally:
            release_service.run_once = original_run_once
            release_service.asyncio.sleep = original_sleep
            release_service.settings.prt_release_announcements_enabled = old_enabled
            release_service.settings.prt_release_poll_seconds = old_interval

        self.assertEqual(slept, [30])


if __name__ == "__main__":
    unittest.main()
