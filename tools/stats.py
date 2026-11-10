#!/usr/bin/env python3
"""How many players are sharing GoldScout data, in one report.

  python tools/stats.py             the report
  python tools/stats.py --days 30   daily new installs over 30 days (default 14)
  python tools/stats.py --players 0 leave out the per-player table (default: top 30)

The per-player table names each companion install by a short tag (the start of
a hash of its random install ID), with the companion version it last uploaded
with and how much its newest export holds. No names, realms or addresses exist
on the server to show.

Reads three places:
  - the live upload server's database (through wrangler, with your Cloudflare
    login; run once from server/: npx wrangler login),
  - "Share drop data" issues on GitHub (public API, no login),
  - this checkout's data/submissions and the latest release's community data
    (git fetch first for the newest).
Your own installs (from GoldScout's saved data on this PC) are marked "you"
and left out of the "other players" counts.

CurseForge and Wago download counts are on their project dashboards; downloads
aren't contributors, since the addon alone never shares anything.
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))
REPO_API = "https://api.github.com/repos/Alkhara/GoldScout-WoW"
MAINTAINER = "Alkhara"   # your GitHub login: your own form submissions
DAY = 86400


# -- sources ---------------------------------------------------------------------
def wrangler_sql(sql):
    """Rows from the live D1 database."""
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise RuntimeError("npx isn't installed (Node.js is needed for wrangler)")
    result = subprocess.run([npx, "wrangler", "d1", "execute", "goldscout", "--remote", "--json",
                             "--command", sql], cwd=ROOT / "server", capture_output=True, text=True,
                            encoding="utf-8", timeout=120)
    try:
        reply = json.loads(result.stdout)
    except ValueError:
        raise RuntimeError((result.stderr or result.stdout).strip().splitlines()[-1:] or "wrangler failed")
    if isinstance(reply, dict):   # an error object
        raise RuntimeError(reply.get("error", {}).get("text") or str(reply))
    return reply[0]["results"]


def github_issues():
    issues, page = [], 1
    while True:
        url = "%s/issues?state=all&labels=data-submission&per_page=100&page=%d" % (REPO_API, page)
        request = urllib.request.Request(url, headers={"User-Agent": "GoldScout-stats"})
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.loads(response.read())
        issues += [issue for issue in batch if "pull_request" not in issue]
        if len(batch) < 100:
            return issues
        page += 1


def my_installs():
    """Install IDs in GoldScout's saved data on this PC."""
    try:
        import savedvars
        local = ROOT / ".addons-path"
        forever = None
        if local.is_file():
            forever = savedvars.normalize_wow_folder(local.read_text(encoding="utf-8").strip())
        forever = forever or next(iter(savedvars.find_forever_folders()), None)
        return {a.install_id for a in savedvars.read_accounts(forever) if a.install_id} if forever else set()
    except Exception:   # no WoW here, or unreadable: just don't mark anything
        return set()


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""


def release_sources():
    """(tag, install IDs) in the latest release's community data."""
    tags = [t for t in git("tag", "--list", "v*").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    if not tags:
        return None, set()
    tag = max(tags, key=lambda t: tuple(int(p) for p in t[1:].split(".")))
    source = git("show", "%s:GoldScout/Data_Community.lua" % tag)
    block = re.search(r"ns\.COMMUNITY_SOURCES = \{(.*?)\n\}", source, re.S)
    return tag, set(re.findall(r'\["(\w+)"\]', block.group(1))) if block else set()


# -- summaries (pure, tested) ----------------------------------------------------
def summarize_installs(rows, now, mine, days):
    """rows: [{install_id, created_at, updated_at, uploads, version}] from the server."""
    others = [r for r in rows if r["install_id"] not in mine]

    def count(items, key, seconds):
        return sum(1 for r in items if r[key] >= now - seconds)

    today = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
    daily = []
    for back in range(days - 1, -1, -1):
        day = today - datetime.timedelta(days=back)
        daily.append((day.isoformat(), sum(
            1 for r in others
            if datetime.datetime.fromtimestamp(r["created_at"], datetime.timezone.utc).date() == day)))
    versions = {}
    for r in rows:
        versions[r["version"]] = versions.get(r["version"], 0) + 1
    return {
        "installs": len(rows), "mine": len(rows) - len(others), "others": len(others),
        "new_24h": count(others, "created_at", DAY), "new_7d": count(others, "created_at", 7 * DAY),
        "active_24h": count(others, "updated_at", DAY), "active_7d": count(others, "updated_at", 7 * DAY),
        "uploads": sum(r["uploads"] for r in rows), "uploads_others": sum(r["uploads"] for r in others),
        "versions": dict(sorted(versions.items())), "daily": daily,
    }


def player_tag(install_id):
    return hashlib.sha256(install_id.encode("utf-8")).hexdigest()[:5]


def export_totals(body):
    """(mobs, kills, pickpockets, item drops) in one export, or Nones if it doesn't parse."""
    import submission
    result = submission.parse(body or "")
    if not result.ok:
        return None, None, None, None
    drops = sum(d for mob in result.mobs for d, _ in list(mob.i.values()) + list(mob.pi.values()))
    return (len(result.mobs), sum(mob.k for mob in result.mobs), sum(mob.p for mob in result.mobs), drops)


def player_rows(rows, mine):
    """One row per install, most kills first: rows from the server with
    install_id, created_at, updated_at, uploads, body, client and os."""
    players = []
    for r in rows:
        mobs, kills, picks, drops = export_totals(r.get("body"))
        players.append({"tag": player_tag(r["install_id"]), "you": r["install_id"] in mine,
                        "client": r.get("client") or "unknown", "os": r.get("os") or "not sent",
                        "uploads": r["uploads"],
                        "created": r["created_at"], "updated": r["updated_at"],
                        "mobs": mobs, "kills": kills, "picks": picks, "drops": drops})
    return sorted(players, key=lambda p: (-(p["kills"] or 0), p["tag"]))


def ago(seconds):
    if seconds < 3600:
        return "%d min ago" % (seconds // 60)
    if seconds < 2 * DAY:
        return "%d h ago" % (seconds // 3600)
    return "%d days ago" % (seconds // DAY)


def player_table(players, now, limit):
    def num(value):
        return "?" if value is None else "{:,}".format(value)

    lines = ["  %-7s %-10s %-8s %7s  %-12s %-14s %5s %7s %6s %7s" % (
        "player", "companion", "system", "uploads", "first seen", "last upload", "mobs", "kills", "picks", "drops")]
    for p in players[:limit]:
        first = datetime.datetime.fromtimestamp(p["created"], datetime.timezone.utc).strftime("%b %d")
        lines.append("  %-7s %-10s %-8s %7d  %-12s %-14s %5s %7s %6s %7s" % (
            p["tag"] + ("*" if p["you"] else ""), p["client"][:10], p.get("os", "not sent")[:8], p["uploads"], first,
            ago(now - p["updated"]), num(p["mobs"]), num(p["kills"]), num(p["picks"]), num(p["drops"])))
    if len(players) > limit:
        lines.append("  ... and %d more (--players %d shows them)" % (len(players) - limit, len(players)))
    lines.append("  * yours. Totals are each install's newest export; companion version and system are from its latest upload.")
    return lines


def summarize_issues(issues, mine_logins=()):
    by_label = {}
    for issue in issues:
        labels = {label["name"] for label in issue.get("labels", [])}
        status = next((name for name in ("data-valid", "data-needs-review", "data-invalid") if name in labels),
                      "unchecked")
        by_label[status] = by_label.get(status, 0) + 1
    people = {issue["user"]["login"] for issue in issues if issue.get("user")}
    return {"total": len(issues), "open": sum(1 for i in issues if i.get("state") == "open"),
            "by_status": by_label, "people": len(people), "others": len(people - set(mine_logins))}


def summarize_submissions(folder, mine):
    files = sorted(Path(folder).glob("*.txt"))
    companion = {f.stem[2:] for f in files if f.stem.startswith("c-")}
    form = {f.stem.split("-", 1)[1] for f in files if not f.stem.startswith("c-") and "-" in f.stem}
    installs = companion | form
    return {"files": len(files), "installs": len(installs), "others": len(installs - mine),
            "companion": len(companion), "form": len(form)}


# -- report ----------------------------------------------------------------------
def bar(n, peak, width=24):
    return "#" * (round(width * n / peak) if peak else 0)


def main():
    parser = argparse.ArgumentParser(description="How many players are sharing GoldScout data.")
    parser.add_argument("--days", type=int, default=14, help="days of daily new installs to show")
    parser.add_argument("--players", type=int, default=30, help="rows in the per-player table (0: none)")
    args = parser.parse_args()
    now = int(time.time())
    mine = my_installs()
    print("GoldScout data sharing, %s UTC" % datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
          .strftime("%Y-%m-%d %H:%M"))
    print("Your installs on this PC: %s" % (", ".join(sorted(mine)) or "none found"))

    print("\nUpload server (companion), live")
    try:
        columns = "install_id, created_at, installs.updated_at AS updated_at, uploads, body, " \
                  "substr(body, 18, 1) AS version"
        try:
            rows = wrangler_sql("SELECT %s, client, os FROM installs LEFT JOIN install_clients USING (install_id) "
                                "LEFT JOIN install_os USING (install_id)" % columns)
        except RuntimeError:   # a server from before companion systems were recorded
            try:
                rows = wrangler_sql("SELECT %s, client FROM installs LEFT JOIN install_clients USING (install_id)"
                                    % columns)
            except RuntimeError:   # or before companion versions were
                rows = wrangler_sql("SELECT %s FROM installs" % columns)
        s = summarize_installs(rows, now, mine, args.days)
        print("  installs           %d  (%d yours, %d other players)" % (s["installs"], s["mine"], s["others"]))
        print("  new players        %d in 24 h, %d in 7 days" % (s["new_24h"], s["new_7d"]))
        print("  sharing recently   %d in 24 h, %d in 7 days  (other players who uploaded)"
              % (s["active_24h"], s["active_7d"]))
        print("  uploads            %d total, %d from other players" % (s["uploads"], s["uploads_others"]))
        print("  export versions    %s" % ", ".join("v%s: %d" % item for item in s["versions"].items()))
        peak = max([n for _, n in s["daily"]] + [0])
        print("  new players per day (UTC):")
        for day, n in s["daily"]:
            print("    %s %3d %s" % (day, n, bar(n, peak)))
        if args.players > 0:
            players = player_rows(rows, mine)
            clients, systems = {}, {}
            for p in players:
                clients[p["client"]] = clients.get(p["client"], 0) + 1
                systems[p["os"]] = systems.get(p["os"], 0) + 1
            print("  companion versions %s" % ", ".join("%s: %d" % item for item in sorted(clients.items())))
            print("  companion systems  %s  (\"not sent\": companions before 0.8.0, Windows only)"
                  % ", ".join("%s: %d" % item for item in sorted(systems.items())))
            print("\nPlayers (companion installs)")
            print("\n".join(player_table(players, now, args.players)))
    except Exception as error:
        print("  couldn't read the server: %s" % error)
        print("  (log in once from server/: npx wrangler login)")

    print("\nShare form (GitHub issues)")
    try:
        f = summarize_issues(github_issues(), {MAINTAINER})
        statuses = ", ".join("%s %d" % item for item in sorted(f["by_status"].items())) or "none"
        print("  submissions        %d (%d open) from %d people (%d other players)"
              % (f["total"], f["open"], f["people"], f["others"]))
        print("  by check           %s" % statuses)
    except Exception as error:
        print("  couldn't read GitHub: %s" % error)

    print("\nCommunity data")
    merged = summarize_submissions(ROOT / "data" / "submissions", mine)
    print("  merged on main     %d installs (%d other players): %d by companion, %d by form"
          % (merged["installs"], merged["others"], merged["companion"], merged["form"]))
    tag, sources = release_sources()
    if tag:
        print("  in release %-7s %d installs (%d other players)" % (tag, len(sources), len(sources - mine)))
    print("\nDownloads: CurseForge and Wago dashboards (downloads aren't contributors).")


if __name__ == "__main__":
    main()
