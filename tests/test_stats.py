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
        rows = [dict(install("aaaaaaaaaaaa", 2, 0.1, uploads=4), body=body, client="0.8.0", os="macOS",
                     region="eu"),
                dict(install("me0000000000", 9, 1, uploads=20), body="not an export", client=None)]
        players = stats.player_rows(rows, {"me0000000000"})
        self.assertEqual([p["you"] for p in players], [False, True])     # most kills first
        top = players[0]
        self.assertEqual((top["mobs"], top["kills"], top["picks"], top["drops"]), (2, 30, 2, 15))
        self.assertEqual((top["client"], top["os"], top["region"], top["uploads"]), ("0.8.0", "macOS", "eu", 4))
        self.assertEqual((players[1]["client"], players[1]["os"]), ("unknown", "not sent"))
        self.assertIsNone(players[1]["kills"])
        self.assertEqual(len(top["tag"]), 5)
        self.assertNotIn(top["tag"], "aaaaaaaaaaaa")                    # a hash, not the ID itself

        lines = stats.player_table(players, NOW, limit=1)
        self.assertIn("0.8.0", lines[1])
        self.assertIn("macOS", lines[1])
        self.assertIn("2 h ago", lines[1])
        self.assertTrue(any("1 more" in line for line in lines))
        self.assertNotIn("aaaaaaaaaaaa", "\n".join(lines))


class DownloadsTests(unittest.TestCase):
    def test_mac_app_isnt_counted_as_the_addon(self):
        import admin_stats
        release = {"tag_name": "v0.8.0", "published_at": "2026-11-20T12:00:00Z", "assets": [
            {"name": "GoldScout-v0.8.0.zip", "download_count": 10},
            {"name": "GoldScoutCompanion.exe", "download_count": 7},
            {"name": "GoldScoutCompanion-macOS.zip", "download_count": 3}]}
        [row] = admin_stats.downloads([release])
        self.assertEqual((row["zip"], row["exe"], row["mac"]), (10, 7, 3))


class WorkerRequestsTests(unittest.TestCase):
    def test_daily_counts_per_worker_and_this_month(self):
        import admin_stats
        sent = {}

        def post(url, headers, body, method):
            sent.update(url=url, auth=headers["Authorization"], body=body)
            row = lambda date, script, n, e=0: {"dimensions": {"date": date, "scriptName": script},  # noqa: E731
                                                "sum": {"requests": n, "errors": e}}
            return {"data": {"viewer": {"accounts": [{"workersInvocationsAdaptive": [
                row("2026-10-31", "goldscout-api", 500), row("2026-11-01", "goldscout-api", 900, 2),
                row("2026-11-01", "goldscout-wow", 100), row("2026-11-10", "goldscout-api", 300, 1)]}]}}}

        now = 1794297600   # 2026-11-10
        usage = admin_stats.worker_requests("token", "acct", now, post=post)
        self.assertEqual(sent["auth"], "Bearer token")
        self.assertIn(b'"account": "acct"', sent["body"])
        self.assertEqual([d["date"] for d in usage["days"]], ["2026-10-31", "2026-11-01", "2026-11-10"])
        self.assertEqual(usage["days"][1]["scripts"], {"goldscout-api": 900, "goldscout-wow": 100})
        self.assertEqual(usage["month"], {"goldscout-api": 1200, "goldscout-wow": 100})   # November only
        self.assertEqual(usage["errors"]["goldscout-api"], 3)

    def test_cloudflare_errors_are_reported(self):
        import admin_stats
        with self.assertRaises(RuntimeError):
            admin_stats.worker_requests("t", "a", 0, post=lambda *a: {"errors": [{"message": "not authorized"}]})

    def test_the_dashboard_is_told_why_there_are_no_request_counts(self):
        import admin_stats
        problems = []

        def attempt(name, fn):
            try:
                return fn()
            except Exception as error:
                problems.append("%s: %s" % (name, error))

        def refused(*_):
            raise RuntimeError("not authorized")

        both = {"CLOUDFLARE_ANALYTICS_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "a"}
        self.assertEqual(admin_stats.request_counts(0, attempt, {"CLOUDFLARE_ANALYTICS_TOKEN": "t"}),
                         {"missing": ["the CLOUDFLARE_ACCOUNT_ID variable"]})
        self.assertEqual(admin_stats.request_counts(0, attempt, both, refused), {"error": "not authorized"})
        self.assertEqual(problems, ["Cloudflare analytics: not authorized"])
        self.assertEqual(admin_stats.request_counts(0, attempt, both, lambda *_: {"days": []}), {"days": []})


class StampTests(unittest.TestCase):
    def test_release_builds_report_the_tag(self):
        import stamp_companion
        text = 'HERE = 1\nVERSION = "0.8.0"  # comment\nOTHER = "VERSION = 1"\n'
        self.assertEqual(stamp_companion.stamp(text, "v0.8.1"),
                         'HERE = 1\nVERSION = "0.8.1"  # comment\nOTHER = "VERSION = 1"\n')
        for bad in ("main", "v0.8", "v0.8.1-beta"):
            with self.assertRaises(ValueError):
                stamp_companion.stamp(text, bad)
        with self.assertRaises(ValueError):
            stamp_companion.stamp("no version here", "v0.8.1")
        app = (ROOT / "companion" / "app.py").read_text(encoding="utf-8")
        self.assertIn('VERSION = "9.9.9"', stamp_companion.stamp(app, "v9.9.9"))


class UserAgentTests(unittest.TestCase):
    def test_names_the_system(self):
        sys.path.insert(0, str(ROOT / "companion"))
        import uploader
        from unittest import mock
        with mock.patch.object(uploader, "OS_NAME", "macOS"):
            self.assertEqual(uploader.user_agent("0.8.0"), "GoldScoutCompanion/0.8.0 (macOS)")
        with mock.patch.object(uploader, "OS_NAME", None):
            self.assertEqual(uploader.user_agent("0.8.0"), "GoldScoutCompanion/0.8.0")


if __name__ == "__main__":
    unittest.main()
