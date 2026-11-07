#!/usr/bin/env python3
"""Combine players' /gscout export strings into GoldScout/Data_Community.lua.

Save each submission as a text file in a folder (default: submissions/, which
git ignores), then run:

  python tools/merge_data.py                 merge submissions/ into the addon
  python tools/merge_data.py --input DIR     use another folder
  python tools/merge_data.py --min-attempts 10

Identical submissions are counted once. Mobs with fewer recorded attempts than
--min-attempts are left out. Spawn spots are the position-weighted average on
the map where the mob was looted most.
"""
import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

HEADER = "GoldScout-export 1"


def parse_items(text):
    items = {}
    for part in filter(None, text.split(",")):
        item_id, times, quantity = part.split(":")
        items[int(item_id)] = (int(times), int(quantity))
    return items


def parse_submission(text):
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines or lines[0] != HEADER:
        raise ValueError("not a GoldScout export (missing '%s' header)" % HEADER)
    mobs = []
    for line in lines[1:]:
        fields = line.split("^")
        if len(fields) != 12:
            raise ValueError("malformed line: %s" % line[:60])
        npc, kills, picks, lmin, lmax, map_id, x, y, positions, name, drops, picks_drops = fields
        mobs.append({
            "npc": int(npc), "k": int(kills), "p": int(picks), "lmin": int(lmin), "lmax": int(lmax),
            "m": int(map_id), "x": float(x), "y": float(y), "c": int(positions), "n": name.strip(),
            "i": parse_items(drops), "pi": parse_items(picks_drops),
        })
    return mobs


def merge(submissions):
    merged = {}
    for mobs in submissions:
        for mob in mobs:
            entry = merged.setdefault(mob["npc"], {
                "k": 0, "p": 0, "lmin": 0, "lmax": 0, "names": defaultdict(int),
                "maps": defaultdict(lambda: [0.0, 0.0, 0]),
                "i": defaultdict(lambda: [0, 0]), "pi": defaultdict(lambda: [0, 0]),
            })
            entry["k"] += mob["k"]
            entry["p"] += mob["p"]
            if mob["lmin"]:
                entry["lmin"] = min(entry["lmin"] or mob["lmin"], mob["lmin"])
            entry["lmax"] = max(entry["lmax"], mob["lmax"])
            if mob["n"]:
                entry["names"][mob["n"]] += 1
            if mob["m"] and mob["c"]:
                spot = entry["maps"][mob["m"]]
                spot[0] += mob["x"] * mob["c"]
                spot[1] += mob["y"] * mob["c"]
                spot[2] += mob["c"]
            for key in ("i", "pi"):
                for item_id, (times, quantity) in mob[key].items():
                    entry[key][item_id][0] += times
                    entry[key][item_id][1] += quantity
    return merged


def lua_items(items):
    parts = ["[%d] = { d = %d, q = %d }" % (item_id, d, q) for item_id, (d, q) in sorted(items.items())]
    return "{ " + ", ".join(parts) + " }" if parts else "{}"


def lua_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_lua(merged, min_attempts, path, contributors):
    out = [
        "-- GoldScout community data: drop rates and spawn spots collected by players",
        "-- with /gscout export and combined by tools/merge_data.py. Generated file;",
        "-- don't edit by hand. Built from %d submission(s)." % contributors,
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
            name = max(entry["names"].items(), key=lambda pair: pair[1])[0]
            fields.append("n = %s" % lua_string(name))
        if entry["maps"]:
            map_id, (sx, sy, count) = max(entry["maps"].items(), key=lambda pair: pair[1][2])
            fields += ["m = %d" % map_id, "x = %.4f" % (sx / count), "y = %.4f" % (sy / count), "c = %d" % count]
        fields += ["i = %s" % lua_items(entry["i"]), "pi = %s" % lua_items(entry["pi"])]
        out.append("  [%d] = { %s }," % (npc, ", ".join(fields)))
    out.append("}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return kept


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Merge GoldScout exports into Data_Community.lua.")
    parser.add_argument("--input", default=str(root / "submissions"), help="folder of export text files")
    parser.add_argument("--min-attempts", type=int, default=5, help="minimum kills plus picks per mob")
    args = parser.parse_args()

    folder = Path(args.input)
    if not folder.is_dir():
        sys.exit("No submissions folder at %s" % folder)
    seen, submissions = set(), []
    for path in sorted(folder.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
        if digest in seen:
            print("skip duplicate: %s" % path.name)
            continue
        try:
            submissions.append(parse_submission(text))
            seen.add(digest)
        except ValueError as error:
            print("skip %s: %s" % (path.name, error))
    if not submissions:
        sys.exit("No valid submissions found in %s" % folder)

    target = root / "GoldScout" / "Data_Community.lua"
    kept = write_lua(merge(submissions), args.min_attempts, target, len(submissions))
    print("Wrote %s: %d mobs from %d submission(s)." % (target, kept, len(submissions)))


if __name__ == "__main__":
    main()
