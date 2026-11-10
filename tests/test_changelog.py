"""Release notes from CHANGELOG.md (tools/changelog.py)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import changelog  # noqa: E402

SAMPLE = """# What's new in GoldScout

Intro text.

## Unreleased

- A new thing.

## v1.2.0

- **Big:** feature.
- Small fix.

## v1.1.0

- Older.

Older releases: see GitHub.
"""


class NotesTests(unittest.TestCase):
    def test_a_release_gets_its_own_section(self):
        notes = changelog.notes("v1.2.0", SAMPLE, counts=(10, 2))
        self.assertIn("## What's new in GoldScout v1.2.0", notes)
        self.assertIn("- **Big:** feature.\n- Small fix.", notes)
        self.assertNotIn("A new thing", notes)

    def test_the_last_section_stops_before_the_footer(self):
        self.assertNotIn("Older releases", changelog.notes("v1.1.0", SAMPLE, counts=(10, 2)))

    def test_a_data_release_says_what_data_it_ships_and_whats_unreleased(self):
        notes = changelog.notes("v1.2.1", SAMPLE, counts=(97, 4))
        self.assertIn("drop rates for 97 mobs, shared by 4 players", notes)
        self.assertIn("Also in this release:", notes)
        self.assertIn("- A new thing.", notes)
        quiet = changelog.notes("v1.2.1", SAMPLE.replace("- A new thing.\n", ""), counts=(1, 1))
        self.assertIn("shared by 1 player.", quiet)
        self.assertNotIn("Also in this release", quiet)

    def test_releasing_by_hand_needs_notes(self):
        self.assertIsNone(changelog.check("v1.2.0", SAMPLE))
        self.assertIn('rename "## Unreleased"', changelog.check("v1.3.0", SAMPLE))
        self.assertIn("write what's new", changelog.check("v1.3.0", SAMPLE.replace("- A new thing.\n", "")))

    def test_the_real_changelog_and_community_data_read(self):
        found = changelog.sections(changelog.CHANGELOG.read_text(encoding="utf-8"))
        self.assertIn("Unreleased", found)
        mobs, contributors = changelog.community_counts()
        self.assertGreater(mobs, 0)
        self.assertGreater(contributors, 0)


if __name__ == "__main__":
    unittest.main()
