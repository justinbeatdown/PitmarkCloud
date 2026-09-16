from __future__ import annotations

import unittest


class FakeChannel:
    def __init__(self):
        self.name = "prt-announcements"
        self.type = "text"
        self.sent = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return object()


class FakeGuild:
    def __init__(self, channel: FakeChannel):
        self.id = 123
        self.channels = [channel]


class FakeBot:
    def __init__(self, channel: FakeChannel):
        self.guilds = [FakeGuild(channel)]


class DiscordReleaseRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_older_manifest_is_ignored_without_state_downgrade(self):
        from services import prt_release_announcements as service

        channel = FakeChannel()
        bot = FakeBot(channel)
        state = {service.STATE_KEY: "0.16.82"}
        old_hq = service.settings.discord_hq_guild_id
        old_guild = service.settings.discord_guild_id
        old_channel = service.settings.prt_release_announcement_channel
        service.settings.discord_hq_guild_id = "123"
        service.settings.discord_guild_id = ""
        service.settings.prt_release_announcement_channel = "prt-announcements"

        async def fetch_stale():
            return {
                "version": "0.16.76",
                "summary": "Stale manifest.",
                "changes": ["Old build."],
            }

        try:
            status = await service.run_once(
                bot,
                fetcher=fetch_stale,
                get_state=lambda key: state.get(key),
                set_state=lambda key, value: state.__setitem__(key, value),
            )
        finally:
            service.settings.discord_hq_guild_id = old_hq
            service.settings.discord_guild_id = old_guild
            service.settings.prt_release_announcement_channel = old_channel

        self.assertEqual(status, "stale")
        self.assertEqual(state[service.STATE_KEY], "0.16.82")
        self.assertEqual(channel.sent, [])


class AutopilotReleaseRegressionTests(unittest.TestCase):
    def test_older_manifest_does_not_queue_release_or_downgrade_state(self):
        from services import first_party_sources as sources

        old_load = sources.load_manifest
        old_get = sources.get_state
        old_set = sources.set_state
        old_queue = sources.queue_event
        state_writes = []
        queued = []

        sources.load_manifest = lambda: (
            {"version": "0.16.76", "notes": "Stale manifest."},
            "r2",
        )
        sources.get_state = lambda key: "0.16.82"
        sources.set_state = lambda key, value: state_writes.append((key, value))
        sources.queue_event = lambda **kwargs: queued.append(kwargs) or (999, True)
        try:
            result = sources.scan_prt_release()
        finally:
            sources.load_manifest = old_load
            sources.get_state = old_get
            sources.set_state = old_set
            sources.queue_event = old_queue

        self.assertEqual(result["queued"], 0)
        self.assertTrue(result.get("stale"))
        self.assertEqual(result.get("previous"), "0.16.82")
        self.assertEqual(state_writes, [])
        self.assertEqual(queued, [])


if __name__ == "__main__":
    unittest.main()
