"""Regional price estimates shipped in the addon (tools/bundle_prices.py), and
how the addon uses them (GoldScout/Prices.lua, in Lua 5.1 via lupa when it's
installed): only while a player has no prices of their own, and never past
30 days."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import bundle_prices as bp  # noqa: E402
from test_auction_prices import PRICES_STUB, NOW  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None


def house(region, number, faction, snapshot=NOW - 3600):
    return {"region": region, "house": number, "faction": faction, "snapshot": snapshot}


class BundleTests(unittest.TestCase):
    def test_median_is_a_price_someone_listed(self):
        self.assertEqual(bp.median_low([300, 100, 200]), 200)
        self.assertEqual(bp.median_low([400, 100, 300, 200]), 200)   # the lower middle, not 250

    def test_items_on_one_house_only_are_left_out(self):
        estimates = bp.region_estimates({1: {"10": [100, 5], "11": [999999, 1]}, 2: {"10": [300, 9]}})
        self.assertEqual(estimates, {10: [100, 5]})
        self.assertEqual(bp.region_estimates({1: {"11": [50, 2]}}), {11: [50, 2]})   # a one-house region

    def test_collect_skips_blackwater_and_stale_houses(self):
        listing = {"source": "Blizzard", "houses": [
            house("eu", 110, "Alliance"), house("eu", 113, "Horde"), house("eu", 116, "Neutral"),
            house("eu", 111, "Alliance", snapshot=NOW - 3 * 86400), house("kr", 110, "Alliance", snapshot=NOW - 7200)]}
        prices = {"/v1/prices/eu/110": {"10": [100, 1]}, "/v1/prices/eu/113": {"10": [300, 3]},
                  "/v1/prices/kr/110": {"20": [5, 50]}}
        fetched = []

        def fetch(api, path):
            fetched.append(path)
            return listing if path == "/v1/prices" else {"prices": prices[path]}

        regions, source = bp.collect("api", NOW, fetch)
        self.assertEqual(source, "Blizzard")
        self.assertEqual(sorted(fetched), ["/v1/prices", "/v1/prices/eu/110", "/v1/prices/eu/113", "/v1/prices/kr/110"])
        self.assertEqual(regions["eu"], {"snapshot": NOW - 3600, "houses": 2, "items": {10: [100, 1]}})
        self.assertEqual(regions["kr"]["snapshot"], NOW - 7200)

    def test_stub_in_git_is_empty(self):
        text = (ROOT / "GoldScout" / "Data_Prices.lua").read_text(encoding="utf-8")
        self.assertEqual(text, bp.lua_text({}, "Empty in git; release builds fill it in."))
        toc = (ROOT / "GoldScout" / "GoldScout.toc").read_text(encoding="utf-8")
        lines = [line.strip() for line in toc.splitlines()]
        self.assertLess(lines.index("Data_Prices.lua"), lines.index("Prices.lua"))   # loads before Prices.lua


@unittest.skipIf(lua51 is None, "lupa is not installed")
class AddonEstimateTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.lua.execute("return loadstring(...)", PRICES_STUB)(self.ns)   # an EU client
        self.bundle({"eu": {"snapshot": NOW - 86400, "houses": 8, "items": {10: [500, 20], 11: [70, 3]}},
                     "us": {"snapshot": NOW - 86400, "houses": 10, "items": {12: [1, 1]}}})
        source = (ROOT / "GoldScout" / "Prices.lua").read_text(encoding="utf-8")
        self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)
        self.ns.db = self.lua.eval("{ markets = {} }")
        self.prices = self.ns.Prices

    def bundle(self, regions):
        self.lua.execute("return loadstring(...)", bp.lua_text(regions, "test"))("GoldScout", self.ns)

    def get(self, item):
        return self.prices.Get(self.prices, item)

    def test_a_new_player_gets_their_regions_estimates(self):
        self.assertEqual(self.get(10), (500, 20, 86400, "estimate"))
        self.assertIsNone(self.get(12))                                   # another region's item
        self.assertEqual(sorted(self.prices.ItemIDs(self.prices).keys()), [10, 11])
        count, last_scan, snapshot, estimate = self.prices.Summary(self.prices)
        self.assertEqual((count, last_scan, snapshot, estimate), (2, None, None, NOW - 86400))

    def test_estimates_stop_once_the_player_has_their_own_prices(self):
        self.prices.Record(self.prices, 11, 90, 1, NOW - 60)
        self.assertIsNone(self.get(10))                                   # not mixed with a scan
        self.assertEqual(self.get(11), (90, 1, 60, "scan"))
        self.assertIsNone(self.prices.Summary(self.prices)[3])

    def test_estimates_stop_after_30_days(self):
        self.lua.globals().NOW = NOW + 30 * 86400
        self.assertIsNone(self.get(10))
        self.assertEqual(self.prices.Summary(self.prices)[0], 0)

    def test_an_empty_bundle_changes_nothing(self):
        self.bundle({})
        self.assertIsNone(self.get(10))


if __name__ == "__main__":
    unittest.main()
