from pathlib import Path
import unittest

from services.racing_culture_conversion import append_racing_culture_conversion_cta


ROOT = Path(__file__).resolve().parents[1]
MARKER = 'data-pitmark-racing-culture-cta="1"'


class RacingCultureConversionCtaTests(unittest.TestCase):
    def test_cta_is_tracked_and_idempotent(self):
        body = "<p>Race story body.</p>"
        title = "Williams Grove: 64th National Open!"

        result = append_racing_culture_conversion_cta(body, title)

        self.assertEqual(result.count(MARKER), 1)
        self.assertIn("Keep Local Racing Visible", result)
        self.assertIn("/products/support-your-local-track-t-shirt-racing-garage-crew-tee?", result)
        self.assertIn("/products/support-your-local-track-t-shirt-racing-sunset-graphic-tee?", result)
        self.assertIn("/collections/all?", result)
        self.assertEqual(result.count("utm_source=racing_culture"), 3)
        self.assertEqual(result.count("utm_medium=article"), 3)
        self.assertEqual(result.count("utm_campaign=keep_local_racing_visible"), 3)
        self.assertEqual(result.count("utm_content=williams_grove_64th_national_open"), 3)

        second_pass = append_racing_culture_conversion_cta(result, title)
        self.assertEqual(second_pass, result)
        self.assertEqual(second_pass.count(MARKER), 1)

    def test_guarded_publisher_applies_cta_only_to_racing_culture_blog(self):
        text = (ROOT / "api" / "blog_publish_guard.py").read_text(encoding="utf-8")
        self.assertIn("append_racing_culture_conversion_cta", text)
        self.assertIn('== "racing-culture"', text)
        self.assertIn("append_racing_culture_conversion_cta(d.body_html, d.title)", text)


if __name__ == "__main__":
    unittest.main()
