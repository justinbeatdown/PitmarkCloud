from pathlib import Path
import unittest

from services.social_quality_gate import assess_automatic_post_quality


ROOT = Path(__file__).resolve().parents[1]


class SocialQualityGateTests(unittest.TestCase):
    def test_blocks_caption_unrelated_to_article(self):
        result = assess_automatic_post_quality(
            platform="facebook",
            title="Pennsylvania Dirt Weekend Roundup: Colton Flinner, Dave Hess Jr., Marino Angelicchio",
            body="Local track, sim, or both — where are you racing this week? Tag your league, track, team, or racing buddy.",
            source="firstparty:123",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("topic" in reason for reason in result["reasons"]))

    def test_allows_relevant_article_copy(self):
        result = assess_automatic_post_quality(
            platform="facebook",
            title="Pennsylvania Dirt Weekend Roundup: Colton Flinner, Dave Hess Jr., Marino Angelicchio",
            body="Pennsylvania dirt racing delivered another packed weekend. Colton Flinner and Dave Hess Jr. are among the names in our latest roundup.",
            source="firstparty:123",
        )
        self.assertTrue(result["ok"])

    def test_blocks_visibly_truncated_title(self):
        result = assess_automatic_post_quality(
            platform="facebook",
            title="Pennsylvania Dirt Weekend Roundup: Colton Flinner, Dave Hess Jr., Marino Angelicchio and T",
            body="Pennsylvania dirt racing roundup featuring Colton Flinner and Dave Hess Jr.",
            source="dailycampaign:9",
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("truncated" in reason for reason in result["reasons"]))

    def test_automatic_instagram_requires_assigned_media(self):
        result = assess_automatic_post_quality(
            platform="instagram",
            title="Pennsylvania Dirt Weekend Roundup",
            body="Pennsylvania dirt racing is the focus of our newest weekend roundup.",
            source="firstparty:123",
            media_url=None,
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("image" in reason for reason in result["reasons"]))

    def test_manual_posts_are_not_blocked_by_automation_gate(self):
        result = assess_automatic_post_quality(
            platform="instagram",
            title="Anything",
            body="Short",
            source="manual",
            media_url=None,
        )
        self.assertTrue(result["ok"])

    def test_daily_art_does_not_expose_internal_blog_publish_label(self):
        text = (ROOT / "services" / "social_daily_package.py").read_text(encoding="utf-8")
        self.assertIn('"blog_publish": "RACING CULTURE"', text)
        self.assertNotIn('title = _clean(campaign.get("title"), 90)', text)
        self.assertIn('raise ValueError("Headline cannot fit safely without truncation")', text)


if __name__ == "__main__":
    unittest.main()
