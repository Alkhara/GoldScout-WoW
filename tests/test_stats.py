"""tools/stats.py: the counting, with fixed data (no server or GitHub)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import stats  # noqa: E402

NOW = 1_800_000_000
DAY = stats.DAY


def install(install_id, joined_days_ago, last_days_ago, uploads=1, version="4"):
    return {"install_id": install_id, "created_at": NOW - joined_days_ago * DAY,
            "updated_at": NOW - last_days_ago * DAY, "uploads": uploads, "version": version}


class StatsTests(unittest.TestCase):
    def test_installs_leave_you_out_of_player_counts(self):
        rows = [install("me0000000000", 10, 0, uploads=20),
                install("aaaaaaaaaaaa", 0.5, 0.2, uploads=2),
                install("bbbbbbbbbbbb", 3, 2, uploads=5, version="3"),
                install("cccccccccccc", 30, 20)]
        s = stats.summarize_installs(rows, NOW, {"me0000000000"}, days=7)
        self.assertEqual((s["installs"], s["mine"], s["others"]), (4, 1, 3))
        self.assertEqual((s["new_24h"], s["new_7d"]), (1, 2))
        self.assertEqual((s["active_24h"], s["active_7d"]), (1, 2))
        self.assertEqual((s["uploads"], s["uploads_others"]), (28, 8))
        self.assertEqual(s["versions"], {"3": 1, "4": 3})
        self.assertEqual(len(s["daily"]), 7)
        self.assertEqual(sum(n for _, n in s["daily"]), 2)   # the 30-day-old one is outside the window

    def test_form_issues(self):
        def issue(login, labels, state="closed"):
            return {"user": {"login": login}, "state": state, "labels": [{"name": n} for n in labels]}
        f = stats.summarize_issues([issue("Alkhara", ["data-submission", "data-valid"]),
                                    issue("player1", ["data-submission", "data-needs-review"], "open"),
                                    issue("player1", ["data-submission", "data-invalid"]),
                                    issue("player2", ["data-submission"], "open")], {"Alkhara"})
        self.assertEqual((f["total"], f["open"], f["people"], f["others"]), (4, 2, 3, 2))
        self.assertEqual(f["by_status"], {"data-valid": 1, "data-needs-review": 1, "data-invalid": 1,
                                          "unchecked": 1})

    def test_merged_submissions(self):
        folder = Path(tempfile.mkdtemp())
        for name in ("c-me0000000000.txt", "29694443-me0000000000.txt", "c-aaaaaaaaaaaa.txt",
                     "123-bbbbbbbbbbbb.txt"):
            (folder / name).write_text("x", encoding="utf-8")
        m = stats.summarize_submissions(folder, {"me0000000000"})
        self.assertEqual((m["files"], m["installs"], m["others"], m["companion"], m["form"]), (4, 3, 2, 2, 2))

    def test_player_table(self):
        body = ("GoldScout-export 4^aaaaaaaaaaaa^3\n"
                "3809^20^2^21^22^1440^0.5400^0.5400^20^Ashenvale Bear^3730:8:8,3702:4:4^1205:1:1\n"
                "4054^10^0^24^25^1440^0.5800^0.5500^10^Laughing Sister^3730:2:2^\n")
        rows = [dict(install("aaaaaaaaaaaa", 2, 0.1, uploads=4), body=body, client="0.7.0"),
                dict(install("me0000000000", 9, 1, uploads=20), body="not an export", client=None)]
        players = stats.player_rows(rows, {"me0000000000"})
        self.assertEqual([p["you"] for p in players], [False, True])     # most kills first
        top = players[0]
        self.assertEqual((top["mobs"], top["kills"], top["picks"], top["drops"]), (2, 30, 2, 15))
        self.assertEqual((top["client"], top["uploads"]), ("0.7.0", 4))
        self.assertEqual(players[1]["client"], "unknown")
        self.assertIsNone(players[1]["kills"])
        self.assertEqual(len(top["tag"]), 5)
        self.assertNotIn(top["tag"], "aaaaaaaaaaaa")                    # a hash, not the ID itself

        lines = stats.player_table(players, NOW, limit=1)
        self.assertIn("0.7.0", lines[1])
        self.assertIn("2 h ago", lines[1])
        self.assertTrue(any("1 more" in line for line in lines))
        self.assertNotIn("aaaaaaaaaaaa", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
