#!/usr/bin/env python3
"""Keeps site/item_names.json: the English name and quality of every item listed on any WoW Forever auction
house, from Blizzard's Game Data API, for the website's Blackwater flips pages. Community data only names items
players have looted; flips can be anything on the auction house. Blizzard's Forever item data
(static-forever-us) is missing many classic items (Nov 2026: about 3,200 of 7,600 listed), so those come from
Classic Era's (static-classic1x-us), which has them under the same IDs.

  python tools/item_names.py              adds the items listed now that the file doesn't name yet
  python tools/item_names.py --limit 200  at most 200 new names

Needs BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET (environment or server/.dev.vars), like ah_prices.py.
The item IDs come from GoldScout's public price API. Names never change, so a name is fetched only once.
Run it now and then (new items rarely reach the auction house); a flip whose item isn't named here falls
back to the community data's name, or "Item 1234".
"""
import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ah_prices  # noqa: E402

NAMES_FILE = ROOT / "site" / "item_names.json"
NAMESPACES = ("static-forever-us", "static-classic1x-us")   # first that knows the item
# Blizzard's quality types, as the numbers the game uses (0 poor ... 5 legendary).
QUALITY = {"POOR": 0, "COMMON": 1, "UNCOMMON": 2, "RARE": 3, "EPIC": 4, "LEGENDARY": 5, "ARTIFACT": 6,
           "HEIRLOOM": 7}
WORKERS = 8


def load(path=NAMES_FILE):
    """{itemID: [name, quality]} from the file, {} if there's none yet."""
    if not path.is_file():
        return {}
    return {int(item): value for item, value in json.loads(path.read_text(encoding="utf-8")).items()}


def save(names, path=NAMES_FILE):
    """One item per line, sorted, so a change shows as a small diff."""
    lines = ["  %s: %s" % (json.dumps(str(item)), json.dumps(names[item], ensure_ascii=False))
             for item in sorted(names)]
    path.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8")


def listed_items(api=ah_prices.DEFAULT_API):
    """Every item ID on any auction house GoldScout has prices for."""
    def get(path):
        request = urllib.request.Request(api + path, headers={"User-Agent": ah_prices.USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    items = set()
    for house in get("/v1/prices").get("houses") or []:
        prices = get("/v1/prices/%s/%d" % (house["region"], house["house"])).get("prices") or {}
        items.update(int(item) for item in prices if item.isdigit())
    return items


def name_of(reply):
    """[name, quality] from Blizzard's item reply, or None."""
    if not isinstance(reply, dict) or not isinstance(reply.get("name"), str) or not reply["name"].strip():
        return None
    return [reply["name"].strip(), QUALITY.get((reply.get("quality") or {}).get("type"), 1)]


def fetch(clients, items):
    """{itemID: [name, quality]} for the items Blizzard knows, from the first client (namespace) that does."""
    def one(item):
        for blizzard in clients:
            status, reply, _ = blizzard.get("/data/wow/item/%d" % item)
            found = name_of(reply) if status == 200 else None
            if found:
                return item, found
        return item, None
    with ThreadPoolExecutor(WORKERS) as pool:
        return {item: found for item, found in pool.map(one, sorted(items)) if found}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="at most this many new names (default: all)")
    args = parser.parse_args()
    settings = ah_prices.settings()
    if not settings["client_id"] or not settings["client_secret"]:
        raise SystemExit("Set BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET (or put them in server/.dev.vars).")
    names = load()
    missing = sorted(listed_items(settings["api"]) - set(names))
    if args.limit:
        missing = missing[:args.limit]
    if not missing:
        print("Every listed item is named already (%d names)." % len(names))
        return
    first = ah_prices.Blizzard(settings["client_id"], settings["client_secret"], "us")
    clients = []
    for namespace in NAMESPACES:
        client = ah_prices.Blizzard(None, None, "us", token=first.token)
        client.namespace = namespace
        clients.append(client)
    found = fetch(clients, missing)
    names.update(found)
    save(names)
    print("Added %d names (%d Blizzard didn't know); %d in all." % (len(found), len(missing) - len(found), len(names)))


if __name__ == "__main__":
    main()
