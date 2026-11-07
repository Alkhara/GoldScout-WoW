#!/usr/bin/env python3
"""Combine players' /gscout export strings into GoldScout/Data_Community.lua.

Accepted submissions live in data/submissions/, one file per contributor
(the GitHub workflow in .github/workflows/data-merge.yml keeps them there).
To merge by hand:

  python tools/merge_data.py                    merge data/submissions/
  python tools/merge_data.py --input DIR        use another folder of .txt exports
  python tools/merge_data.py --min-attempts 10

Every file is checked by tools/submission.py; files with errors are skipped.
Identical files are counted once. Each export holds everything that player
has ever looted, so keep only one file per player, or their loot counts twice.
No single player can outweigh the rest: their kills (and pickpockets) of any
one mob count up to --max-per-player, with their drops scaled to match.
"""
import argparse
import hashlib
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import submission  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "submissions"
TARGET = ROOT / "GoldScout" / "Data_Community.lua"


def load(folder):
    """Reads and validates every .txt export in a folder. Returns a list of Results."""
    seen, submissions = set(), []
    for path in sorted(Path(folder).glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        if digest in seen:
            print("skip duplicate: %s" % path.name)
            continue
        result = submission.parse(text)
        if not result.ok:
            print("skip %s: %s" % (path.name, result.errors[0]))
            continue
        seen.add(digest)
        submissions.append(result)
    return submissions


def half_up(value):
    """Rounds like Community.lua does, so clients can undo a player's capped
    contribution exactly."""
    return int(math.floor(value + 0.5))


def _scaled(items, factor):
    if factor >= 1:
        return items
    scaled = {}
    for item, (d, q) in items.items():
        d2 = half_up(d * factor)
        if d2 > 0:
            scaled[item] = (d2, max(d2, half_up(q * factor)))
    return scaled


def sources_of(submissions):
    """Install ID -> the snapshot number included for it."""
    sources = {}
    for result in submissions:
        sources[result.install_id] = max(result.seq, sources.get(result.install_id, 0))
    return sources


def merge(submissions, max_per_player):
    merged = {}
    for mobs in submissions:
        for mob in mobs:
            kill_factor = min(1.0, max_per_player / mob.k) if mob.k else 1.0
            pick_factor = min(1.0, max_per_player / mob.p) if mob.p else 1.0
            entry = merged.setdefault(mob.npc, {
                "k": 0, "p": 0, "lmin": 0, "lmax": 0, "names": defaultdict(int),
                "maps": defaultdict(lambda: [0.0, 0.0, 0]),
                "i": defaultdict(lambda: [0, 0]), "pi": defaultdict(lambda: [0, 0]),
            })
            entry["k"] += min(mob.k, max_per_player)
            entry["p"] += min(mob.p, max_per_player)
            if mob.lmin:
                entry["lmin"] = min(entry["lmin"] or mob.lmin, mob.lmin)
            entry["lmax"] = max(entry["lmax"], mob.lmax)
            if mob.n:
                entry["names"][mob.n] += 1
            if mob.m and mob.c:
                count = min(mob.c, max_per_player)
                spot = entry["maps"][mob.m]
                spot[0] += mob.x * count
                spot[1] += mob.y * count
                spot[2] += count
            for key, factor in (("i", kill_factor), ("pi", pick_factor)):
                for item, (d, q) in _scaled(getattr(mob, key), factor).items():
                    entry[key][item][0] += d
                    entry[key][item][1] += q
    return merged


def lua_items(items):
    parts = ["[%d] = { d = %d, q = %d }" % (item_id, d, q) for item_id, (d, q) in sorted(items.items())]
    return "{ " + ", ".join(parts) + " }" if parts else "{}"


def lua_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_lua(merged, min_attempts, path, contributors, sources=None, cap=1000):
    out = [
        "-- GoldScout community data: drop rates and spawn spots collected by players",
        "-- with /gscout export and combined by tools/merge_data.py. Generated file;",
        "-- don't edit by hand. Built from %d submission(s)." % contributors,
        "-- Covered by the GoldScout Data License (DATA_LICENSE.md), not the MIT",
        "-- License: no use outside GoldScout without permission.",
        "local _, ns = ...",
        "",
        "ns.COMMUNITY = {",
    ]
    kept = 0
    for npc in sorted(merged):
        entry = merged[npc]
        if entry["k"] + entry["p"] < min_attempts:
            continue
        kept += 1
        fields = ["k = %d" % entry["k"], "p = %d" % entry["p"]]
        if entry["lmin"]:
            fields += ["lmin = %d" % entry["lmin"], "lmax = %d" % entry["lmax"]]
        if entry["names"]:
            name = max(entry["names"].items(), key=lambda pair: (pair[1], pair[0]))[0]
            fields.append("n = %s" % lua_string(name))
        if entry["maps"]:
            map_id, (sx, sy, count) = max(entry["maps"].items(), key=lambda pair: (pair[1][2], pair[0]))
            fields += ["m = %d" % map_id, "x = %.4f" % (sx / count), "y = %.4f" % (sy / count), "c = %d" % count]
        fields += ["i = %s" % lua_items(entry["i"]), "pi = %s" % lua_items(entry["pi"])]
        out.append("  [%d] = { %s }," % (npc, ", ".join(fields)))
    out.append("}")
    out.append("")
    out.append("-- The export snapshot of each install included above, so a player's own")
    out.append("-- client can take its shared loot back out (see Community.lua).")
    out.append("ns.COMMUNITY_SOURCES = {")
    for install_id, seq in sorted((sources or {}).items()):
        out.append('  ["%s"] = %d,' % (install_id, seq))
    out.append("}")
    out.append("ns.COMMUNITY_CAP = %d" % cap)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return kept


def main():
    parser = argparse.ArgumentParser(description="Merge GoldScout exports into Data_Community.lua.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="folder of export .txt files")
    parser.add_argument("--min-attempts", type=int, default=5, help="minimum kills plus picks per mob")
    parser.add_argument("--max-per-player", type=int, default=1000,
                        help="most kills (and picks) of one mob counted from any one player")
    args = parser.parse_args()

    folder = Path(args.input)
    if not folder.is_dir():
        sys.exit("No submissions folder at %s" % folder)
    submissions = load(folder)
    if not submissions:
        print("No valid submissions in %s; writing an empty data file." % folder)
    merged = merge([result.mobs for result in submissions], args.max_per_player)
    kept = write_lua(merged, args.min_attempts, TARGET, len(submissions), sources_of(submissions),
                     args.max_per_player)
    print("Wrote %s: %d mobs from %d submission(s)." % (TARGET, kept, len(submissions)))


if __name__ == "__main__":
    main()
