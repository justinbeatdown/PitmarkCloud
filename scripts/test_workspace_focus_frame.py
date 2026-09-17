from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceFocusFrameContract(unittest.TestCase):
    def test_scroll_workspace_never_draws_browser_focus_frame(self):
        css = (ROOT / 'api/control_center_overhaul.css').read_text(encoding='utf-8')
        normalized = ''.join(css.split())
        self.assertIn('.pm-workspace:focus,.pm-workspace:focus-visible{outline:none}', normalized)


if __name__ == '__main__':
    unittest.main()
