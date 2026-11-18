"""Gold guides (site/guides.py): the best farms on each realm type and faction's auction house."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))

import data_pages  # noqa: E402
import guides  # noqa: E402
import merge_data  # noqa: E402
import submission  # noqa: E402

# Coyote: 60 kills, Coyote Meat (2673) on 24. Packleader: 55 kills, also Coyote Meat (the same farm).
# Bear: 70 kills, Bear Gall Bladder (3702) on 14 and Big Bear Meat (3730) on 7. Thin: 12 kills (too few).
EXPORT = """GoldScout-export 4^abcdefghijkl^9
1109^60^0^10^11^1436^0.5^0.5^60^Coyote^2673:24:24,2934:6:6^
833^55^0^11^12^1436^0.5^0.5^55^Coyote Packleader^2673:20:20^
3809^70^0^21^22^1440^0.5^0.5^70^Ashenvale Bear^3702:14:14,3730:7:14^
4000^12^0^30^31^1440^0.5^0.5^12^Thin Mob^3702:12:12^
@i^2673^Coyote Meat
@i^3702^Bear Gall Bladder
@i^3730^Big Bear Meat
@i^2934^Ruined Leather Scraps
@m^1436^Westfall
@m^1440^Ashenvale
@q^2673^1:7:1
@q^3702^1:7:1
@q^3730^1:7:1
@q^2934^1:7:1
"""
PRICES = {2673: (1550, 176), 3702: (2000, 12), 3730: (500, 300)}   # 2934 isn't listed: it doesn't count
LINKS = {"curseforge": "https://cf.example/goldscout"}


def dataset():
    result = submission.parse(EXPORT)
    assert result.ok, result.errors
    return data_pages.Dataset([result], merge_data.merge([result.mobs], 1000))


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.data = dataset()
        self.ranked = guides.farms(self.data, PRICES)

    def test_only_mobs_with_solid_kills_and_listed_drops(self):
        self.assertEqual([farm["npc"] for farm in self.ranked], [1109, 833, 3809])
        coyote = self.ranked[0]
        self.assertEqual([part["item"] for part in coyote["parts"]], [2673])   # Ruined Leather Scraps aren't listed
        self.assertAlmostEqual(coyote["per_kill"], 24 / 60 * 1550 * guides.AH_CUT)
        self.assertLess(coyote["cautious"], coyote["per_kill"])

    def test_parts_most_valuable_first_with_stacks(self):
        bear = self.ranked[2]
        self.assertEqual([part["item"] for part in bear["parts"]], [3702, 3730])
        meat = bear["parts"][1]
        self.assertEqual(meat["stack"], 2)
        self.assertAlmostEqual(meat["per_kill"], 7 / 70 * 2 * 500 * guides.AH_CUT)

    def test_the_top_list_has_one_farm_per_item(self):
        self.assertEqual([farm["npc"] for farm in guides.top(self.ranked)], [1109, 3809])

    def test_best_farm_per_level_range(self):
        levels = guides.by_level(self.data, self.ranked)
        self.assertEqual([(bracket, farm["npc"]) for bracket, farm in levels], [((1, 10), 1109), ((11, 20), 833),
                                                                                ((21, 30), 3809)])

    def test_the_hour_range_runs_from_cautious_to_average(self):
        coyote = self.ranked[0]
        low, high = (guides.money(v * data_pages.KILLS_PER_HOUR) for v in (coyote["cautious"], coyote["per_kill"]))
        self.assertEqual(guides.hour_range(coyote), "%s&ndash;%s" % (low, high))


class FetchTests(unittest.TestCase):
    HOUSES = {"houses": [
        {"region": "us", "house": 113, "ruleset": 1, "rulesetName": "PvP", "faction": "Horde", "snapshot": 100,
         "items": 50},
        {"region": "us", "house": 116, "ruleset": 1, "rulesetName": "PvP", "faction": "Neutral", "snapshot": 100,
         "items": 50},
        {"region": "us", "house": 115, "ruleset": None, "rulesetName": None, "faction": "Horde", "snapshot": 100,
         "items": 0},
        {"region": "eu", "house": 110, "ruleset": 2, "rulesetName": "Roleplay PvP", "faction": "Alliance",
         "snapshot": 90, "items": 9},
    ]}

    def fake(self, url):
        if url.endswith("/v1/prices"):
            return self.HOUSES
        return {"prices": {"2673": [1550, 176], "bad": [1, 1], "3702": "nope"}}

    def test_faction_houses_with_prices_only(self):
        markets = guides.fetch_markets("https://api.example", self.fake)
        self.assertEqual([guides.slug(m) for m in markets], ["us/pvp-horde", "eu/roleplay-pvp-alliance"])
        self.assertEqual(markets[0]["prices"], {2673: (1550, 176)})
        self.assertEqual(guides.market_name(markets[1]), "EU Roleplay PvP Alliance")

    def test_no_server_no_guides(self):
        def down(url):
            raise OSError("unreachable")
        self.assertEqual(guides.fetch_markets("https://api.example", down), [])


class PageTests(unittest.TestCase):
    def setUp(self):
        self.data = dataset()
        self.market = {"region": "us", "house": 113, "ruleset": "PvP", "faction": "Horde", "snapshot": 1794986707,
                       "prices": PRICES}
        self.other = dict(self.market, house=114, ruleset="Normal")
        self.pages = {}

        def write(path, title, description, body, index=True):
            self.pages[path] = (title, description, body)
        self.paths = guides.build(self.data, LINKS, write, [self.market, self.other])

    def test_every_market_gets_a_page_and_the_index_links_them(self):
        self.assertEqual(self.paths, ["/guides", "/guides/us/pvp-horde", "/guides/us/normal-horde"])
        index = self.pages["guides.html"][2]
        self.assertIn('href="/guides/us/pvp-horde"', index)
        self.assertIn("Coyote Meat", index)

    def test_market_page(self):
        title, description, body = self.pages["guides/us/pvp-horde.html"]
        self.assertEqual(title, "Best gold farms on US PvP Horde right now (WoW Forever)")
        self.assertIn("US PvP Horde", description)
        self.assertIn("1. <a href=\"/item/2673\">Coyote Meat</a> from <a href=\"/mob/1109\">Coyote</a>", body)
        self.assertIn("2. ", body)
        self.assertNotIn("3. ", body)                    # the Packleader is the same farm as the Coyote
        self.assertIn("15s 50c", body)                   # the lowest buyout
        self.assertIn(">176<", body)                     # listed now
        self.assertIn("18 Nov 2026, 07:25 UTC", body)    # the snapshot
        self.assertIn(data_pages.SOURCE, body)           # Blizzard credited
        self.assertIn('href="/guides/us/normal-horde"', body)
        self.assertNotIn("Thin Mob", body)
        # Each farm hands over to the add-on and carries the mob's whole loot table, priced here.
        self.assertIn("Run it in game with GoldScout.", body)
        self.assertIn('href="https://cf.example/goldscout"', body)
        self.assertIn("Everything players have looted from it (2 items)", body)   # the Coyote: meat and scraps
        self.assertIn("<td class=num>&ndash;</td>", body)                      # scraps aren't listed here

    def test_nothing_ranked_yet(self):
        title, _, body = guides.market_page(self.data, self.market, [], [self.market], LINKS)
        self.assertIn("No farm on US PvP Horde", body)

    def test_money(self):
        self.assertEqual([guides.money(c) for c in (0, 80, 400, 412, 50000, 57600, 123456)],
                         ["0c", "80c", "4s", "4s 12c", "5g", "5g 76s", "12g 34s"])


if __name__ == "__main__":
    unittest.main()
