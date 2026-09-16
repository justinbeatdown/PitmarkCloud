from __future__ import annotations

import unittest


class SocialDailyPackageContractTests(unittest.TestCase):
    def test_visual_specs_are_exact_phone_first_sizes(self):
        from services.social_daily_package import IG_OUTPUT_SIZE, VERTICAL_OUTPUT_SIZE
        self.assertEqual(IG_OUTPUT_SIZE, (1080, 1350))
        self.assertEqual(VERTICAL_OUTPUT_SIZE, (1080, 1920))

    def test_slide_plan_has_six_distinct_story_beats(self):
        from services.social_daily_package import build_slide_plan
        campaign = {
            "title": "PRT v0.16.82 is live",
            "summary": "A new Pitmark Racing Tools patch shipped with stability improvements.",
            "url": "https://prt.pitmarkracing.com",
            "topic_type": "prt_release",
        }
        plan = build_slide_plan(campaign)
        self.assertEqual(len(plan["instagram"]), 6)
        self.assertGreaterEqual(len(plan["vertical"]), 4)
        self.assertEqual(len({item["headline"] for item in plan["instagram"]}), 6)
        self.assertTrue(all(item["visual_prompt"] for item in plan["instagram"]))

    def test_queue_platforms_exclude_tiktok_direct_publish(self):
        from services.social_daily_package import QUEUE_PLATFORMS, COPY_PLATFORMS
        self.assertEqual(COPY_PLATFORMS, ("facebook", "instagram", "x", "discord", "tiktok_reels"))
        self.assertEqual(QUEUE_PLATFORMS, ("facebook", "instagram", "x", "discord"))
        self.assertNotIn("tiktok_reels", QUEUE_PLATFORMS)

    def test_asset_prompt_forbids_logo_redraw_and_fake_specifics(self):
        from services.social_daily_package import visual_prompt
        text = visual_prompt(
            campaign={"title": "Local racing culture", "summary": "Pitmark community feature", "topic_type": "blog_publish", "url": ""},
            headline="Built at the track",
            beat="Show the racing atmosphere without inventing a person or car.",
            aspect="4:5",
        ).lower()
        self.assertIn("do not draw", text)
        self.assertIn("pitmark logo", text)
        self.assertIn("do not invent", text)
        self.assertIn("text-safe", text)


if __name__ == "__main__":
    unittest.main()
