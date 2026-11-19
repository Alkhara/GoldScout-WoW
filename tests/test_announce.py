"""Release announcements on Discord (tools/announce.py): what's posted, and that patch notes never spell out a
security problem."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import announce  # noqa: E402
import changelog  # noqa: E402

CHANGELOG = """# What's new in GoldScout

## Unreleased

## v1.2.4

- **Bag coins:** a gold coin on bag items worth listing
  on the auction house.
- Security fix.
- Updated drop data from the community.

## v1.2.3

- **Faster Farm tab.**
"""


class AnnounceTests(unittest.TestCase):
    def test_a_release_with_notes(self):
        payload = announce.message("v1.2.4", CHANGELOG)
        embed = payload["embeds"][0]
        self.assertEqual(embed["title"], "GoldScout v1.2.4 is out")
        self.assertEqual(embed["url"], "https://github.com/Alkhara/GoldScout-WoW/releases/tag/v1.2.4")
        self.assertEqual(embed["description"], "- **Bag coins:** a gold coin on bag items worth listing on the "
                                               "auction house.\n- Security fix.\n- Updated drop data from the community.")
        self.assertIn("CurseForge", embed["fields"][0]["value"])
        self.assertEqual(payload["allowed_mentions"], {"parse": []})    # never pings anyone
        json.dumps(payload)                                            # sendable as is

    def test_data_releases_arent_announced(self):
        self.assertIsNone(announce.message("v1.2.5", CHANGELOG))

    def test_security_details_never_go_out(self):
        text = CHANGELOG.replace("- Security fix.\n", "- Fixed a password leak in the companion.\n"
                                                       "- Fixed an exploit that let anyone bypass the upload token.\n")
        self.assertTrue(announce.sensitive(text))
        description = announce.message("v1.2.4", text)["embeds"][0]["description"]
        self.assertNotIn("password", description)
        self.assertNotIn("exploit", description)
        self.assertEqual(description.count(announce.SAFE_LINE), 1)          # one plain line for both
        self.assertIn("Bag coins", description)

    def test_wording_that_is_fine(self):
        for text in ("Security fix.", "Security and stability fixes.", "Fixed a Lua error in the Farm tab.",
                     "GoldScout Companion bundles the latest Pillow image library, which fixes published security "
                     "issues."):
            self.assertEqual(announce.sensitive(text), [], text)
        for text in ("Fixed a password leak", "an XSS on the share page", "CVE-2026-1234", "leaked install IDs",
                     "unauthorized uploads", "an attacker could"):
            self.assertTrue(announce.sensitive(text), text)

    def test_every_release_note_in_the_changelog_is_safe_to_publish(self):
        # Pushing runs the tests, so wording that says too much never reaches a release (daily data releases
        # publish "Unreleased" too).
        for heading, body in changelog.sections(changelog.CHANGELOG.read_text(encoding="utf-8")).items():
            self.assertEqual(announce.sensitive(body), [], "CHANGELOG.md %s: write \"Security fix\" instead" % heading)

    def test_long_notes_are_cut_at_a_line(self):
        many = "## v2.0.0\n\n" + "".join("- Change number %d with some words.\n" % i for i in range(400))
        description = announce.message("v2.0.0", many)["embeds"][0]["description"]
        self.assertLessEqual(len(description), 4096)
        self.assertTrue(description.endswith("see the full notes on GitHub."))

    def test_posting(self):
        sent = {}

        class Response:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def opener(request, timeout):
            sent.update(url=request.full_url, body=json.loads(request.data), method=request.get_method())
            return Response()
        payload = announce.message("v1.2.4", CHANGELOG)
        self.assertEqual(announce.post("https://discord.example/hook", payload, opener), 204)
        self.assertEqual((sent["method"], sent["body"]), ("POST", payload))


if __name__ == "__main__":
    unittest.main()
