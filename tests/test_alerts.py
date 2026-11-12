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


if __name__ == "__main__":
    unittest.main()
