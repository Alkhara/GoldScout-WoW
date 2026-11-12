"""WoW Forever auction house prices from Blizzard's Game Data API.

  python tools/ah_prices.py fetch    fetch every auction house, in every
                                     region (US, EU, KR, TW), that has a new
                                     snapshot and send the prices to the
                                     GoldScout server (the ah-prices workflow
                                     runs this every 15 minutes)
  python tools/ah_prices.py match    compare your own GoldScout auction house
                                     scans with every house, to map houses to
                                     rulesets in data/ah_houses.json

For each house the server keeps only the newest snapshot, reduced to the
lowest unit buyout and total quantity per item. Blizzard's API terms allow
keeping API data for at most 30 days; the server deletes older rows.

fetch needs BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET and GOLDSCOUT_API_ADMIN
(environment, or server/.dev.vars locally where ADMIN_TOKEN also works), and
uses GOLDSCOUT_API_URL when set.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import format_datetime, parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOUSES_FILE = ROOT / "data" / "ah_houses.json"
DEV_VARS = ROOT / "server" / ".dev.vars"
DEFAULT_API = "https://api.wowgoldscout.com"
REGION = "us"                        # where `match` looks (your own scans are US)
REGIONS = ("us", "eu", "kr", "tw")   # WoW Forever regions with a Game Data API
# Cloudflare answers Python's default User-Agent with 403 (error 1010).
USER_AGENT = "GoldScout-ah-prices/1.0 (+https://github.com/Alkhara/GoldScout-WoW)"
FACTIONS = {"Alliance Auction House": "Alliance", "Horde Auction House": "Horde",
            "Blackwater Auction House": "Neutral"}


# ---------------------------------------------------------------------------
# Pure helpers (tested in tests/test_ah_prices.py)
# ---------------------------------------------------------------------------
def unit_price(auction):
    """Copper per unit for buying it out now, or None for bid-only auctions."""
    if auction.get("unit_price"):
        return int(auction["unit_price"])
    if auction.get("buyout"):
        return int(round(auction["buyout"] / max(auction.get("quantity") or 1, 1)))
    return None


def reduce_auctions(*lists):
    """{itemID: [lowest unit buyout, total quantity listed]} over auction lists."""
    out = {}
    for auctions in lists:
        for a in auctions or ():
            item = (a.get("item") or {}).get("id")
            price = unit_price(a)
            if not item or price is None or price <= 0:
                continue
            quantity = int(a.get("quantity") or 1)
            entry = out.get(item)
            if entry:
                entry[0] = min(entry[0], price)
                entry[1] += quantity
            else:
                out[item] = [price, quantity]
    return out


def prices_json(prices):
    """Compact JSON text the server stores as is: {"itemID":[price,qty],...}."""
    return json.dumps({str(k): prices[k] for k in sorted(prices)}, separators=(",", ":"))


def http_time(unix):
    return format_datetime(datetime.fromtimestamp(unix, timezone.utc), usegmt=True)


def unix_time(http_date):
    return int(parsedate_to_datetime(http_date).timestamp()) if http_date else None


def load_houses(path=HOUSES_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mapping_for(config, region, house):
    """(ruleset id, ruleset name, faction) for a mapped house, else Nones."""
    entry = config.get("houses", {}).get(region, {}).get(str(house))
    if not entry:
        return None, None, None
    ruleset = entry["ruleset"]
    return ruleset, config["rulesets"][str(ruleset)], entry["faction"]


# The companion matches scans to houses the same way (companion/auction_prices.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))
from auction_prices import clear_match, score  # noqa: E402,F401


# ---------------------------------------------------------------------------
# Talking to Blizzard and to our server
# ---------------------------------------------------------------------------
def settings():
    values = {}
    if DEV_VARS.exists():
        for line in DEV_VARS.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key.strip()] = value.strip().strip('"').strip("'")

    def get(*names):
        for name in names:
            if os.environ.get(name):
                return os.environ[name]
        for name in names:
            if values.get(name):
                return values[name]
        return ""

    return {
        "client_id": get("BLIZZARD_CLIENT_ID"),
        "client_secret": get("BLIZZARD_CLIENT_SECRET"),
        "admin": get("GOLDSCOUT_API_ADMIN", "ADMIN_TOKEN"),
        "api": (os.environ.get("GOLDSCOUT_API_URL") or DEFAULT_API).rstrip("/"),
    }


class Blizzard:
    def __init__(self, client_id, client_secret, region=REGION, token=None):
        self.region = region
        self.base = "https://%s.api.blizzard.com" % region
        self.namespace = "dynamic-forever-%s" % region
        self.calls = 0
        if token:   # one OAuth token works for every region
            self.token = token
            return
        auth = base64.b64encode(("%s:%s" % (client_id, client_secret)).encode()).decode()
        request = urllib.request.Request(
            "https://oauth.battle.net/token", data=b"grant_type=client_credentials",
            headers={"Authorization": "Basic " + auth, "Content-Type": "application/x-www-form-urlencoded",
                     "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.token = json.load(response)["access_token"]
        except urllib.error.HTTPError as error:
            raise SystemExit("Blizzard token request failed: HTTP %d. Check the client ID and secret." % error.code)

    def get(self, path, since=None):
        """(status, parsed JSON or None, Last-Modified as unix time)."""
        query = urllib.parse.urlencode({"namespace": self.namespace, "locale": "en_US"})
        headers = {"Authorization": "Bearer " + self.token, "User-Agent": USER_AGENT}
        if since:
            headers["If-Modified-Since"] = http_time(since)
        request = urllib.request.Request("%s%s?%s" % (self.base, path, query), headers=headers)
        self.calls += 1
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    return response.status, json.load(response), unix_time(response.headers.get("Last-Modified"))
            except urllib.error.HTTPError as error:
                if error.code == 304:
                    return 304, None, since
                if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                return error.code, None, None
            except (urllib.error.URLError, TimeoutError):
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise


def server_request(api, path, admin=None, method="GET", body=None, headers=None):
    all_headers = dict(headers or {}, **{"User-Agent": USER_AGENT})
    if admin:
        all_headers["Authorization"] = "Bearer " + admin
    data = body.encode("utf-8") if isinstance(body, str) else body
    if data is not None:
        all_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(api + path, data=data, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.load(error)
        except ValueError:
            return error.code, {}


def house_list(blizzard):
    """{house id: (name, ruleset ids listing it)} from every ruleset's index."""
    status, index, _ = blizzard.get("/data/wow/ruleset/index")
    if status != 200:
        raise SystemExit("Ruleset index (%s): HTTP %s" % (blizzard.region, status))
    houses = {}
    for ruleset in index.get("rulesets") or []:
        status, auctions, _ = blizzard.get("/data/wow/ruleset/%s/auctions/" % ruleset["id"])
        if status != 200:
            print("warn ruleset %s auction index: HTTP %s" % (ruleset["id"], status))
            continue
        for house in auctions.get("auctions") or []:
            name, rulesets = houses.get(house["id"], (house.get("name", ""), []))
            rulesets.append(ruleset["id"])
            houses[house["id"]] = (name, rulesets)
    return houses


def fetch(args):
    s = settings()
    missing = [n for n, k in (("BLIZZARD_CLIENT_ID", "client_id"), ("BLIZZARD_CLIENT_SECRET", "client_secret"),
                              ("GOLDSCOUT_API_ADMIN", "admin")) if not s[k]]
    if missing:
        raise SystemExit("Missing: %s" % ", ".join(missing))
    config = load_houses()
    status, stored = server_request(s["api"], "/v1/prices")
    if status != 200:
        raise SystemExit("GoldScout server %s/v1/prices: HTTP %s %s" % (s["api"], status, stored))
    known = {(h["region"], h["house"]): h for h in stored.get("houses", [])}
    realm_notes = sync_realms(s, config, stored)

    lines, updated, failed, total, calls, token = [], 0, 0, 0, 0, None
    for region in REGIONS:
        blizzard = Blizzard(s["client_id"], s["client_secret"], region=region, token=token)
        token = blizzard.token
        try:
            houses = house_list(blizzard)
        except SystemExit as error:
            failed += 1
            total += 1
            lines.append("| %s | | | **failed** (%s) | |" % (region.upper(), error))
            calls += blizzard.calls
            continue
        total += len(houses)
        result = fetch_region(args, s, config, known, blizzard, houses)
        lines += result["lines"]
        updated += result["updated"]
        failed += result["failed"]
        calls += blizzard.calls

    report = ["**Auction prices:** %d house(s) updated, %d failed, %d Blizzard API calls." % (
        updated, failed, calls)] + realm_notes + [
        "", "| Region | House | Ruleset | Result | Snapshot |", "|---|---|---|---|---|"] + lines
    print("\n".join(report))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(report) + "\n")
    # Fail the run (and email the maintainer) only when nothing worked at all;
    # one house hiccupping is retried by the next run 15 minutes later.
    if failed and failed == total:
        sys.exit(1)


def fetch_region(args, s, config, known, blizzard, houses):
    """Fetches one region's houses that have a new snapshot and stores them."""
    region = blizzard.region
    out = {"lines": [], "updated": 0, "failed": 0}

    def line(house, ruleset_name, result, when=""):
        out["lines"].append("| %s | %d | %s | %s | %s |" % (region.upper(), house, ruleset_name or "?", result, when))

    for house in sorted(houses):
        name, listed_by = houses[house]
        ruleset, ruleset_name, faction = mapping_for(config, region, house)
        faction = faction or FACTIONS.get(name, "")
        previous = known.get((region, house))
        same_mapping = previous and previous.get("ruleset") == ruleset and previous.get("faction") == faction
        since = previous["snapshot"] if previous and same_mapping and not args.force else None
        base = "/data/wow/ruleset/%d/auctions/%d" % (listed_by[0], house)
        st1, regular, lm1 = blizzard.get(base, since)
        st2, commodities, lm2 = blizzard.get(base + "/commodities", since)
        if st1 == 304 and st2 == 304:
            line(house, ruleset_name, "unchanged", age_text(since))
            continue
        if st1 == 304:
            st1, regular, lm1 = blizzard.get(base)
        if st2 == 304:
            st2, commodities, lm2 = blizzard.get(base + "/commodities")
        if st1 != 200 or st2 not in (200, 404):
            out["failed"] += 1
            line(house, ruleset_name, "**failed** (HTTP %s / %s)" % (st1, st2))
            continue
        prices = reduce_auctions((regular or {}).get("auctions"), (commodities or {}).get("auctions"))
        if not prices and not previous:
            line(house, ruleset_name, "empty, not stored")   # a set no realm uses
            continue
        snapshot = max(t for t in (lm1, lm2, 0) if t is not None) or int(time.time())
        headers = {"X-Snapshot": str(snapshot), "X-House-Name": name, "X-Faction": faction,
                   "X-Items": str(len(prices))}
        if ruleset is not None:
            headers.update({"X-Ruleset": str(ruleset), "X-Ruleset-Name": ruleset_name})
        status, answer = server_request(s["api"], "/v1/admin/prices/%s/%d" % (region, house), s["admin"],
                                        "PUT", prices_json(prices), headers)
        if status != 200:
            out["failed"] += 1
            line(house, ruleset_name, "**server refused** (HTTP %s %s)" % (status, answer.get("error", "")))
            continue
        out["updated"] += 1
        line(house, ruleset_name, "%s, %d items" % (answer.get("status", "stored"), len(prices)), age_text(snapshot))
    return out


def sync_realms(s, config, stored):
    """Sends data/ah_houses.json's realm map to the server when it differs, so
    GoldScout Companion can find a player's auction house from the realm name."""
    notes = []
    for region, realms in sorted(config.get("realms", {}).items()):
        if stored.get("realms", {}).get(region) == realms:
            continue
        status, answer = server_request(s["api"], "/v1/admin/realms/%s" % region, s["admin"], "PUT",
                                        json.dumps(realms, sort_keys=True),
                                        {"Content-Type": "application/json"})
        notes.append("Realm map for %s: %s" % (region, answer.get("status") if status == 200 else
                                               "**not stored** (HTTP %s %s)" % (status, answer.get("error", ""))))
    return notes


def age_text(unix):
    if not unix:
        return ""
    return "%s UTC (%d min old)" % (time.strftime("%H:%M", time.gmtime(unix)), (time.time() - unix) // 60)


# ---------------------------------------------------------------------------
# Mapping houses from your own scans
# ---------------------------------------------------------------------------
def my_scans():
    """{market key: {item: lowest price}} from GoldScout's saved data on this PC."""
    sys.path.insert(0, str(ROOT / "companion"))
    import savedvars
    scans = {}
    for forever in savedvars.find_forever_folders():
        for path in savedvars.saved_variables_files(forever):
            variables = savedvars.parse_saved_variables(path.read_text(encoding="utf-8", errors="replace"))
            markets = (variables.get("GoldScoutDB") or {}).get("markets") or {}
            for key, market in markets.items():
                items = (market or {}).get("items") or {}
                newest = max((e.get("t") or 0 for e in items.values() if isinstance(e, dict)), default=0)
                scan = {int(i): e["p"] for i, e in items.items() if isinstance(e, dict) and e.get("p")}
                if scan:
                    scans[key] = (scan, newest)
    return scans


def match(args):
    s = settings()
    scans = my_scans()
    if not scans:
        raise SystemExit("No GoldScout auction house scans found on this PC.")
    blizzard = Blizzard(s["client_id"], s["client_secret"])
    houses = house_list(blizzard)
    house_prices = {}
    for house in sorted(houses):
        base = "/data/wow/ruleset/%d/auctions/%d" % (houses[house][1][0], house)
        _, regular, _ = blizzard.get(base)
        _, commodities, _ = blizzard.get(base + "/commodities")
        house_prices[house] = reduce_auctions((regular or {}).get("auctions"), (commodities or {}).get("auctions"))
    for key, (scan, newest) in sorted(scans.items()):
        hours = (time.time() - newest) / 3600
        ranked = sorted(((score(scan, house_prices[h]), h) for h in house_prices), key=lambda x: -x[0][1])
        print("\n%s (scan %.1f h old, %d items)" % (key, hours, len(scan)))
        for (n, share), h in ranked[:4]:
            print("  house %d (%s): %d items in common, %.0f%% same lowest price" % (h, houses[h][0], n, 100 * share))
        house = clear_match(ranked)
        if house:
            print("  -> clear match: house %d. Add it to data/ah_houses.json with this realm's ruleset." % house)
        else:
            print("  -> no clear match; scan again at the auction house and run this soon after.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="fetch new snapshots and send them to the server")
    f.add_argument("--force", action="store_true", help="fetch every house even if unchanged")
    sub.add_parser("match", help="match your own scans to houses")
    args = parser.parse_args()
    {"fetch": fetch, "match": match}[args.command](args)


if __name__ == "__main__":
    main()
