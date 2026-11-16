"""tools/alert_watch.py: when GitHub warns Discord that the server's own alert checks have stopped."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import alert_watch  # noqa: E402

HOUR = 3600
DAY_START = 1_800_000_000 - 1_800_000_000 % 86400
NINE = DAY_START + 9 * HOUR + 17 * 60       # an ordinary hourly run
SIXTEEN = DAY_START + 16 * HOUR + 17 * 60   # the daily reminder's run


def decide(status=None, error=None, now=NINE, previous_ok=True):
    return alert_watch.decide(status, error, now, previous_ok)


class DecideTests(unittest.TestCase):
    def test_recent_checks_say_nothing(self):
        self.assertIsNone(decide({"checked": NINE - 40 * 60, "webhook": True}))
        self.assertIsNone(decide({"checked": NINE - 2 * HOUR, "webhook": True}, now=SIXTEEN - 7 * HOUR))

    def test_stopped_checks_warn_once_then_daily(self):
        message = decide({"checked": NINE - 3 * HOUR - 600, "webhook": True})
        self.assertIn("hasn't finished for 3 h", message)
        self.assertIn("From GitHub", message)
        self.assertIsNone(decide({"checked": NINE - 5 * HOUR, "webhook": True}))
        self.assertIn("hasn't finished for 12 h", decide({"checked": SIXTEEN - 12 * HOUR, "webhook": True}, now=SIXTEEN))
        self.assertIn("never finished", decide({"checked": None, "webhook": True}))

    def test_no_webhook_on_the_server_is_daily_only(self):
        self.assertIsNone(decide({"checked": None, "webhook": False}))
        self.assertIn("ALERT_WEBHOOK_URL secret isn't set", decide({"checked": None, "webhook": False}, now=SIXTEEN))

    def test_an_unreachable_server_warns_when_it_starts_then_daily(self):
        self.assertIn("couldn't read the GoldScout server's alert status (HTTP 502)", decide(error="HTTP 502"))
        self.assertIsNone(decide(error="HTTP 502", previous_ok=False))
        self.assertIsNotNone(decide(error="timed out", previous_ok=False, now=SIXTEEN))


if __name__ == "__main__":
    unittest.main()
