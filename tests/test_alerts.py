"""server/src/alerts.js: which problems alert, and that each goes to Discord
once when it starts, daily while it lasts and once when it clears. Runs the
real module in Node (tests/alerts_logic.mjs); skipped without node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
NOW = 1_800_000_000
HOUR = 3600


def call(fn, *args):
    done = subprocess.run([NODE, str(ROOT / "tests" / "alerts_logic.mjs")], input=json.dumps({"fn": fn, "args": args}),
                          capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(done.stdout)


def healthy(**changes):
    data = {
        "houses": [{"region": r, "snapshot": NOW - 1800, "items": 100} for r in ("us", "eu", "kr", "tw")],
        "statsUpdated": NOW - 1200,
        "snapshot": {"workflows": [{"file": "ah-prices.yml", "name": "Auction prices", "latest": {
            "status": "completed", "conclusion": "success", "url": "https://github.com/x/runs/1"}}]},
        "errors24": {"errors": 0, "players": 0},
    }
    data.update(changes)
    return data


def problems(data):
    return call("findProblems", data, NOW)


def plan(stored, current, now=NOW):
    return call("planAlerts", stored, current, now)


ON = {"key": "_on", "message": "", "since": NOW - 99 * HOUR, "notified": NOW - 99 * HOUR}


@unittest.skipUnless(NODE, "node isn't installed")
class FindProblemsTests(unittest.TestCase):
    def test_a_healthy_server_has_none(self):
        self.assertEqual(problems(healthy()), {})

    def test_stale_or_missing_prices_alert_per_region(self):
        houses = [{"region": "us", "snapshot": NOW - 4 * HOUR, "items": 100},
                  {"region": "eu", "snapshot": NOW - 600, "items": 100},
                  {"region": "kr", "snapshot": NOW - 600, "items": 0}]     # empty houses don't count
        found = problems(healthy(houses=houses))
        self.assertEqual(sorted(found), ["prices:kr", "prices:tw", "prices:us"])
        self.assertIn("4 h old", found["prices:us"])
        self.assertIn("none on the server", found["prices:tw"])

    def test_prices_under_three_hours_are_fine(self):
        houses = [{"region": r, "snapshot": NOW - 2 * HOUR, "items": 1} for r in ("us", "eu", "kr", "tw")]
        self.assertEqual(problems(healthy(houses=houses)), {})

    def test_a_silent_data_merge_alerts(self):
        self.assertIn("4 h ago", problems(healthy(statsUpdated=NOW - 4 * HOUR))["stats"])

    def test_failed_workflows_alert_with_their_run_but_cancelled_ones_dont(self):
        def flow(conclusion):
            return {"workflows": [{"file": "backup.yml", "name": "Back up database", "latest": {
                "status": "completed", "conclusion": conclusion, "url": "https://github.com/x/runs/9"}}]}
        found = problems(healthy(snapshot=flow("failure")))
        self.assertIn("https://github.com/x/runs/9", found["workflow:backup.yml"])
        self.assertEqual(problems(healthy(snapshot=flow("cancelled"))), {})
        self.assertEqual(problems(healthy(snapshot=None)), {})

    def test_a_stuck_data_pull_request_alerts_after_two_hours(self):
        def pr(**fields):
            return {"workflows": [], "data_pr": dict({"number": 147, "url": "https://github.com/x/pull/147",
                                                       "created": NOW - 600, "updated": NOW - 600}, **fields)}
        self.assertEqual(problems(healthy(snapshot=pr())), {})   # a slow website build merges on the next run
        found = problems(healthy(snapshot=pr(created=NOW - 3 * HOUR)))["data_pr"]
        self.assertIn("open 3 h", found)
        self.assertIn("https://github.com/x/pull/147", found)
        self.assertIn("open 3 h", problems(healthy(snapshot=pr(created=None, updated=NOW - 3 * HOUR)))["data_pr"])
        self.assertEqual(problems(healthy(snapshot={"workflows": [], "data_pr": None})), {})

    def test_held_uploads_alert_right_away(self):
        def snap(held):
            return {"workflows": [], "held_uploads": held}
        found = problems(healthy(snapshot=snap({"count": 1, "url": "https://github.com/x/runs/5"})))["held"]
        self.assertIn("1 upload is held for review, so its data isn't in the community data", found)
        self.assertIn("data/approved-installs.txt", found)
        self.assertIn("https://github.com/x/runs/5", found)
        self.assertIn("2 uploads are held", problems(healthy(snapshot=snap({"count": 2, "url": None})))["held"])
        self.assertEqual(problems(healthy(snapshot=snap({"count": 0, "url": None}))), {})
        self.assertEqual(problems(healthy(snapshot=snap(None))), {})

    def test_workflows_running_short_alert(self):
        def flow(file, expected, runs, created=NOW - 600):
            return {"file": file, "name": file, "expected_24h": expected, "runs_24h": runs,
                    "latest": {"status": "completed", "conclusion": "success", "created": created, "url": None}}
        snap = {"workflows": [flow("ah-prices.yml", 96, 40), flow("data-merge.yml", 24, 12),
                              flow("tests.yml", None, 0), flow("backup.yml", 1, 1)]}
        found = problems(healthy(snapshot=snap))
        self.assertEqual(sorted(found), ["runs:ah-prices.yml"])   # 12 of 24 is half: fine
        self.assertIn("ran 40 times in the last 24 h, where about 96 is normal", found["runs:ah-prices.yml"])
        late = problems(healthy(snapshot={"workflows": [flow("backup.yml", 1, 0, NOW - 27 * HOUR)]}))
        self.assertIn("hasn't run for 27 h", late["runs:backup.yml"])
        self.assertEqual(problems(healthy(snapshot={"workflows": [flow("backup.yml", 1, 0, NOW - 25 * HOUR)]})), {})

    def test_no_uploads_for_half_a_day_alerts(self):
        self.assertEqual(problems(healthy(uploads={"newest": NOW - 11 * HOUR})), {})
        self.assertEqual(problems(healthy(uploads={"newest": None})), {})   # a new server with no installs
        self.assertIn("No uploads from players for 13 h", problems(healthy(uploads={"newest": NOW - 13 * HOUR}))["uploads"])

    def test_data_waiting_for_a_release_alerts_after_30_hours(self):
        def snap(waiting):
            return {"workflows": [], "data_release": {"latest": "v0.12.15", "published": NOW - 40 * HOUR,
                                                      "waiting_since": waiting}}
        self.assertEqual(problems(healthy(snapshot=snap(None))), {})
        self.assertEqual(problems(healthy(snapshot=snap(NOW - 29 * HOUR))), {})
        found = problems(healthy(snapshot=snap(NOW - 31 * HOUR)))["data_release"]
        self.assertIn("waited 31 h for a release (the latest, v0.12.15, came out 40 h ago)", found)
        self.assertIn("data-release.yml", found)

    def test_failed_workflow_starts_alert_while_they_keep_failing(self):
        row = {"key": "_dispatch", "message": "Could not start ah-prices.yml (HTTP 401)", "since": NOW - 9 * HOUR}
        found = problems(healthy(dispatch=dict(row, notified=NOW - 900)))
        self.assertIn("couldn't start workflows on GitHub: Could not start ah-prices.yml (HTTP 401)", found["dispatch"])
        self.assertIn("GITHUB_DISPATCH_TOKEN", found["dispatch"])
        self.assertEqual(problems(healthy(dispatch=dict(row, notified=NOW - 3 * HOUR))), {})

    def test_errors_alert_from_three_players(self):
        self.assertEqual(problems(healthy(errors24={"errors": 2, "players": 2})), {})
        self.assertIn("from 3 players", problems(healthy(errors24={"errors": 1, "players": 3}))["errors"])


@unittest.skipUnless(NODE, "node isn't installed")
class PlanAlertsTests(unittest.TestCase):
    def test_the_first_run_says_alerts_are_on(self):
        result = plan([], {})
        self.assertIn("alerts are on", result["text"])
        self.assertEqual(result["writes"][0][1:3], ["_on", ""])
        self.assertEqual(plan([ON], {}), {"text": "", "writes": []})          # once

    def test_a_new_problem_is_sent_once(self):
        result = plan([ON], {"prices:us": "US prices are old."})
        self.assertEqual(result["text"], "🔴 US prices are old.")
        stored = [ON, {"key": "prices:us", "message": "US prices are old.", "since": NOW, "notified": NOW}]
        self.assertEqual(plan(stored, {"prices:us": "US prices are old."}, NOW + 3 * HOUR)["text"], "")

    def test_an_open_problem_is_repeated_daily(self):
        stored = [ON, {"key": "stats", "message": "Merge quiet.", "since": NOW - 30 * HOUR, "notified": NOW - 24 * HOUR}]
        result = plan(stored, {"stats": "Merge quiet still."})
        self.assertEqual(result["text"], "🔴 Still, for 30 h: Merge quiet still.")
        self.assertEqual(result["writes"], [["UPDATE alerts SET message = ?, notified = ? WHERE key = ?",
                                             "Merge quiet still.", NOW, "stats"]])

    def test_a_cleared_problem_is_reported_and_forgotten(self):
        stored = [ON, {"key": "errors", "message": "Errors from 3 players.", "since": NOW - 5 * HOUR,
                       "notified": NOW - 5 * HOUR}]
        result = plan(stored, {})
        self.assertEqual(result["text"], "✅ Cleared after 5 h: Errors from 3 players.")
        self.assertEqual(result["writes"], [["DELETE FROM alerts WHERE key = ?", "errors"]])

    def test_a_long_message_fits_discord(self):
        current = {"workflow:%d" % i: "x" * 300 for i in range(20)}
        self.assertLessEqual(len(plan([ON], current)["text"]), 2000)


def names(waiting, stored, now=NOW):
    return call("planNames", waiting, stored, now)


LINK = "https://admin.wowgoldscout.com/admin#names"


@unittest.skipUnless(NODE, "node isn't installed")
class PlanNamesTests(unittest.TestCase):
    def test_nothing_waiting_says_nothing(self):
        self.assertEqual(names({"count": 0, "newest": None}, None), {"line": "", "writes": []})

    def test_a_new_name_is_sent_once(self):
        result = names({"count": 1, "newest": NOW - 600}, None)
        self.assertEqual(result["line"], "📝 1 leaderboard name is waiting for your approval: " + LINK)
        self.assertEqual(result["writes"][0][1:], ["_names", "", NOW, NOW])
        stored = {"key": "_names", "message": "", "since": NOW, "notified": NOW}
        self.assertEqual(names({"count": 1, "newest": NOW - 600}, stored, NOW + 3 * HOUR)["line"], "")

    def test_another_name_arriving_is_sent(self):
        stored = {"key": "_names", "message": "", "since": NOW - HOUR, "notified": NOW - HOUR}
        result = names({"count": 3, "newest": NOW - 60}, stored)
        self.assertEqual(result["line"], "📝 3 leaderboard names are waiting for your approval: " + LINK)
        self.assertEqual(result["writes"], [["UPDATE alerts SET notified = ? WHERE key = ?", NOW, "_names"]])

    def test_names_still_waiting_are_repeated_daily(self):
        stored = {"key": "_names", "message": "", "since": NOW - 30 * HOUR, "notified": NOW - 24 * HOUR}
        result = names({"count": 2, "newest": NOW - 30 * HOUR}, stored)
        self.assertEqual(result["line"], "📝 Still 2 leaderboard names waiting for your approval: " + LINK)

    def test_reviewing_them_all_forgets_quietly(self):
        stored = {"key": "_names", "message": "", "since": NOW - HOUR, "notified": NOW - HOUR}
        self.assertEqual(names({"count": 0, "newest": None}, stored),
                         {"line": "", "writes": [["DELETE FROM alerts WHERE key = ?", "_names"]]})


if __name__ == "__main__":
    unittest.main()


DAY_START = NOW - NOW % 86400   # midnight UTC of NOW's day
SIXTEEN = DAY_START + 16 * HOUR + 17 * 60   # the 16:17 UTC check


def daily(stored, open_problems, installs, release, now):
    return call("planDaily", stored, open_problems, installs, release, now)


@unittest.skipUnless(NODE, "node isn't installed")
class PlanDailyTests(unittest.TestCase):
    RELEASE = {"latest": "v0.12.15", "published": SIXTEEN - 2 * HOUR}

    def test_all_clear_once_a_day_from_16_utc(self):
        self.assertEqual(daily(None, 0, {"d1": 9, "new1": 2}, self.RELEASE, SIXTEEN - HOUR), {"line": "", "writes": []})
        result = daily(None, 0, {"d1": 9, "new1": 2}, self.RELEASE, SIXTEEN)
        self.assertEqual(result["line"], "☀️ Daily check: all clear. Last 24 h: 9 installs shared data, 2 new. "
                                         "Latest release v0.12.15, 2 h ago.")
        self.assertEqual(result["writes"][0][1:], ["_daily", "", SIXTEEN, SIXTEEN])
        sent = {"key": "_daily", "message": "", "since": SIXTEEN, "notified": SIXTEEN}
        self.assertEqual(daily(sent, 0, {}, None, SIXTEEN + HOUR)["line"], "")            # once that day
        later = daily(sent, 0, {}, None, SIXTEEN + 24 * HOUR)
        self.assertEqual(later["writes"], [["UPDATE alerts SET notified = ? WHERE key = ?", SIXTEEN + 24 * HOUR,
                                            "_daily"]])

    def test_a_missed_16_check_sends_it_at_the_next(self):
        sent = {"key": "_daily", "message": "", "since": SIXTEEN - 24 * HOUR, "notified": SIXTEEN - 24 * HOUR}
        self.assertTrue(daily(sent, 0, {}, None, SIXTEEN + HOUR)["line"])

    def test_open_problems_are_counted(self):
        line = daily(None, 2, {"d1": 1, "new1": 0}, None, SIXTEEN)["line"]
        self.assertEqual(line, "☀️ Daily check: 2 problems open (see above). Last 24 h: 1 install shared data, 0 new.")
