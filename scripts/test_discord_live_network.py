from __future__ import annotations

import json
import unittest

from services import discord_bot_service, discord_live_network


class LiveNetworkTests(unittest.TestCase):
    def test_new_commands_are_registered(self):
        names = {item["name"] for item in discord_bot_service.command_definitions()}
        self.assertTrue({"live", "upcoming", "racealerts", "poll"}.issubset(names))

    def test_filters_match_series_and_track(self):
        item = {
            "series_name": "Lucas Oil Late Model Dirt Series",
            "series_key": "lucas-oil-late-models",
            "group": "Dirt",
            "event": {
                "name": "Jackson 100",
                "venue": "Brownstown Speedway",
                "location": "Brownstown, IN",
            },
        }
        self.assertTrue(
            discord_live_network.matches_config(
                item,
                {"enabled": True, "series": ["lucas oil"], "tracks": ["brownstown"]},
            )
        )
        self.assertFalse(
            discord_live_network.matches_config(
                item,
                {"enabled": True, "series": ["nascar"], "tracks": []},
            )
        )

    def test_poll_vote_updates_single_user_vote(self):
        memory = {}
        original_get = discord_live_network.persistent_store.get_runtime_state
        original_set = discord_live_network.persistent_store.set_runtime_state
        discord_live_network.persistent_store.get_runtime_state = lambda key: memory.get(key)
        discord_live_network.persistent_store.set_runtime_state = lambda key, value: memory.__setitem__(key, value)
        try:
            response = discord_live_network.create_poll(
                guild_id="1",
                user_id="2",
                question="Which widgets do you use every race?",
                options=["Relative", "Standings", "Track Map"],
            )
            custom_id = response["data"]["components"][0]["components"][0]["custom_id"]
            poll_id = custom_id.split(":")[1]
            vote = discord_live_network.vote_poll(custom_id, "99")
            self.assertEqual(vote["type"], 7)
            state = json.loads(memory[f"{discord_live_network.POLL_PREFIX}{poll_id}"])
            self.assertEqual(state["votes"]["99"], 0)

            second_custom_id = response["data"]["components"][0]["components"][1]["custom_id"]
            discord_live_network.vote_poll(second_custom_id, "99")
            state = json.loads(memory[f"{discord_live_network.POLL_PREFIX}{poll_id}"])
            self.assertEqual(state["votes"]["99"], 1)
            self.assertEqual(len(state["votes"]), 1)
        finally:
            discord_live_network.persistent_store.get_runtime_state = original_get
            discord_live_network.persistent_store.set_runtime_state = original_set


class LiveNetworkContractTests(unittest.TestCase):
    def test_poll_custom_id_prefix(self):
        self.assertTrue(
            discord_live_network._poll_components("abc123", ["A", "B"])[0]["components"][0]["custom_id"].startswith(
                "pitmark_poll:"
            )
        )

    def test_event_key_is_stable(self):
        item = {
            "series_key": "test",
            "series_name": "Test Series",
            "event": {"name": "Test 100", "start": "2026-09-25T20:00:00+00:00", "venue": "Test Speedway"},
        }
        self.assertEqual(discord_live_network.event_key(item), discord_live_network.event_key(item))


if __name__ == "__main__":
    unittest.main()
