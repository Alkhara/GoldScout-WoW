"""The CurseForge description (tools/store_page.py): always ready to paste as it is,
and reviewed for every hand-made release."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import store_page  # noqa: E402

GOOD = """**GoldScout** ranks farms.

### Farm tab
- mobs, cloth and herbs

---

### Links
- Website: https://wowgoldscout.com
"""
PAGE = "Intro.\n\n**Description reviewed for:** v1.2.3\n\nMore."


class StorePageTests(unittest.TestCase):
    def test_the_description_is_ready_to_paste(self):
        self.assertEqual(store_page.problems(), [])

    def test_the_page_names_the_version_it_was_reviewed_for(self):
        self.assertRegex(store_page.reviewed() or "", r"^v\d+\.\d+\.\d+$")

    def test_every_command_the_help_lists_is_in_the_description(self):
        # A new /gscout command belongs in the description's Commands line.
        ui = (ROOT / "GoldScout" / "UI.lua").read_text(encoding="utf-8")
        help_text = ui.split("local function PrintHelp()", 1)[1].split("\nend", 1)[0]
        commands = set(re.findall(r"/gscout (\w+)", help_text))
        description = store_page.DESCRIPTION.read_text(encoding="utf-8")
        listed = set(re.findall(r"`/gscout (\w+)", description))
        missing = commands - listed - {"options", "errors", "reset", "set", "farm", "craft", "welcome"}
        self.assertEqual(missing, set())

    def test_a_release_needs_the_description_reviewed_for_it(self):
        self.assertIsNone(store_page.check("v1.2.3", PAGE, GOOD))
        problem = store_page.check("v1.2.4", PAGE, GOOD)
        self.assertIn("last reviewed for v1.2.3", problem)
        self.assertIn('"**Description reviewed for:** v1.2.4"', problem)
        self.assertIn("no version", store_page.check("v1.2.3", "Intro.", GOOD))

    def test_what_cant_be_pasted_as_it_is(self):
        self.assertEqual(store_page.problems(GOOD), [])
        cases = {
            "# GoldScout\n\n" + GOOD: "page title",
            GOOD + "<!-- note -->": "HTML comment",
            GOOD.split("### Links")[0]: "no '### Links' section",
            "See https://wowgoldscout.com\n\n" + GOOD: "before '### Links'",
            GOOD + "- https://example.com/GoldScoutCompanion.exe\n": "straight to a download",
            GOOD + "Also on Wago.\n": "Wago",
            "A free addon.\n\n" + GOOD: "free",
        }
        for text, expected in cases.items():
            with self.subTest(expected):
                self.assertTrue(any(expected in problem for problem in store_page.problems(text)),
                                store_page.problems(text))

    def test_free_counts_only_as_a_whole_word(self):
        self.assertEqual(store_page.problems("Free-roaming mobs.\n\n" + GOOD), ["it says \"free\" (left out of "
                                                                                "GoldScout's promotional text)"])
        self.assertEqual(store_page.problems("Spawns freely.\n\n" + GOOD), [])


if __name__ == "__main__":
    unittest.main()
