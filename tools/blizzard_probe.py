"""First look at WoW Forever auction data from Blizzard's Game Data API.

Reads BLIZZARD_CLIENT_ID and BLIZZARD_CLIENT_SECRET from the environment or
from server/.dev.vars (git-ignored), then reports:
  - the rulesets and their auction houses
  - per house: auction count, size, Last-Modified (how old the snapshot is)
  - whether different rulesets return the same data (reported bug, Nov 2026)
  - the lowest unit price of a few sample items in each house

  python tools/blizzard_probe.py
  python tools/blizzard_probe.py --region eu --items 2770,2589

Nothing is saved; the secret is never printed.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEV_VARS = ROOT / "server" / ".dev.vars"
SAMPLE_ITEMS = [2770, 2589, 2996]  # Copper Ore, Linen Cloth, Bolt of Linen Cloth


def credentials():
    values = {}
    if DEV_VARS.exists():
        for line in DEV_VARS.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep:
                values[key.strip()] = value.strip().strip('"').strip("'")
    cid = os.environ.get("BLIZZARD_CLIENT_ID") or values.get("BLIZZARD_CLIENT_ID")
    secret = os.environ.get("BLIZZARD_CLIENT_SECRET") or values.get("BLIZZARD_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("Put BLIZZARD_CLIENT_ID=... and BLIZZARD_CLIENT_SECRET=... in %s" % DEV_VARS)
    return cid, secret


def token(cid, secret):
    auth = base64.b64encode(("%s:%s" % (cid, secret)).encode()).decode()
    req = urllib.request.Request(
        "https://oauth.battle.net/token", data=b"grant_type=client_credentials",
        headers={"Authorization": "Basic " + auth,
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit("Token request failed: HTTP %d (check the client ID and secret)" % e.code)


class Api:
    def __init__(self, region, access):
        self.base = "https://%s.api.blizzard.com" % region
        self.namespace = "dynamic-forever-%s" % region
        self.access = access
        self.calls = 0

    def get(self, path):
        url = "%s%s?%s" % (self.base, path, urllib.parse.urlencode(
            {"namespace": self.namespace, "locale": "en_US"}))
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.access, "Accept-Encoding": "identity"})
        self.calls += 1
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read()
                return resp.status, body, resp.headers.get("Last-Modified"), time.time() - started
        except urllib.error.HTTPError as e:
            return e.code, e.read(), None, time.time() - started


def age(last_modified):
    if not last_modified:
        return "no Last-Modified"
    minutes = (time.time() - parsedate_to_datetime(last_modified).timestamp()) / 60
    return "%s (%.0f min old)" % (last_modified, minutes)


def unit_price(auction):
    if auction.get("unit_price"):
        return auction["unit_price"]
    if auction.get("buyout"):
        return auction["buyout"] / max(auction.get("quantity", 1), 1)
    return None


def money(copper):
    if copper is None:
        return "-"
    copper = int(round(copper))
    return "%dg %02ds %02dc" % (copper // 10000, copper // 100 % 100, copper % 100)


def describe(api, path, items):
    status, body, last_modified, seconds = api.get(path)
    if status != 200:
        print("    %s -> HTTP %d %s" % (path, status, body[:120]))
        return None
    data = json.loads(body)
    auctions = data.get("auctions") or []
    print("    %s: %d auctions, %.1f MB, %.1fs, %s" % (
        path, len(auctions), len(body) / 1e6, seconds, age(last_modified)))
    if auctions:
        keys = sorted(auctions[0].keys())
        print("      auction fields: %s" % ", ".join(keys))
    lowest = {}
    for a in auctions:
        item = (a.get("item") or {}).get("id")
        price = unit_price(a)
        if item in items and price is not None:
            p, q = lowest.get(item, (price, 0))
            lowest[item] = (min(p, price), q + a.get("quantity", 1))
    for item in items:
        if item in lowest:
            print("      item %d: lowest %s, %d listed at all prices" % (item, money(lowest[item][0]), lowest[item][1]))
    # The body embeds links with the ruleset id, so compare the auctions themselves.
    ids = ",".join(str(a.get("id")) for a in sorted(auctions, key=lambda a: a.get("id", 0)))
    return hashlib.sha256(ids.encode()).hexdigest()[:12]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us", choices=["us", "eu", "kr", "tw"])
    parser.add_argument("--items", default=",".join(map(str, SAMPLE_ITEMS)),
                        help="comma-separated item IDs to price")
    parser.add_argument("--all", action="store_true",
                        help="download every house of every ruleset (otherwise only the first ruleset in full)")
    args = parser.parse_args()
    items = {int(x) for x in args.items.split(",") if x.strip()}

    api = Api(args.region, token(*credentials()))
    print("ok   token received")

    status, body, _, _ = api.get("/data/wow/ruleset/index")
    if status != 200:
        sys.exit("ruleset index: HTTP %d %s" % (status, body[:200]))
    rulesets = json.loads(body).get("rulesets") or json.loads(body).get("ruleset") or []
    print("ok   %d rulesets: %s" % (len(rulesets), ", ".join(
        "%s=%s" % (r.get("id"), r.get("name")) for r in rulesets)))

    fingerprints = {}
    for n, ruleset in enumerate(rulesets):
        rid = ruleset.get("id")
        print("\n== ruleset %s (%s)" % (rid, ruleset.get("name")))
        status, body, _, _ = api.get("/data/wow/ruleset/%s/auctions/" % rid)
        if status != 200:
            print("    auction index: HTTP %d %s" % (status, body[:200]))
            continue
        index = json.loads(body)
        houses = index.get("auctions") or []
        print("    houses: %s" % ", ".join("%s=%s" % (h.get("id"), h.get("name")) for h in houses))
        full = args.all or n == 0
        for i, house in enumerate(houses if full else houses[:1]):
            hid = house.get("id")
            fp = describe(api, "/data/wow/ruleset/%s/auctions/%s" % (rid, hid), items)
            if fp:
                fingerprints.setdefault(hid, {})[rid] = fp
            if args.all or i == 0:  # commodities (stackables like ore and cloth) are per house too
                describe(api, "/data/wow/ruleset/%s/auctions/%s/commodities" % (rid, hid), items)

    print("\n== same data across rulesets?")
    for hid, by_ruleset in sorted(fingerprints.items()):
        if len(by_ruleset) > 1:
            same = len(set(by_ruleset.values())) == 1
            print("    house %s: %s" % (hid, "IDENTICAL in every ruleset" if same else "differs by ruleset"))
    print("\n%d API calls (limit 36,000 an hour)" % api.calls)


if __name__ == "__main__":
    main()
