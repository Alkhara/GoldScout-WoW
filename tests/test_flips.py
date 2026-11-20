"""The website's Blackwater flips (site/flips.py, site/flips.js) and the item names behind them
(tools/item_names.py): the same rules as the add-on's Flip tab, worked out the same way in Python and JavaScript."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "tools"))

import flips  # noqa: E402
import item_names  # noqa: E402

NOW = 1795000000
HOUR = 3600


class FakeData:
    """The bits of data_pages.Dataset the pages use: items 2589 and 14047 have pages."""

    def has_page(self, item):
        return item in (2589, 14047)

    item_names = {2589: "Linen Cloth", 287013: "Krol'dok Warplate Legplates"}

    def item_name(self, item):
        return {2589: "Linen Cloth"}.get(item, "Item %d" % item)


NAMES = {14047: ("Runecloth", 1), 7910: ("Star Ruby", 2), 9999: ("<Bad & Name>", 3)}
BUY = {14047: (1000, 20), 7910: (50000, 2), 2589: (100, 5), 3000: (500, 1), 9999: (100, 0)}
SELL = {14047: (2000, 40), 7910: (56000, 3), 2589: (130, 9), 3000: (900, 0), 9999: (900, 4)}


class RuleTests(unittest.TestCase):
    def test_the_rules_are_the_addons(self):
        self.assertEqual((flips.MIN_PROFIT, flips.MIN_MARGIN, flips.MAX_AGE, flips.AH_CUT, flips.PRICE_CAP),
                         (100, 0.15, 43200, 0.95, 3))

    def test_far_above_the_usual_price_is_a_long_shot(self):
        # Simple Wildflowers: 3g 29s on Blackwater, one listed at 100g on the Horde auction house, 1g usually.
        buy, sell = {2589: (32900, 1)}, {2589: (1000600, 1)}
        self.assertEqual(len(flips.flips(buy, sell)), 1)                    # no usual price known: a flip
        rows, long_shots = flips.split(buy, sell, {2589: 10000})
        self.assertEqual((rows, [(r["item"], r["usual"]) for r in long_shots]), ([], [(2589, 10000)]))
        rows, long_shots = flips.split(buy, sell, {2589: 400000})          # 100g is under 3 x 40g
        self.assertEqual((len(rows), long_shots), (1, []))

    def test_flips(self):
        rows = flips.flips(BUY, SELL)
        # Runecloth: 2000 x 0.95 - 1000 = 900c, 90%. Star Ruby: 53200 - 50000 = 3200c but only 6.4%: left out.
        # Linen: 123.5 - 100 = 23.5c, under 1 silver. 3000: none listed on the faction auction house, so no price
        # to sell at. 9999: none to buy on Blackwater.
        self.assertEqual([(r["item"], r["profit"]) for r in rows], [(14047, 900.0)])
        self.assertAlmostEqual(rows[0]["margin"], 0.9)
        self.assertEqual((rows[0]["stock"], rows[0]["listed"]), (20, 40))

    def test_best_profit_first(self):
        rows = flips.flips({1: (1000, 1), 2: (1000, 1), 3: (2000, 1)}, {1: (3000, 1), 2: (5000, 1), 3: (5000, 1)})
        self.assertEqual([r["item"] for r in rows], [2, 3, 1])

    @unittest.skipIf(not shutil.which("node"), "Node isn't installed")
    def test_the_page_script_finds_the_same_flips(self):
        buy = {"%d" % i: [100 + i * 37 % 900, i % 4] for i in range(1, 400)}
        sell = {"%d" % i: [150 + i * 53 % 1300, (i + 1) % 3] for i in range(1, 400)}
        reference = {"%d" % i: 100 + i % 300 for i in range(1, 400, 2)}
        script = ("const f = require(%s).flips; const [b, s, c, p, m, r, x] = JSON.parse(require('fs').readFileSync(0));"
                  "const got = f(b, s, c, p, m, r, x);"
                  "process.stdout.write(JSON.stringify([got.flips, got.long].map(rows => rows.map(r => [r.item, r.profit]))));"
                  % json.dumps(str(ROOT / "site" / "flips.js")))
        done = subprocess.run(["node", "-e", script], input=json.dumps([buy, sell, flips.AH_CUT, flips.MIN_PROFIT,
                                                                       flips.MIN_MARGIN, reference, flips.PRICE_CAP]),
                              capture_output=True, text=True, check=True)
        expected = flips.split({int(k): tuple(v) for k, v in buy.items()}, {int(k): tuple(v) for k, v in sell.items()},
                               {int(k): v for k, v in reference.items()})
        self.assertTrue(expected[0] and expected[1])                        # both lists have rows
        for got, rows in zip(json.loads(done.stdout), expected):
            self.assertEqual([r[0] for r in got], [r["item"] for r in rows])
            for (_, profit), row in zip(got, rows):
                self.assertAlmostEqual(profit, row["profit"])


def house(region, number, ruleset, faction, items=10):
    return {"region": region, "house": number, "ruleset": ruleset, "rulesetName": {1: "PvP", 2: "Normal"}[ruleset],
            "faction": faction, "snapshot": NOW, "items": items}


class MarketTests(unittest.TestCase):
    def test_faction_houses_pair_with_their_blackwater(self):
        listing = {"houses": [house("us", 1, 1, "Alliance"), house("us", 2, 1, "Horde"), house("us", 3, 1, "Neutral"),
                              house("us", 4, 2, "Horde"),                        # no Blackwater for Normal
                              house("eu", 5, 1, "Alliance"), house("eu", 6, 1, "Neutral", items=0)]}   # empty
        asked = []

        def fetch(url):
            asked.append(url)
            if url.endswith("/v1/prices"):
                return listing
            return {"snapshot": NOW, "prices": {"14047": [1000, 3]}}
        markets = flips.fetch_markets("https://api", fetch)
        self.assertEqual([(m["region"], m["faction"], m["sell"]["house"], m["buy"]["house"]) for m in markets],
                         [("us", "Alliance", 1, 3), ("us", "Horde", 2, 3)])
        self.assertEqual(asked.count("https://api/v1/prices/us/3"), 1)            # Blackwater fetched once
        self.assertEqual(markets[0]["buy"]["prices"], {14047: (1000, 3)})
        self.assertEqual(markets[0]["reference"], {14047: 1000})                  # the region's median
        self.assertEqual(json.loads(flips.reference_json(markets, "us")), {"14047": 1000})
        # The faction houses the gold guides already fetched aren't asked for again.
        asked.clear()
        guide = {"region": "us", "house": 1, "snapshot": NOW - 60, "prices": {2589: (5, 1)}}
        markets = flips.fetch_markets("https://api", fetch, known=[guide])
        self.assertNotIn("https://api/v1/prices/us/1", asked)
        self.assertEqual(markets[0]["sell"], {"house": 1, "snapshot": NOW - 60, "prices": {2589: (5, 1)}})

    def test_waits_once_when_the_api_says_too_many(self):
        import urllib.error
        listing = {"houses": [house("us", 1, 1, "Horde"), house("us", 3, 1, "Neutral")]}
        refused, slept = [], []

        def fetch(url):
            if url.endswith("/v1/prices"):
                return listing
            if not refused:
                refused.append(url)
                raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
            return {"snapshot": NOW, "prices": {}}
        markets = flips.fetch_markets("https://api", fetch, sleep=slept.append)
        self.assertEqual((len(markets), slept), (1, [flips.RETRY_AFTER]))

    def test_no_server_no_flips(self):
        def offline(url):
            raise OSError("down")
        self.assertEqual(flips.fetch_markets("https://api", offline), [])


def market(faction="Horde", age=HOUR):
    return {"region": "us", "ruleset": "Normal", "faction": faction,
            "buy": {"house": 117, "snapshot": NOW - age, "prices": BUY},
            "sell": {"house": 114, "snapshot": NOW - HOUR, "prices": SELL}}


class PageTests(unittest.TestCase):
    LINKS = {"curseforge": "https://cf"}

    def test_market_page(self):
        title, description, body = flips.market_page(FakeData(), NAMES, market(), [market(), market("Alliance")],
                                                      self.LINKS, NOW)
        self.assertEqual(title, "Blackwater auction house flips for US Normal Horde (WoW Forever)")
        self.assertIn("1 items are cheaper on the US Normal Blackwater auction house", body)
        self.assertIn('<a class=q1 href="/item/14047">Runecloth</a>', body)        # has a page: linked
        self.assertIn('data-region="us" data-buy="117" data-sell="114" data-cut="0.95"', body)
        self.assertIn('data-min-profit="100" data-min-margin="0.15" data-max-age="43200" data-top="50" data-cap="3.0"', body)
        self.assertIn("<td class=num>20 / 40</td>", body)
        self.assertIn('href="/flips/us/normal-alliance"', body)                    # the other market
        self.assertIn('<script src="/flips.js" defer></script>', body)
        self.assertIn("<details class=long-shots id=long-shots hidden>", body)    # no usual prices: no long shots

    def test_long_shots_are_listed_apart(self):
        # Runecloth usually 5s in the region: 20s on the Horde auction house is over 3 times that.
        long_market = dict(market(), reference={14047: 500})
        _, _, body = flips.market_page(FakeData(), NAMES, long_market, [long_market], self.LINKS, NOW)
        self.assertIn("Nothing on the US Normal Blackwater auction house sells for enough more", body)
        self.assertIn("<details class=long-shots id=long-shots><summary>Long shots: <span id=long-count>1</span>", body)
        self.assertIn("<td class=num>20s</td><td class=num>5s</td><td class=num><b>9s</b></td>", body)
        self.assertIn("<th class=num>Usual in US</th>", body)

    def test_old_prices_list_nothing(self):
        _, _, body = flips.market_page(FakeData(), NAMES, market(age=13 * HOUR), [market()], self.LINKS, NOW)
        self.assertIn("more than 12 hours old", body)
        self.assertIn("No flips right now.", body)

    def test_names_are_escaped_and_fall_back(self):
        data = FakeData()
        self.assertEqual(flips.item_cell(data, NAMES, 9999), "<span class=q3>&lt;Bad &amp; Name&gt;</span>")
        self.assertEqual(flips.item_cell(data, NAMES, 2589), '<a class=q1 href="/item/2589">Linen Cloth</a>')
        self.assertEqual(flips.item_cell(data, NAMES, 5), "<span class=q1>Item 5</span>")

    def test_index_page(self):
        _, _, body = flips.index_page(FakeData(), NAMES, [market(), market("Alliance", age=20 * HOUR)], self.LINKS, NOW)
        self.assertIn('<a href="/flips/us/normal-horde">US Normal Horde</a></td><td class=num>1</td>', body)
        self.assertIn("prices too old", body)

    def test_names_for_the_page_script(self):
        names = json.loads(flips.names_json(FakeData(), NAMES))
        self.assertEqual(names["14047"], ["Runecloth", 1, 1])
        self.assertEqual(names["7910"], ["Star Ruby", 2, 0])
        self.assertEqual(names["287013"], ["Krol'dok Warplate Legplates", 1, 0])   # Blizzard doesn't know it

    def test_build_writes_every_market(self):
        written = {}
        paths = flips.build(FakeData(), self.LINKS, lambda path, *page: written.setdefault(path, page),
                            [market(), market("Alliance")], NAMES, NOW)
        self.assertEqual(paths, ["/flips", "/flips/us/normal-horde", "/flips/us/normal-alliance"])
        self.assertEqual(sorted(written), ["flips.html", "flips/us/normal-alliance.html", "flips/us/normal-horde.html"])


class ItemNameTests(unittest.TestCase):
    def test_blizzards_reply(self):
        self.assertEqual(item_names.name_of({"name": "Runecloth", "quality": {"type": "COMMON"}}), ["Runecloth", 1])
        self.assertEqual(item_names.name_of({"name": " Star Ruby ", "quality": {"type": "UNCOMMON"}}), ["Star Ruby", 2])
        self.assertIsNone(item_names.name_of({"name": ""}))
        self.assertIsNone(item_names.name_of(None))

    def test_the_file_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "names.json"
            item_names.save({14047: ["Runecloth", 1], 25: ["Worn Shortsword", 1]}, path)
            self.assertTrue(path.read_text(encoding="utf-8").startswith('{\n  "25": '))   # sorted by number
            self.assertEqual(item_names.load(path), {25: ["Worn Shortsword", 1], 14047: ["Runecloth", 1]})
            self.assertEqual(flips.load_names(path), {25: ("Worn Shortsword", 1), 14047: ("Runecloth", 1)})

    def test_the_shipped_file_is_valid(self):
        names = flips.load_names()
        self.assertTrue(all(isinstance(name, str) and name and 0 <= quality <= 7 for name, quality in names.values()))


if __name__ == "__main__":
    unittest.main()
