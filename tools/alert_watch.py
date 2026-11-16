#!/usr/bin/env python3
"""Watches the watcher: warns Discord from GitHub when the server's hourly
alert checks (server/src/alerts.js) have stopped.

The server sends every other alert, so if its cron, its database or its
Discord webhook breaks, the alerts channel just goes quiet. The hourly data
merge workflow runs this after its other steps. It reads when the server
last finished an alert check (GET /admin/api/alerts, with the admin token)
and posts to the same Discord webhook, stored as a GitHub secret too, when:

  - the last check finished 3 hours ago or more: once when it starts (under
    4 hours), then daily at 16:00 UTC
  - the webhook isn't set on the server: daily at 16:00 UTC
  - the server can't be reached or refuses the token: when the previous merge
    run had succeeded (so once when it starts), then daily at 16:00 UTC

  python tools/alert_watch.py            check, and post if needed
  python tools/alert_watch.py --print    check and print, post nothing

Needs ALERT_WEBHOOK_URL and GOLDSCOUT_API_ADMIN; without either it says so
and does nothing. GOLDSCOUT_API_URL picks the server. GITHUB_TOKEN reads the
previous merge run's result.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HOUR = 3600
STALE = 3 * HOUR       # checks run hourly; three missed in a row is a break
DAILY_HOUR = 16        # UTC, the hour the server's own daily summary goes out
REPO = os.environ.get("GITHUB_REPOSITORY", "Alkhara/GoldScout-WoW")
USER_AGENT = "GoldScout-alert-watch/1.0 (+https://github.com/Alkhara/GoldScout-WoW)"


def fetch_json(url, headers=None, data=None, method=None):
    request = urllib.request.Request(url, data=data, method=method,
                                     headers=dict(headers or {}, **{"User-Agent": USER_AGENT}))
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"{}")


def read_status(api, admin, tries=3):
    """The server's {"checked", "webhook"}, or an error message if it can't be read."""
    error = None
    for attempt in range(tries):
        try:
            return fetch_json(api + "/admin/api/alerts", {"Authorization": "Bearer " + admin}), None
        except urllib.error.HTTPError as failure:
            error = "HTTP %d" % failure.code
            if failure.code in (401, 403, 404):
                break   # retrying won't help
        except Exception as failure:   # network trouble: try again
            error = str(failure) or failure.__class__.__name__
        if attempt + 1 < tries:
            time.sleep(10)
    return None, error


def previous_run_succeeded():
    """Whether the data merge's last completed run (before this one) succeeded; True if it can't tell, so an
    unreachable server is reported rather than missed."""
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        runs = fetch_json("https://api.github.com/repos/%s/actions/workflows/data-merge.yml/runs"
                          "?status=completed&per_page=5" % REPO, headers).get("workflow_runs", [])
    except Exception:
        return True
    this = str(os.environ.get("GITHUB_RUN_ID", ""))
    earlier = [r for r in runs if str(r.get("id")) != this]
    return not earlier or earlier[0].get("conclusion") == "success"


def decide(status, error, now, previous_ok):
    """What to post to Discord, or None. Pure, so the tests can drive it."""
    daily = (now % 86400) // HOUR == DAILY_HOUR
    if error:
        if previous_ok or daily:
            return ("⚠️ From GitHub: the hourly data merge couldn't read the GoldScout server's alert status (%s), "
                    "so the server may be down or its admin token changed, and its Discord alerts may be "
                    "silent. Check https://api.wowgoldscout.com/health and the goldscout-api Worker." % error)
        return None
    if not status.get("webhook"):
        new = False   # a setting, not an outage, and with no record of when it changed: daily only
        problem = "its ALERT_WEBHOOK_URL secret isn't set, so it sends no alerts"
    else:
        checked = status.get("checked")
        if checked and now - checked < STALE:
            return None
        age = now - checked if checked else None
        new = age is None or age < STALE + HOUR
        problem = ("its hourly alert check hasn't finished for %d h" % (age // HOUR) if age is not None
                   else "it has never finished an alert check")
    if not (new or daily):
        return None
    return ("⚠️ From GitHub: the GoldScout server is up, but %s, so Discord alerts may be silent. Check the "
            "goldscout-api Worker's logs and cron triggers in Cloudflare." % problem)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--print", action="store_true", help="print what it would post, post nothing")
    args = parser.parse_args()
    webhook = os.environ.get("ALERT_WEBHOOK_URL", "")
    admin = os.environ.get("GOLDSCOUT_API_ADMIN", "")
    api = os.environ.get("GOLDSCOUT_API_URL", "https://api.wowgoldscout.com").rstrip("/")
    if not admin or (not webhook and not args.print):
        print("ALERT_WEBHOOK_URL or GOLDSCOUT_API_ADMIN isn't set, so the alerts aren't watched from GitHub.")
        return
    status, error = read_status(api, admin)
    now = int(time.time())
    message = decide(status, error, now, previous_run_succeeded() if error else True)
    if status and not error:
        checked = status.get("checked")
        print("Server alert check last finished %s; webhook %s." % (
            "%d min ago" % ((now - checked) // 60) if checked else "never", "set" if status.get("webhook") else "NOT set"))
    else:
        print("Couldn't read the server's alert status: %s" % error)
    if not message:
        return
    print(message)
    if args.print:
        return
    fetch_json(webhook, {"Content-Type": "application/json"}, method="POST", data=json.dumps(
        {"username": "GoldScout (GitHub)", "content": message, "allowed_mentions": {"parse": []}}).encode())
    print("Posted to Discord.")


if __name__ == "__main__":
    sys.exit(main())
