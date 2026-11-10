#!/usr/bin/env python3
"""Builds the admin dashboard's statistics and sends them to the GoldScout server.

The hourly data merge workflow runs this after it has collected new data, so
the heavy counting (every export, the whole community data set, GitHub's API)
happens on GitHub, and the server only stores and serves the result
(PUT /v1/admin/stats; the dashboard at /admin reads it).

  python tools/admin_stats.py            build and send
  python tools/admin_stats.py --print    build and print, send nothing

Needs GOLDSCOUT_API_ADMIN (the server's ADMIN_TOKEN). GITHUB_TOKEN is optional
(without it, GitHub's public API is used, with its lower rate limit).
GOLDSCOUT_MY_INSTALLS (comma-separated install IDs) marks the maintainer's own
installs. Players appear only as short hashed tags, never install IDs.
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))

import data_pages  # noqa: E402
import merge_data  # noqa: E402
import stats  # noqa: E402

DAY = 86400
REPO = os.environ.get("GITHUB_REPOSITORY", "Alkhara/GoldScout-WoW")
DEFAULT_API = "https://goldscout-api.cawley22.workers.dev"
USER_AGENT = "GoldScout-admin-stats/1.0 (+https://github.com/Alkhara/GoldScout-WoW)"
WORKFLOWS = [("ah-prices.yml", "Auction prices", 96), ("data-merge.yml", "Merge community data", 24),
             ("tests.yml", "Tests", None), ("server-deploy.yml", "Deploy server", None),
             ("release.yml", "Release", None), ("data-release.yml", "Data release", None)]
GOOD = 15          # attempts for "good" confidence (site/data_pages.py CONFIDENCE)
LISTS = 25         # rows in each list


# -- fetching ------------------------------------------------------------------
def get_json(url, headers=None, data=None, method=None):
    request = urllib.request.Request(url, data=data, method=method,
                                     headers=dict(headers or {}, **{"User-Agent": USER_AGENT}))
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read() or b"{}")


def github(path):
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    return get_json("https://api.github.com/repos/%s%s" % (REPO, path), headers)


# -- pieces (pure, tested) -------------------------------------------------------
def day_of(unix):
    return datetime.datetime.fromtimestamp(unix, datetime.timezone.utc).date()


def growth(installs, now, days=30):
    """Daily new players, activity windows, quiet installs and weekly cohorts."""
    today = day_of(now)
    daily = []
    for back in range(days - 1, -1, -1):
        day = today - datetime.timedelta(days=back)
        daily.append([day.isoformat(), sum(1 for i in installs if day_of(i["created_at"]) == day)])
    cohorts = defaultdict(lambda: {"joined": 0, "after7": 0, "after14": 0, "after28": 0, "eligible7": 0,
                                   "eligible14": 0, "eligible28": 0})
    for i in installs:
        start = day_of(i["created_at"])
        week = (start - datetime.timedelta(days=start.weekday())).isoformat()
        cohort = cohorts[week]
        cohort["joined"] += 1
        kept = i["updated_at"] - i["created_at"]
        for span in (7, 14, 28):
            if now - i["created_at"] >= span * DAY:   # only installs old enough to tell
                cohort["eligible%d" % span] += 1
                cohort["after%d" % span] += kept >= span * DAY
    return {
        "daily_new": daily,
        "active": {"d1": sum(1 for i in installs if now - i["updated_at"] <= DAY),
                   "d7": sum(1 for i in installs if now - i["updated_at"] <= 7 * DAY),
                   "d30": sum(1 for i in installs if now - i["updated_at"] <= 30 * DAY)},
        "quiet14": sum(1 for i in installs if now - i["updated_at"] > 14 * DAY),
        "uploads": sum(i["uploads"] for i in installs),
        "cohorts": [dict(week=week, **values) for week, values in sorted(cohorts.items())][-12:],
    }


def coverage(results, merged, prices=None):
    """Where the community data is thin: by level bracket and zone, mobs close
    to good confidence, and valuable reagents with few good sources."""
    data = data_pages.Dataset(results, merged)
    brackets = {label: {"label": "%d-%d" % label, "mobs": 0, "good": 0, "kills": 0}
                for label in data_pages.BRACKETS}
    zones = {}
    for npc, entry in merged.items():
        attempts = entry["k"] + entry["p"]
        mid = (entry["lmin"] + entry["lmax"]) / 2 if entry["lmin"] else 0
        for low, high in data_pages.BRACKETS:
            if low <= mid <= high or (mid > high and (low, high) == data_pages.BRACKETS[-1]):
                row = brackets[(low, high)]
                row["mobs"] += 1
                row["good"] += attempts >= GOOD
                row["kills"] += entry["k"]
                break
        maps = entry["maps"]
        if maps:
            map_id = max(maps.items(), key=lambda pair: (pair[1][2], pair[0]))[0]
            name = data.map_names.get(map_id, "Map %d" % map_id)
            zone = zones.setdefault(name, {"name": name, "mobs": 0, "good": 0, "kills": 0})
            zone["mobs"] += 1
            zone["good"] += attempts >= GOOD
            zone["kills"] += entry["k"]

    def mob_row(npc, entry):
        names = entry["names"]
        levels = "" if not entry["lmin"] else (str(entry["lmin"]) if entry["lmin"] == entry["lmax"]
                                               else "%d-%d" % (entry["lmin"], entry["lmax"]))
        maps = entry["maps"]
        zone = ""
        if maps:
            map_id = max(maps.items(), key=lambda pair: (pair[1][2], pair[0]))[0]
            zone = data.map_names.get(map_id, "")
        return {"npc": npc, "name": max(names.items(), key=lambda p: (p[1], p[0]))[0] if names else "Mob %d" % npc,
                "levels": levels, "zone": zone, "kills": entry["k"], "picks": entry["p"],
                "attempts": entry["k"] + entry["p"]}

    rows = [mob_row(npc, entry) for npc, entry in merged.items()]
    close = sorted((r for r in rows if 0 < r["attempts"] < GOOD), key=lambda r: (-r["attempts"], r["name"]))
    top = sorted(rows, key=lambda r: (-r["attempts"], r["name"]))

    reagents = []
    for item, sources in data.reagent_sources.items():
        good = [s for s in sources if data.mobs[s[0]]["k"] >= GOOD]
        price = (prices or {}).get(str(item))
        reagents.append({"item": item, "name": data.item_name(item), "sources": len(sources),
                         "good_sources": len(good), "best_rate": round(sources[0][1], 4) if sources else 0,
                         "price": price[0] if price else None, "listed": price[1] if price else None})
    reagents.sort(key=lambda r: (r["good_sources"] >= 2, -(r["price"] or 0), r["name"]))
    return {
        "mobs_seen": len(merged), "mobs_shown": len(data.mobs),
        "mobs_good": sum(1 for e in merged.values() if e["k"] + e["p"] >= GOOD),
        "kills": sum(e["k"] for e in merged.values()), "picks": sum(e["p"] for e in merged.values()),
        "brackets": list(brackets.values()),
        "zones": sorted(zones.values(), key=lambda z: (-z["kills"], z["name"])),
        "close_to_good": close[:LISTS], "top_mobs": top[:LISTS], "thin_reagents": reagents[:LISTS],
    }


def workflow_health(runs_by_workflow, now):
    """Latest run and the last 24 hours, per workflow."""
    out = []
    for file, name, expected in WORKFLOWS:
        runs = runs_by_workflow.get(file, [])
        recent = [r for r in runs if now - parse_time(r["created_at"]) <= DAY]
        latest = runs[0] if runs else None
        out.append({
            "file": file, "name": name, "expected_24h": expected,
            "runs_24h": len(recent),
            "success_24h": sum(1 for r in recent if r.get("conclusion") == "success"),
            "by_event_24h": dict(sorted(count_by(recent, "event").items())),
            "latest": None if not latest else {
                "status": latest.get("status"), "conclusion": latest.get("conclusion"),
                "event": latest.get("event"), "created": parse_time(latest["created_at"]),
                "url": latest.get("html_url")},
        })
    return out


def count_by(rows, key):
    counts = defaultdict(int)
    for row in rows:
        counts[row.get(key) or "?"] += 1
    return counts


def parse_time(text):
    return int(datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())


def downloads(releases):
    out = []
    for release in releases[:10]:
        assets = {a["name"]: a.get("download_count", 0) for a in release.get("assets", [])}
        out.append({"tag": release.get("tag_name"), "published": parse_time(release["published_at"])
                    if release.get("published_at") else None,
                    "exe": sum(n for name, n in assets.items() if name.lower().endswith(".exe")),
                    "zip": sum(n for name, n in assets.items() if name.lower().endswith(".zip"))})
    return out


# -- building ------------------------------------------------------------------
def build(now, api, admin, mine):
    snapshot = {"generated": now, "problems": []}

    def attempt(name, fn):
        try:
            return fn()
        except Exception as error:   # one source failing shouldn't sink the rest
            snapshot["problems"].append("%s: %s" % (name, error))
            return None

    uploads = attempt("upload server", lambda: get_json(
        api + "/v1/uploads", {"Authorization": "Bearer " + admin})["uploads"]) or []
    installs = [u for u in uploads if "created_at" in u]
    rows = [dict(u, version=(u.get("body") or "")[17:18]) for u in installs]
    players = stats.player_rows(rows, mine)
    snapshot["players"] = players
    snapshot["growth"] = growth(installs, now)
    snapshot["mine"] = sum(1 for i in installs if i["install_id"] in mine)
    snapshot["versions"] = dict(sorted(count_by([{"c": p["client"]} for p in players], "c").items()))
    snapshot["export_versions"] = dict(sorted(count_by(rows, "version").items()))

    listing = attempt("prices", lambda: get_json(api + "/v1/prices")) or {}
    mapped = sorted((h for h in listing.get("houses", []) if h.get("ruleset") and h.get("items")),
                    key=lambda h: -h["items"])
    prices = None
    if mapped:
        house = mapped[0]
        snapshot["price_house"] = {"house": house["house"], "ruleset": house.get("rulesetName"),
                                   "faction": house["faction"], "snapshot": house["snapshot"]}
        prices = attempt("house prices", lambda: get_json(
            "%s/v1/prices/%s/%d" % (api, house["region"], house["house"])).get("prices"))
    results = merge_data.load(ROOT / "data" / "submissions")
    merged = merge_data.merge([r.mobs for r in results], data_pages.PLAYER_CAP)
    snapshot["community"] = dict(coverage(results, merged, prices), contributors=len(results))

    releases = attempt("releases", lambda: github("/releases?per_page=10")) or []
    snapshot["downloads"] = downloads(releases)
    issues = attempt("share form", lambda: stats.github_issues())
    if issues is not None:
        snapshot["form"] = stats.summarize_issues(issues, {stats.MAINTAINER})
    runs = {}
    for file, _, _ in WORKFLOWS:
        found = attempt("workflow " + file, lambda f=file: github(
            "/actions/workflows/%s/runs?per_page=100" % f).get("workflow_runs", []))
        runs[file] = found or []
    snapshot["workflows"] = workflow_health(runs, now)
    pulls = attempt("data pull request", lambda: github(
        "/pulls?state=open&head=%s:data/community-update" % REPO.split("/")[0])) or []
    snapshot["data_pr"] = None if not pulls else {
        "number": pulls[0]["number"], "url": pulls[0]["html_url"], "updated": parse_time(pulls[0]["updated_at"])}
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print", action="store_true", help="print the statistics instead of sending them")
    args = parser.parse_args()
    api = (os.environ.get("GOLDSCOUT_API_URL") or DEFAULT_API).rstrip("/")
    admin = os.environ.get("GOLDSCOUT_API_ADMIN", "")
    if not admin:
        raise SystemExit("GOLDSCOUT_API_ADMIN isn't set.")
    mine = {i.strip() for i in os.environ.get("GOLDSCOUT_MY_INSTALLS", "").split(",") if i.strip()}
    snapshot = build(int(time.time()), api, admin, mine)
    body = json.dumps(snapshot, separators=(",", ":"), sort_keys=True)
    if args.print:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return
    reply = get_json(api + "/v1/admin/stats", {"Authorization": "Bearer " + admin,
                                               "Content-Type": "application/json"},
                     body.encode("utf-8"), "PUT")
    print("Dashboard statistics: %s (%d KB, %d problem(s))" % (reply.get("status"), len(body) // 1024,
                                                              len(snapshot["problems"])))
    for problem in snapshot["problems"]:
        print("  " + problem)


if __name__ == "__main__":
    main()
