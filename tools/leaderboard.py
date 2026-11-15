#!/usr/bin/env python3
"""Contributor leaderboard scores: each install's kills that count in the
community data.

Reads the validated submissions (data/submissions/, the same files
tools/merge_data.py merges) and scores each install by its kills, each mob's
kills capped the way merge_data.py caps them, so only kills that made it into
Data_Community.lua count. The data merge workflow runs it hourly on main and
sends the scores to the GoldScout server (PUT /v1/admin/leaderboard), which
ranks them and adds the names players chose in GoldScout Companion. With them
go each zone's top contributors (zone champions on the website's zone pages):
an install's kills of the mobs whose zone that is, the zone a mob is seen in
most across everyone's exports, as on the website.

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
ZONE_SENT = 10   # contributors per zone sent (the server's limit; it shows 3)


def scores(submissions, cap=merge_data.MAX_PER_PLAYER):
    """{install ID: [kills, mobs]} for installs with at least one kill."""
    result = {}
    for submission in submissions:
        killed = [mob for mob in submission.mobs if mob.k > 0]
        kills = sum(min(mob.k, cap) for mob in killed)
        if kills > 0:
            result[submission.install_id] = [kills, len(killed)]
    return result


def zone_of(merged):
    """npcID -> the uiMapID players see it in most (merge_data's maps), as the website files mobs under zones."""
    return {npc: max(entry["maps"].items(), key=lambda pair: (pair[1][2], pair[0]))[0]
            for npc, entry in merged.items() if entry["maps"]}


def zone_scores(submissions, cap=merge_data.MAX_PER_PLAYER, top=ZONE_SENT):
    """{uiMapID (str): [[install ID, kills], ...]}, each zone's best first, at most top of them."""
    zones = zone_of(merge_data.merge([submission.mobs for submission in submissions], cap))
    kills = {}
    for submission in submissions:
        for mob in submission.mobs:
            zone = zones.get(mob.npc)
            if zone and mob.k > 0:
                per_zone = kills.setdefault(zone, {})
                per_zone[submission.install_id] = per_zone.get(submission.install_id, 0) + min(mob.k, cap)
    return {str(zone): [[install, count] for install, count in
                        sorted(per_zone.items(), key=lambda pair: (-pair[1], pair[0]))[:top]]
            for zone, per_zone in sorted(kills.items())}


def push(table, api, admin, now=None, zones=None):
    body = {"generated": int(now or time.time()), "scores": table}
    if zones is not None:
        body["zones"] = zones
    body = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(api.rstrip("/") + "/v1/admin/leaderboard", data=body, method="PUT", headers={
        "Authorization": "Bearer " + admin, "Content-Type": "application/json", "User-Agent": "GoldScout-tools"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def main():
    parser = argparse.ArgumentParser(description="Score contributors for the GoldScout leaderboard.")
    parser.add_argument("--input", default=str(merge_data.DEFAULT_INPUT), help="folder of export .txt files")
    parser.add_argument("--push", action="store_true", help="send the scores to the GoldScout server")
    args = parser.parse_args()
    submissions = merge_data.load(Path(args.input))
    table = scores(submissions)
    zones = zone_scores(submissions)
    print("%d contributors with kills, %d kills counted, %d zones." % (
        len(table), sum(k for k, _ in table.values()), len(zones)))
    if not args.push:
        ranked = sorted(table.values(), reverse=True)[:20]
        for place, (kills, mobs) in enumerate(ranked, 1):
            print("%3d. %8d kills, %4d mobs" % (place, kills, mobs))   # no install IDs in logs
        return
    admin = os.environ.get("GOLDSCOUT_API_ADMIN", "")
    if not admin:
        sys.exit("GOLDSCOUT_API_ADMIN isn't set.")
    reply = push(table, os.environ.get("GOLDSCOUT_API_URL") or DEFAULT_API, admin, zones=zones)
    print("Leaderboard: %s, %s scores, %s zones." % (reply.get("status"), reply.get("scores"), reply.get("zones")))


if __name__ == "__main__":
    main()
