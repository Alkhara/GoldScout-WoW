"""Auction prices for the GoldScout addon.

Addons can't go online, so GoldScout Companion downloads the GoldScout server's
copy of Blizzard's auction house snapshots for the realms you play and writes
them as a small data addon, GoldScout_Prices, which the game loads at login or
/reload. GoldScout then uses whichever is newer for each item: that snapshot or
your own scan.

Which auction house is yours: GoldScout records each realm's region (US, EU,
KR or TW). The server lists which ruleset each known realm uses; otherwise WoW
Forever realm names end in their ruleset ("CAMWOWUS2Realm2PvP"). Every region
uses the same auction house layout, so ruleset and faction pick the house.
Whenever you've scanned recently, the companion also compares your own scan
with each auction house of your faction and region, on this PC, and goes with
a clear match; nothing about it is uploaded.

The only folder ever written is AddOns/GoldScout_Prices. Blizzard's API terms
allow keeping API data at most 30 days: the server never lists older snapshots,
the addon ignores them, and the folder is removed when nothing current is left.
"""
import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import uploader

DATA_ADDON = "GoldScout_Prices"
DATA_FILE = "Prices.lua"
MARKER = "## X-Written-By: GoldScout Companion"
FORMAT = 1
MAX_AGE = 30 * 86400          # Blizzard Developer API Terms: at most 30 days
SCAN_WINDOW = 2 * 3600        # a scan this close to a snapshot can identify the auction house
FALLBACK_INTERFACE = "16001"
SOURCE = ("Auction data from the Blizzard Entertainment Game Data API. "
          "GoldScout is not affiliated with or endorsed by Blizzard.")


class PriceError(Exception):
    pass


# ---------------------------------------------------------------------------
# Talking to the GoldScout server
# ---------------------------------------------------------------------------
def get_json(path, version="dev", timeout=30):
    request = urllib.request.Request(uploader.upload_url() + path,
                                     headers={"User-Agent": "GoldScoutCompanion/%s" % version})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise PriceError("The GoldScout server answered HTTP %d." % error.code)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise PriceError("Couldn't reach the GoldScout server (%s)." % getattr(error, "reason", error))


# ---------------------------------------------------------------------------
# Which auction houses you need
# ---------------------------------------------------------------------------
def split_market(key):
    """GoldScout's market key "Realm-Faction" as (realm, faction)."""
    realm, _, faction = key.rpartition("-")
    return realm, faction


# WoW Forever realm names end in their ruleset ("CAMWOWUS2Realm2PvP"), and every
# realm with the same ruleset shares one auction house per faction. Longest
# suffix first: "RPPvP" also ends in "PvP". (GoldScout's Core.lua does the same.)
RULESET_SUFFIXES = (("RPPvP", "Roleplay PvP", 15), ("PvP", "PvP", 1), ("PvE", "Normal", 2), ("RP", "Roleplay", 3))
REGION_NAME = re.compile(r"^CAMWOW(US|EU|KR|TW)\d")


def realm_ruleset(realm):
    """(ruleset name, Blizzard ruleset id) from a WoW Forever realm name, or None."""
    for suffix, name, ruleset in RULESET_SUFFIXES:
        if len(realm) > len(suffix) and realm.endswith(suffix):
            return name, ruleset
    return None


def realm_region(realm):
    """"us", "eu", "kr" or "tw" from a WoW Forever realm name, or None."""
    match = REGION_NAME.match(realm)
    return match.group(1).lower() if match else None


def market_label(key):
    """A market as players would say it: "PvP Horde", "PvP Blackwater"."""
    realm, faction = split_market(key)
    if not realm:
        return key
    side = "Blackwater" if faction == "Neutral" else faction
    ruleset = realm_ruleset(realm)
    return "%s %s" % (ruleset[0] if ruleset else realm, side)


def wanted_markets(accounts, now):
    """{market key: {"scan": {item: price}, "last_scan": unix or None, "seen",
    "region"}} for the realms and factions played in the last 30 days, across
    WoW accounts. region is what GoldScout recorded, else from the realm name."""
    found, regions = {}, {}
    for account in accounts:
        for key, region in (getattr(account, "market_regions", None) or {}).items():
            if region in ("us", "eu", "kr", "tw", "cn"):
                regions[key] = region
        times = {}
        for key, seen in (account.seen_markets or {}).items():
            if isinstance(seen, (int, float)):
                times[key] = max(times.get(key, 0), seen)
        for key, market in (account.markets or {}).items():
            if not isinstance(market, dict):
                continue
            last_scan = market.get("lastScan") if isinstance(market.get("lastScan"), (int, float)) else None
            scan = {}
            for item, entry in (market.get("items") or {}).items():
                if isinstance(item, int) and isinstance(entry, dict) and isinstance(entry.get("p"), (int, float)):
                    scan[item] = entry["p"]
            times.setdefault(key, 0)
            if last_scan:
                times[key] = max(times[key], last_scan)
            mine = found.setdefault(key, {"scan": {}, "last_scan": None, "seen": 0})
            if last_scan and (not mine["last_scan"] or last_scan > mine["last_scan"]):
                mine["scan"], mine["last_scan"] = scan, last_scan
        for key, seen in times.items():
            mine = found.setdefault(key, {"scan": {}, "last_scan": None, "seen": 0})
            mine["seen"] = max(mine["seen"], seen)
    wanted = {key: info for key, info in found.items()
              if isinstance(key, str) and "-" in key and (not info["seen"] or now - info["seen"] <= MAX_AGE)}
    for key, info in wanted.items():
        info["region"] = regions.get(key) or realm_region(split_market(key)[0])
    return wanted


def score(scan, house_prices):
    """How well a scan {item: price} matches a house {item: [price, qty]}:
    (items in common, share of them with the same lowest price, within 1c)."""
    common = [i for i in scan if i in house_prices]
    if not common:
        return 0, 0.0
    same = sum(1 for i in common if abs(house_prices[i][0] - scan[i]) <= 1)
    return len(common), same / len(common)


def clear_match(ranked):
    """The best house from [((common, share), house), ...] if it clearly wins."""
    ranked = sorted(ranked, key=lambda entry: -entry[0][1])
    if not ranked:
        return None
    (common, best), house = ranked[0]
    runner_up = ranked[1][0][1] if len(ranked) > 1 else 0
    if common >= 200 and best >= 0.4 and best >= 2 * runner_up:
        return house
    return None


def house_for_realm(key, listing, region=None):
    """(region, house) from the server's realm map, or None."""
    realm, faction = split_market(key)
    for mapped, realms in (listing.get("realms") or {}).items():
        ruleset = realms.get(realm)
        if ruleset is None or (region and mapped != region):
            continue
        for house in listing.get("houses", []):
            if house["region"] == mapped and house["ruleset"] == ruleset and house["faction"] == faction:
                return mapped, house["house"]
    return None


def house_for_realm_name(key, listing, region):
    """(region, house) from the ruleset at the end of the realm's name, or None."""
    realm, faction = split_market(key)
    ruleset = realm_ruleset(realm)
    if not ruleset or not region:
        return None
    for house in listing.get("houses", []):
        if house["region"] == region and house["ruleset"] == ruleset[1] and house["faction"] == faction:
            return region, house["house"]
    return None


# ---------------------------------------------------------------------------
# The data addon
# ---------------------------------------------------------------------------
def addons_folder(forever):
    return Path(forever) / "Interface" / "AddOns"


def interface_version(forever):
    """GoldScout's own ## Interface number, so the data addon is never "out of date"."""
    try:
        for line in (addons_folder(forever) / "GoldScout" / "GoldScout.toc").read_text(encoding="utf-8").splitlines():
            if line.startswith("## Interface:"):
                value = line.split(":", 1)[1].strip()
                if value.replace(",", "").replace(" ", "").isdigit():
                    return value
    except OSError:
        pass
    return FALLBACK_INTERFACE


def lua_string(text):
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def lua_text(markets, written):
    """The data file. markets: {key: {"region", "house", "snapshot", "prices": {item: [price, qty]}}}."""
    lines = ["-- Written by GoldScout Companion and replaced about once an hour. Don't edit.",
             "-- " + SOURCE,
             "GoldScoutPricesData = {",
             "  format = %d," % FORMAT,
             "  written = %d," % written,
             "  source = %s," % lua_string(SOURCE),
             "  markets = {"]
    for key in sorted(markets):
        market = markets[key]
        lines.append("    [%s] = { region = %s, house = %d, snapshot = %d, items = {" % (
            lua_string(key), lua_string(market["region"]), market["house"], market["snapshot"]))
        entries = ["[%d]={%d,%d}," % (item, int(value[0]), int(value[1]))
                   for item, value in sorted((int(i), v) for i, v in market["prices"].items())]
        for start in range(0, len(entries), 12):
            lines.append("      " + "".join(entries[start:start + 12]))
        lines.append("    } },")
    lines += ["  },", "}", ""]
    return "\n".join(lines)


def toc_text(interface):
    return "\n".join([
        "## Interface: %s" % interface,
        "## Title: GoldScout Prices",
        "## Notes: Auction house prices for GoldScout, updated by GoldScout Companion. "
        "Auction data from the Blizzard Entertainment Game Data API.",
        "## Author: GoldScout Companion",
        MARKER,
        "",
        DATA_FILE,
        "",
    ])


def _write(path, text):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def write_addon(forever, markets, written):
    folder = addons_folder(forever) / DATA_ADDON
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / DATA_FILE, lua_text(markets, written))
    _write(folder / (DATA_ADDON + ".toc"), toc_text(interface_version(forever)))
    return folder


def remove_addon(forever):
    """Removes the data addon, but only one the companion wrote."""
    folder = addons_folder(forever) / DATA_ADDON
    toc = folder / (DATA_ADDON + ".toc")
    try:
        if MARKER in toc.read_text(encoding="utf-8"):
            shutil.rmtree(folder)
            return True
    except OSError:
        pass
    return False


def addon_written(forever):
    return (addons_folder(forever) / DATA_ADDON / DATA_FILE).exists()


# ---------------------------------------------------------------------------
# One update
# ---------------------------------------------------------------------------
def update(forever, accounts, state, now, fetch=get_json):
    """Brings the data addon up to date. state is the companion's saved
    {"learned", "tried", "written"} (updated in place). Returns a summary dict:
    {"markets": {key: {"house", "snapshot", "how"}}, "unknown": [keys], "wrote": bool}."""
    learned = state.setdefault("learned", {})
    tried = state.setdefault("tried", {})
    if not (addons_folder(forever) / "GoldScout").is_dir():
        return {"markets": {}, "unknown": [], "unsupported": [], "wrote": False,
                "problem": "GoldScout isn't installed in this WoW folder."}
    wanted = wanted_markets(accounts, now)
    listing = fetch("/v1/prices")
    houses = {(h["region"], h["house"]): h for h in listing.get("houses", [])
              if now - h.get("snapshot", 0) <= MAX_AGE and h.get("items", 0) > 0}
    downloaded = {}

    def prices_for(region, house):
        if (region, house) not in downloaded:
            downloaded[(region, house)] = fetch("/v1/prices/%s/%d" % (region, house))
        return downloaded[(region, house)]

    # Each realm's Blackwater (goblin) auction house too, for GoldScout's extra
    # tooltip line; only when it's mapped, and never reported as unknown.
    extra = set()
    for key in list(wanted):
        realm, faction = split_market(key)
        neutral = realm + "-Neutral"
        if faction != "Neutral" and neutral not in wanted:
            wanted[neutral] = {"scan": {}, "last_scan": None, "seen": 0, "region": wanted[key]["region"]}
            extra.add(neutral)

    served = {h["region"] for h in houses.values()}
    chosen, unknown, unsupported = {}, [], []
    for key, info in sorted(wanted.items()):
        region = info.get("region")
        found, how = None, None
        if key in learned and (learned[key]["region"], learned[key]["house"]) in houses:
            found, how = (learned[key]["region"], learned[key]["house"]), "your scan"
        if not found:
            found, how = house_for_realm(key, listing, region), "realm"
        if not found:
            found, how = house_for_realm_name(key, listing, region), "realm name"
        # A recent scan of your own is checked against the houses of your faction
        # (and region): a clear match wins, and corrects an inferred mapping.
        if info["last_scan"] and len(info["scan"]) >= 200 and tried.get(key) != info["last_scan"]:
            _, faction = split_market(key)
            candidates = [h for h in houses.values() if h["faction"] == faction
                          and (not region or h["region"] == region)
                          and abs(h["snapshot"] - info["last_scan"]) <= SCAN_WINDOW]
            if candidates:
                tried[key] = info["last_scan"]
                ranked = [(score(info["scan"], {int(i): v for i, v in prices_for(h["region"], h["house"])
                                                .get("prices", {}).items()}), (h["region"], h["house"]))
                          for h in candidates]
                match = clear_match(ranked)
                if match:
                    learned[key] = {"region": match[0], "house": match[1], "matched": int(now)}
                    found, how = match, "your scan"
        if found and found in houses:
            chosen[key] = (found, how)
        elif key in extra:
            continue
        elif region and region not in served:
            unsupported.append(key)
        else:
            unknown.append(key)

    summary = {"markets": {key: {"house": house, "region": region,
                                 "snapshot": houses[(region, house)]["snapshot"], "how": how}
                           for key, ((region, house), how) in chosen.items()},
               "unknown": unknown, "unsupported": unsupported, "wrote": False}
    if not chosen:
        if remove_addon(forever):
            summary["wrote"] = True
        state["written"] = {}
        return summary
    current = {key: [region, house, houses[(region, house)]["snapshot"]] for key, ((region, house), _) in chosen.items()}
    if state.get("written") == current and addon_written(forever):
        return summary
    markets = {}
    for key, ((region, house), _) in chosen.items():
        data = prices_for(region, house)
        markets[key] = {"region": region, "house": house, "snapshot": data["snapshot"],
                        "prices": data.get("prices", {})}
    write_addon(forever, markets, int(now))
    state["written"] = {key: [m["region"], m["house"], m["snapshot"]] for key, m in markets.items()}
    summary["wrote"] = True
    return summary
