#!/usr/bin/env python3
"""Contributor leaderboard scores: each install's kills that count in the
community data.

Reads the validated submissions (data/submissions/, the same files
tools/merge_data.py merges) and scores each install by its kills, each mob's
kills capped the way merge_data.py caps them, so only kills that made it into
Data_Community.lua count. The data merge workflow runs it hourly on main and
sends the scores to the GoldScout server (PUT /v1/admin/leaderboard), which
ranks them and adds the names players chose in GoldScout Companion.

  python tools/leaderboard.py                  print the top 20
  python tools/leaderboard.py --push           send them (GOLDSCOUT_API_URL, GOLDSCOUT_API_ADMIN)
  python tools/leaderboard.py --input DIR      score another folder of exports
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_data  # noqa: E402

DEFAULT_API = "https://api.wowgoldscout.com"


def scores(submissions, cap=merge_data.MAX_PER_PLAYER):
    """{install ID: [kills, mobs]} for installs with at least one kill."""
    result = {}
    for submission in submissions:
        killed = [mob for mob in submission.mobs if mob.k > 0]
        kills = sum(min(mob.k, cap) for mob in killed)
        if kills > 0:
            result[submission.install_id] = [kills, len(killed)]
    return result


def push(table, api, admin, now=None):
    body = json.dumps({"generated": int(now or time.time()), "scores": table}).encode("utf-8")
    request = urllib.request.Request(api.rstrip("/") + "/v1/admin/leaderboard", data=body, method="PUT", headers={
        "Authorization": "Bearer " + admin, "Content-Type": "application/json", "User-Agent": "GoldScout-tools"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def main():
    parser = argparse.ArgumentParser(description="Score contributors for the GoldScout leaderboard.")
    parser.add_argument("--input", default=str(merge_data.DEFAULT_INPUT), help="folder of export .txt files")
    parser.add_argument("--push", action="store_true", help="send the scores to the GoldScout server")
    args = parser.parse_args()
    table = scores(merge_data.load(Path(args.input)))
    print("%d contributors with kills, %d kills counted." % (len(table), sum(k for k, _ in table.values())))
    if not args.push:
        ranked = sorted(table.values(), reverse=True)[:20]
        for place, (kills, mobs) in enumerate(ranked, 1):
            print("%3d. %8d kills, %4d mobs" % (place, kills, mobs))   # no install IDs in logs
        return
    admin = os.environ.get("GOLDSCOUT_API_ADMIN", "")
    if not admin:
        sys.exit("GOLDSCOUT_API_ADMIN isn't set.")
    reply = push(table, os.environ.get("GOLDSCOUT_API_URL") or DEFAULT_API, admin)
    print("Leaderboard: %s, %s scores." % (reply.get("status"), reply.get("scores")))


if __name__ == "__main__":
    main()
