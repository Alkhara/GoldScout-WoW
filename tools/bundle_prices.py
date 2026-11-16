#!/usr/bin/env python3
"""Regional price estimates shipped inside the addon (GoldScout/Data_Prices.lua).

  python tools/bundle_prices.py                 write GoldScout/Data_Prices.lua
  python tools/bundle_prices.py --stub          write the empty file kept in git

A new player has no prices of their own until they scan or install GoldScout
Companion, so the Farm list would start empty. Each release build therefore
ships one price list per region: for every item, the middle (median) lowest
buyout across that region's Alliance and Horde auction houses, from the
GoldScout server's copy of Blizzard's hourly snapshots. The addon uses it only
while the player has no prices of their own (GoldScout/Prices.lua).

Blizzard's API terms allow keeping their data for at most 30 days, so each
region carries its snapshot time and the addon stops using it 30 days later.
The daily data release ships at least every three weeks to keep it fresh.

The file in git is an empty stub; the release workflow writes the real one
just before packaging, so price data never lands in the repository.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "GoldScout" / "Data_Prices.lua"
DEFAULT_API = "https://api.wowgoldscout.com"
USER_AGENT = "GoldScout-bundle-prices/1.0 (+https://github.com/Alkhara/GoldScout-WoW)"
FACTIONS = ("Alliance", "Horde")   # Blackwater (Neutral) houses are a market of their own
MAX_SNAPSHOT_AGE = 2 * 86400       # leave out houses whose snapshot has stopped updating
MIN_HOUSES = 2                     # an item listed on only one house is too easily an outlier

HEADER = """\
-- Regional auction price estimates: the median lowest buyout per item across
-- each region's Alliance and Horde auction houses. Used only until you have
-- prices of your own (GoldScout/Prices.lua), and never after 30 days.
-- Written by tools/bundle_prices.py when a release is built.
-- %s
local _, ns = ...
"""


def median_low(values):
    """The lower middle value: always a price someone actually listed."""
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def region_estimates(houses):
    """{itemID: [median price, median quantity]} over {house: {"itemID": [price, quantity]}}."""
    seen = {}
    for prices in houses.values():
        for item, entry in prices.items():
            seen.setdefault(int(item), []).append(entry)
    needed = min(MIN_HOUSES, len(houses))
    return {item: [median_low([e[0] for e in entries]), median_low([e[1] for e in entries])]
            for item, entries in seen.items() if len(entries) >= needed}


def lua_text(regions, source):
    """The Data_Prices.lua text. regions: {region: {"snapshot", "houses", "items"}}."""
    lines = [HEADER % source, "ns.BUNDLED_PRICES = {"]
    for region in sorted(regions):
        info = regions[region]
        items = ",".join("%d:%d:%d" % (item, price, quantity)
                         for item, (price, quantity) in sorted(info["items"].items()))
        lines.append('  %s = { snapshot = %d, houses = %d, items = "%s" },'
                     % (region, info["snapshot"], info["houses"], items))
    lines.append("}")
    return "\n".join(lines) + "\n"


RETRIES = 3          # tries per request: one slow or failed answer used to stop a whole release
RETRY_PAUSE = 10     # seconds before the second try, doubling after


def fetch_json(api, path, tries=RETRIES, pause=RETRY_PAUSE, sleep=time.sleep, opener=urllib.request.urlopen):
    request = urllib.request.Request(api + path, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, tries + 1):
        try:
            with opener(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429 or attempt == tries:
                raise   # a 404 or 403 won't change; the last try's error is the one to report
            problem = "HTTP %d" % error.code
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as error:
            if attempt == tries:
                raise
            problem = str(error) or error.__class__.__name__
        print("..   %s: %s; trying again in %d s" % (path, problem, pause), file=sys.stderr)
        sleep(pause)
        pause *= 2


def collect(api, now, fetch=fetch_json):
    """{region: {"snapshot": oldest snapshot used, "houses": count, "items": estimates}}, and the source line."""
    listing = fetch(api, "/v1/prices")
    by_region = {}
    for house in listing.get("houses", []):
        if house.get("faction") not in FACTIONS or now - (house.get("snapshot") or 0) > MAX_SNAPSHOT_AGE:
            continue
        by_region.setdefault(house["region"], []).append(house)
    regions = {}
    for region, houses in sorted(by_region.items()):
        prices = {}
        for house in houses:
            prices[house["house"]] = fetch(api, "/v1/prices/%s/%d" % (region, house["house"]))["prices"]
        items = region_estimates(prices)
        if items:
            regions[region] = {"snapshot": min(h["snapshot"] for h in houses), "houses": len(houses), "items": items}
    return regions, listing.get("source", "")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stub", action="store_true", help="write the empty file kept in git")
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    output = Path(args.output)
    if args.stub:
        text = lua_text({}, "Empty in git; release builds fill it in.")
    else:
        regions, source = collect(args.api, int(time.time()))
        if not regions:
            sys.exit("No current auction prices on %s; not writing %s" % (args.api, output))
        text = lua_text(regions, source)
        for region, info in sorted(regions.items()):
            print("ok   %s: %d items from %d auction houses" % (region, len(info["items"]), info["houses"]))
    output.write_bytes(text.encode("utf-8"))
    print("wrote %s (%d KB)" % (output, len(text) // 1024))


if __name__ == "__main__":
    main()
