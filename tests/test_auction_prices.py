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
    def __init__(self, markets=None, seen=None, regions=None):
        self.markets, self.seen_markets, self.market_regions = markets or {}, seen or {}, regions or {}


def scan(prices, when):
    return {"lastScan": when, "items": {item: {"p": price, "q": 1, "t": when} for item, price in prices.items()}}


def house(number, faction, ruleset=None, snapshot=NOW - 600, items=300, region="us"):
    return {"region": region, "house": number, "name": "Auction House", "ruleset": ruleset,
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
        region, number = path.rsplit("/", 2)[1], int(path.rsplit("/", 1)[1])
        info = next(h for h in self.houses if h["house"] == number and h["region"] == region)
        prices = self.prices.get((region, number), self.prices.get(number))
        return dict(info, prices={str(i): v for i, v in prices.items()})


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

    def test_also_saves_the_realms_blackwater_house(self):
        server = FakeServer([house(113, "Horde", 1), house(116, "Neutral", 1), house(114, "Horde", 2)],
                            {113: many(10), 116: many(20), 114: many(30)},
                            {"us": {"CAMWOWUS2Realm2PvP": 1, "PvERealm": 2}})
        with Folder() as forever:
            summary = ap.update(forever, [FakeAccount(seen={PVP: NOW, "PvERealm-Horde": NOW})], {}, NOW, server)
            self.assertEqual(summary["markets"]["CAMWOWUS2Realm2PvP-Neutral"]["house"], 116)
            self.assertEqual(summary["unknown"], [])          # PvE's Blackwater isn't mapped: not "unknown"
            lua = (forever / "Interface" / "AddOns" / ap.DATA_ADDON / ap.DATA_FILE).read_text(encoding="utf-8")
            self.assertIn('["CAMWOWUS2Realm2PvP-Neutral"] = { region = "us", house = 116', lua)

    def test_regions_come_from_goldscout_or_the_realm_name(self):
        eu, plain = "CAMWOWEU1Realm3PvP-Horde", "Ravenholdt-Horde"
        accounts = [FakeAccount(seen={eu: NOW, plain: NOW, PVP: NOW}, regions={plain: "eu"})]
        wanted = ap.wanted_markets(accounts, NOW)
        self.assertEqual((wanted[eu]["region"], wanted[plain]["region"], wanted[PVP]["region"]), ("eu", "eu", "us"))
        self.assertEqual(ap.realm_ruleset("CAMWOWUS1Realm9RPPvP"), ("Roleplay PvP", 15))
        self.assertIsNone(ap.realm_region("Stormrage"))

    def test_other_regions_use_the_realm_names_ruleset(self):
        eu = "CAMWOWEU1Realm3PvP-Horde"
        server = FakeServer([house(113, "Horde", 1), house(113, "Horde", 1, region="eu"),
                             house(114, "Horde", 2, region="eu")],
                            {("us", 113): many(10), ("eu", 113): many(20), ("eu", 114): many(30)})
        with Folder() as forever:
            summary = ap.update(forever, [FakeAccount(seen={eu: NOW})], {}, NOW, server)
            self.assertEqual(summary["markets"][eu], {"house": 113, "region": "eu",
                                                      "snapshot": NOW - 600, "how": "realm name"})
            lua = (forever / "Interface" / "AddOns" / ap.DATA_ADDON / ap.DATA_FILE).read_text(encoding="utf-8")
            self.assertIn('["%s"] = { region = "eu", house = 113' % eu, lua)

    def test_your_scan_corrects_an_inferred_house(self):
        eu = "CAMWOWEU1Realm3PvP-Horde"
        prices = {("eu", 113): many(100), ("eu", 114): many(100, offset=9), ("us", 114): many(100)}
        server = FakeServer([house(113, "Horde", 1, region="eu"), house(114, "Horde", 2, region="eu"),
                             house(114, "Horde", 2)], prices)
        mine = {item: value[0] for item, value in prices[("eu", 114)].items()}
        with Folder() as forever:
            state = {}
            summary = ap.update(forever, [FakeAccount({eu: scan(mine, NOW - 1800)}, regions={eu: "eu"})],
                                state, NOW, server)
            self.assertEqual((summary["markets"][eu]["house"], summary["markets"][eu]["how"]), (114, "your scan"))
            self.assertEqual(state["learned"][eu], {"region": "eu", "house": 114, "matched": NOW})
            # Next hour, no new scan: the learned house still wins over the realm name.
            again = ap.update(forever, [FakeAccount({eu: scan(mine, NOW - 1800)}, regions={eu: "eu"})],
                              state, NOW + 3600, server)
            self.assertEqual(again["markets"][eu]["house"], 114)

    def test_a_region_without_prices_says_so(self):
        cn = "SomeChinaRealm-Horde"
        server = FakeServer([house(113, "Horde", 1)], {113: many(10)})
        with Folder() as forever:
            summary = ap.update(forever, [FakeAccount(seen={cn: NOW}, regions={cn: "cn"})], {}, NOW, server)
            self.assertEqual((summary["unsupported"], summary["unknown"]), ([cn], []))

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
GetCurrentRegion = function() return 3 end
NOW = 1800000000
time = function() return NOW end
FAKE = { map = 1454, npc = "Creature-0-6805-1-18-8724-6384EE0F44" }
UnitGUID = function(unit) if unit == "npc" then return FAKE.npc end end
C_Map = { GetBestMapForUnit = function() return FAKE.map end }
strsplit = function(sep, text)
  local parts = {}
  for part in (text .. sep):gmatch("(.-)%" .. sep) do parts[#parts + 1] = part end
  return unpack(parts)
end
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

    def test_blackwater_is_recognized_only_for_sure(self):
        fake, prices = self.lua.globals().FAKE, self.ns.Prices
        self.assertFalse(prices.AtBlackwater(prices))                      # Orgrimmar, as seen in game
        fake.map, fake.npc = 1446, "Creature-0-7053-1-22-8661-D6187EAA96"  # Gadgetzan, as seen in game
        self.assertTrue(prices.AtBlackwater(prices))
        fake.map = None                                                    # map unknown: the auctioneer decides
        self.assertTrue(prices.AtBlackwater(prices))
        fake.npc = "Creature-0-1-1-1-9999-0"
        self.assertFalse(prices.AtBlackwater(prices))
        self.assertEqual(prices.BlackwaterKey(prices), "Realm-Neutral")

    def test_blackwater_prices_stay_separate(self):
        prices = self.ns.Prices
        self.record_scan(10, 500, 3, NOW - 600)                             # your Horde scan
        neutral = prices.Market(prices, "Realm-Neutral")
        prices.Record(prices, 10, 650, 2, NOW - 60, neutral)              # a newer Blackwater scan
        self.assertEqual(self.get(10), (500, 3, 600, "scan"))               # rankings keep your faction's
        self.assertEqual(prices.Blackwater(prices, 10), (650, 2, 60, "scan"))
        self.assertEqual(prices.Blackwater(prices, 11), None)

    def test_blackwater_from_the_companion_without_creating_a_market(self):
        text = ap.lua_text({"Realm-Neutral": {"region": "us", "house": 116, "snapshot": NOW - 1800,
                                              "prices": {"10": [700, 4]}}}, NOW)
        self.lua.execute(text)
        prices = self.ns.Prices
        self.assertEqual(prices.Blackwater(prices, 10), (700, 4, 1800, "blizzard"))
        self.assertEqual(self.get(10), None)
        self.assertIsNone(self.ns.db.markets["Realm-Neutral"])

    def test_login_remembers_the_market(self):
        self.ns.listeners["LOGIN"]()
        self.assertEqual(self.ns.db.seenMarkets["Realm-Horde"], NOW)
        self.assertEqual(self.ns.db.marketRegions["Realm-Horde"], "eu")   # GetCurrentRegion() 3


LABELS = {
    "CAMWOWUS2Realm2PvP-Horde": "PvP Horde",
    "CAMWOWUS1Realm7PvE-Alliance": "Normal Alliance",
    "CAMWOWUS1Realm10RP-Alliance": "Roleplay Alliance",
    "CAMWOWUS1Realm9RPPvP-Horde": "Roleplay PvP Horde",
    "CAMWOWUS2Realm2PvP-Neutral": "PvP Blackwater",
    "Stormrage-Alliance": "Stormrage Alliance",
    "PvP-Horde": "PvP Horde",           # a realm named only "PvP": shown as it is
}


class MarketLabelTests(unittest.TestCase):
    """Players see "PvP Horde", not the internal realm name; addon and companion agree."""

    def test_companion(self):
        for key, label in LABELS.items():
            with self.subTest(key):
                self.assertEqual(ap.market_label(key), label)

    @unittest.skipIf(lua51 is None, "lupa is not installed")
    def test_addon(self):
        import re
        core = (ROOT / "GoldScout" / "Core.lua").read_text(encoding="utf-8")
        snippet = re.search(r"local RULESET_SUFFIXES = .*?\nend\n", core.replace("\r\n", "\n"), re.S).group(0)
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        ns = lua.table()
        lua.execute("return loadstring(...)", "local ns = ...\n" + snippet)(ns)
        for key, label in LABELS.items():
            with self.subTest(key):
                self.assertEqual(ns.MarketLabel(key), label)


if __name__ == "__main__":
    unittest.main()
