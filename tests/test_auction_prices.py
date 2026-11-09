"""In-game auction prices: GoldScout Companion picks your auction houses and
writes the GoldScout_Prices data addon (companion/auction_prices.py), and the
addon uses whichever is newer per item, that snapshot or your own scan
(GoldScout/Prices.lua, run in Lua 5.1 via lupa when it's installed)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

import auction_prices as ap  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

NOW = 1_800_000_000
PVP = "CAMWOWUS2Realm2PvP-Horde"
OTHER = "SomeNormalRealm-Horde"


class FakeAccount:
    def __init__(self, markets=None, seen=None):
        self.markets, self.seen_markets = markets or {}, seen or {}


def scan(prices, when):
    return {"lastScan": when, "items": {item: {"p": price, "q": 1, "t": when} for item, price in prices.items()}}


def house(number, faction, ruleset=None, snapshot=NOW - 600, items=300):
    return {"region": "us", "house": number, "name": "Auction House", "ruleset": ruleset,
            "rulesetName": "PvP" if ruleset == 1 else None, "faction": faction, "snapshot": snapshot,
            "fetched": snapshot + 300, "items": items}


class FakeServer:
    """Answers /v1/prices and /v1/prices/us/<house> like the GoldScout server."""

    def __init__(self, houses, prices, realms=None):
        self.houses, self.prices, self.realms, self.calls = houses, prices, realms or {}, []

    def __call__(self, path):
        self.calls.append(path)
        if path == "/v1/prices":
            return {"houses": self.houses, "realms": self.realms}
        number = int(path.rsplit("/", 1)[1])
        info = next(h for h in self.houses if h["house"] == number)
        return dict(info, prices={str(i): v for i, v in self.prices[number].items()})


class Folder:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.forever = Path(self.temp.name) / "_forever_"
        goldscout = self.forever / "Interface" / "AddOns" / "GoldScout"
        goldscout.mkdir(parents=True)
        (goldscout / "GoldScout.toc").write_text("## Interface: 16001\n## Title: GoldScout\n", encoding="utf-8")
        return self.forever

    def __exit__(self, *exc):
        self.temp.cleanup()


def many(base, count=300, offset=0):
    return {item: [base + item + offset, 5] for item in range(1, count + 1)}


class CompanionTests(unittest.TestCase):
    def test_wanted_markets_are_recent_and_merged(self):
        accounts = [FakeAccount({PVP: scan({1: 10}, NOW - 3600)}, {PVP: NOW - 60, "Old-Horde": NOW - 40 * 86400}),
                    FakeAccount({OTHER: {"items": {}}})]
        wanted = ap.wanted_markets(accounts, NOW)
        self.assertEqual(sorted(wanted), sorted([OTHER, PVP]))   # Old-Horde: last played 40 days ago
        self.assertEqual(wanted[PVP]["scan"], {1: 10})
        self.assertEqual(wanted[PVP]["last_scan"], NOW - 3600)

    def test_realm_map_picks_the_house(self):
        listing = {"houses": [house(110, "Alliance", 1), house(113, "Horde", 1), house(114, "Horde")],
                   "realms": {"us": {"CAMWOWUS2Realm2PvP": 1}}}
        self.assertEqual(ap.house_for_realm(PVP, listing), ("us", 113))
        self.assertIsNone(ap.house_for_realm(OTHER, listing))

    def test_writes_the_data_addon_once_per_snapshot(self):
        server = FakeServer([house(113, "Horde", 1)], {113: {2589: [18, 24560], 2770: [149, 5945]}},
                            {"us": {"CAMWOWUS2Realm2PvP": 1}})
        with Folder() as forever:
            state = {}
            summary = ap.update(forever, [FakeAccount(seen={PVP: NOW})], state, NOW, server)
            self.assertTrue(summary["wrote"])
            self.assertEqual(summary["markets"][PVP]["house"], 113)
            folder = forever / "Interface" / "AddOns" / ap.DATA_ADDON
            toc = (folder / "GoldScout_Prices.toc").read_text(encoding="utf-8")
            self.assertIn("## Interface: 16001", toc)
            self.assertIn(ap.MARKER, toc)
            lua = (folder / ap.DATA_FILE).read_text(encoding="utf-8")
            self.assertIn("[2589]={18,24560},", lua)
            self.assertIn("Blizzard Entertainment Game Data API", lua)

            # Same snapshot an hour later: only the list is fetched, nothing rewritten.
            server.calls.clear()
            again = ap.update(forever, [FakeAccount(seen={PVP: NOW})], state, NOW + 3600, server)
            self.assertFalse(again["wrote"])
            self.assertEqual(server.calls, ["/v1/prices"])

            # A new snapshot is downloaded and written.
            server.houses[0]["snapshot"] = NOW + 3000
            self.assertTrue(ap.update(forever, [FakeAccount(seen={PVP: NOW})], state, NOW + 3600, server)["wrote"])

    def test_unknown_realm_is_matched_from_your_own_recent_scan(self):
        prices = {114: many(100), 120: many(100, offset=7), 124: many(100, offset=13)}
        server = FakeServer([house(114, "Horde"), house(120, "Horde"), house(124, "Horde"), house(111, "Alliance")],
                            {**prices, 111: many(100)})
        mine = {item: value[0] for item, value in prices[120].items()}
        with Folder() as forever:
            state = {}
            accounts = [FakeAccount({OTHER: scan(mine, NOW - 1800)})]
            summary = ap.update(forever, accounts, state, NOW, server)
            self.assertEqual(summary["markets"][OTHER]["house"], 120)
            self.assertEqual(state["learned"][OTHER]["house"], 120)
            self.assertEqual(summary["markets"][OTHER]["how"], "your scan")

    def test_an_old_or_unclear_scan_does_not_guess(self):
        prices = {114: many(100), 120: many(100)}       # two identical houses: no clear winner
        server = FakeServer([house(114, "Horde"), house(120, "Horde")], prices)
        mine = {item: value[0] for item, value in prices[120].items()}
        with Folder() as forever:
            unclear = ap.update(forever, [FakeAccount({OTHER: scan(mine, NOW - 1800)})], {}, NOW, server)
            self.assertEqual(unclear["unknown"], [OTHER])
            server.calls.clear()
            old = ap.update(forever, [FakeAccount({OTHER: scan(mine, NOW - 86400)})], {}, NOW, server)
            self.assertEqual(old["unknown"], [OTHER])
            self.assertEqual(server.calls, ["/v1/prices"])   # a day-old scan isn't compared at all

    def test_removes_only_its_own_folder_when_nothing_is_current(self):
        server = FakeServer([house(113, "Horde", 1)], {113: many(10)}, {"us": {"CAMWOWUS2Realm2PvP": 1}})
        with Folder() as forever:
            state = {}
            ap.update(forever, [FakeAccount(seen={PVP: NOW})], state, NOW, server)
            folder = forever / "Interface" / "AddOns" / ap.DATA_ADDON
            self.assertTrue(folder.exists())
            server.houses[0]["snapshot"] = NOW - 31 * 86400       # past Blizzard's 30 days
            self.assertTrue(ap.update(forever, [FakeAccount(seen={PVP: NOW})], state, NOW, server)["wrote"])
            self.assertFalse(folder.exists())
            folder.mkdir()
            (folder / "GoldScout_Prices.toc").write_text("## Title: someone else's\n", encoding="utf-8")
            self.assertFalse(ap.remove_addon(forever))
            self.assertTrue(folder.exists())

    def test_needs_goldscout_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = ap.update(Path(temp), [FakeAccount(seen={PVP: NOW})], {}, NOW,
                                FakeServer([], {}))
            self.assertIn("isn't installed", summary["problem"])


PRICES_STUB = r"""
local ns = ...
ns.listeners = {}
function ns.Listen(message, handler) ns.listeners[message] = handler end
function ns.MarketKey() return "Realm-Horde" end
NOW = 1800000000
time = function() return NOW end
"""


@unittest.skipIf(lua51 is None, "lupa is not installed")
class AddonPricesTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.lua.execute("return loadstring(...)", PRICES_STUB)(self.ns)
        source = (ROOT / "GoldScout" / "Prices.lua").read_text(encoding="utf-8")
        self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)
        self.ns.db = self.lua.eval("{ markets = {} }")

    def load_companion_file(self, snapshot, items):
        text = ap.lua_text({"Realm-Horde": {"region": "us", "house": 113, "snapshot": snapshot,
                                            "prices": items}}, snapshot + 300)
        self.lua.execute(text)

    def record_scan(self, item, price, quantity, when):
        self.ns.Prices.Record(self.ns.Prices, item, price, quantity, when)

    def get(self, item):
        return self.ns.Prices.Get(self.ns.Prices, item)

    def test_newer_source_wins_per_item(self):
        self.load_companion_file(NOW - 3600, {"10": [500, 7], "11": [900, 2]})
        self.record_scan(10, 450, 3, NOW - 600)          # scanned after the snapshot
        self.record_scan(11, 800, 4, NOW - 7200)         # scanned before it
        self.assertEqual(self.get(10), (450, 3, 600, "scan"))
        self.assertEqual(self.get(11), (900, 2, 3600, "blizzard"))
        self.assertEqual(self.get(12), None)

    def test_scanned_item_missing_from_a_newer_snapshot_is_not_listed(self):
        self.load_companion_file(NOW - 3600, {"10": [500, 7]})
        self.record_scan(11, 800, 4, NOW - 7200)
        self.assertEqual(self.get(11), (800, 0, 7200, "scan"))

    def test_companion_data_older_than_30_days_is_ignored(self):
        self.load_companion_file(NOW - 31 * 86400, {"10": [500, 7]})
        self.assertEqual(self.get(10), None)
        self.assertEqual(self.ns.Prices.Summary(self.ns.Prices), (0, None, None))

    def test_summary_counts_both_sources(self):
        self.load_companion_file(NOW - 3600, {"10": [500, 7], "11": [900, 2]})
        self.record_scan(12, 100, 1, NOW - 60)
        count, _, snapshot = self.ns.Prices.Summary(self.ns.Prices)
        self.assertEqual((count, snapshot), (3, NOW - 3600))

    def test_login_remembers_the_market(self):
        self.ns.listeners["LOGIN"]()
        self.assertEqual(self.ns.db.seenMarkets["Realm-Horde"], NOW)


if __name__ == "__main__":
    unittest.main()
