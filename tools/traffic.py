#!/usr/bin/env python3
"""Prints how much traffic wowgoldscout.com gets: visits and page views per day, top pages, where visitors
come from, countries and devices, from Cloudflare Web Analytics.

  python tools/traffic.py             the last 7 days
  python tools/traffic.py --days 30   up to 30 days

With CLOUDFLARE_ANALYTICS_TOKEN set (a Cloudflare API token with Account Analytics: Read, and optionally
CLOUDFLARE_ACCOUNT_ID), it asks Cloudflare directly. Without it, it reads the copy the hourly data merge
saved for the admin dashboard (tools/admin_stats.py), through wrangler's remote D1 access; that copy covers
30 days and is up to an hour old.

Cloudflare counts without cookies and keeps no IP addresses; these are totals only. A visit starts when
someone arrives from another site or types the address, and each page they open is a page view.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import admin_stats  # noqa: E402

MAX_DAYS = 30
LIST = 10


def live(days, environ=os.environ):
    token = environ.get("CLOUDFLARE_ANALYTICS_TOKEN")
    account = environ.get("CLOUDFLARE_ACCOUNT_ID") or admin_stats.token_account(token)
    if not account:
        raise SystemExit("Set CLOUDFLARE_ACCOUNT_ID: the token can see more than one Cloudflare account, or none.")
    return admin_stats.site_traffic(token, account, int(time.time()), days)


def saved(run=subprocess.run):
    """The traffic in the admin dashboard's statistics snapshot, read from the live database."""
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx isn't installed, and CLOUDFLARE_ANALYTICS_TOKEN isn't set.")
    command = [npx, "wrangler", "d1", "execute", "goldscout", "--remote", "--json", "--command",
               "SELECT json_extract(body, '$.traffic') AS traffic FROM admin_stats WHERE name = 'dashboard'"]
    done = run(command, cwd=ROOT / "server", capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise SystemExit("wrangler couldn't read the dashboard statistics:\n" + (done.stderr or done.stdout)[-800:])
    rows = json.loads(done.stdout)[0]["results"]
    traffic = json.loads(rows[0]["traffic"]) if rows and rows[0]["traffic"] else None
    if not traffic:
        raise SystemExit("The dashboard statistics have no website traffic yet; the next hourly data merge adds it.")
    if not traffic.get("days"):
        raise SystemExit("The last statistics run couldn't get website traffic: %s"
                         % (traffic.get("error") or ", ".join(traffic.get("missing") or []) or "no reason given"))
    return traffic


def number(value):
    return "{:,}".format(value)


def report(traffic, days):
    """The traffic as text, for the last days of it (the lists cover everything fetched)."""
    shown = traffic["days"][-days:]
    visits = sum(d["visits"] for d in shown)
    views = sum(d["views"] for d in shown)
    fetched = len(traffic["days"])
    lines = ["%s: %s visits, %s page views in the last %d days (UTC, through %s)"
             % (traffic["host"], number(visits), number(views), len(shown),
                time.strftime("%Y-%m-%d %H:%M", time.gmtime(traffic["through"]))), ""]
    lines.append("Day          Visits   Page views")
    for day in shown:
        lines.append("%s %8s %12s" % (day["date"], number(day["visits"]), number(day["views"])))

    def block(title, rows, label, columns):
        lines.extend(["", title])
        if not rows:
            lines.append("  (none yet)")
        for row in rows[:LIST]:
            lines.append("  %-44s %s" % (label(row)[:44], "  ".join("%8s" % number(row[c]) for c in columns)))

    span = "" if fetched == len(shown) else " (last %d days)" % fetched
    block("Top pages%s           views    visits" % span, traffic.get("pages") or [], lambda r: r["path"],
          ["views", "visits"])
    block("Where visits come from%s        visits" % span, traffic.get("referrers") or [],
          lambda r: r["host"] or "(typed in, bookmark, or hidden)", ["visits"])
    block("Countries%s                     visits" % span, traffic.get("countries") or [], lambda r: r["name"],
          ["visits"])
    block("Devices%s                       visits" % span, traffic.get("devices") or [], lambda r: r["name"],
          ["visits"])
    others = [h for h in traffic.get("hosts") or [] if h["host"] != traffic["host"]]
    if others:
        lines.extend(["", "Also counted on: " + ", ".join("%s (%s page views)" % (h["host"], number(h["views"]))
                                                     for h in others)])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=7, help="days to show, 1 to %d (default 7)" % MAX_DAYS)
    args = parser.parse_args()
    days = max(1, min(MAX_DAYS, args.days))
    if os.environ.get("CLOUDFLARE_ANALYTICS_TOKEN"):
        traffic = live(days)
    else:
        traffic = saved()
        print("From the admin dashboard's statistics, %d min old.\n" % ((time.time() - traffic["through"]) // 60))
    print(report(traffic, days))


if __name__ == "__main__":
    main()
