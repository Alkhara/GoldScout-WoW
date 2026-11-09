"""Tests for tools/ah_prices.py (no network)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ah_prices  # noqa: E402


class ReduceTests(unittest.TestCase):
    def test_lowest_unit_price_and_total_quantity(self):
        regular = [
            {"id": 1, "item": {"id": 10}, "buyout": 500, "quantity": 5},    # 100 each
            {"id": 2, "item": {"id": 10}, "buyout": 90, "quantity": 1},
            {"id": 3, "item": {"id": 11}, "bid": 50, "quantity": 1},       # bid only: no price
            {"id": 4, "item": {"id": 12}, "buyout": 1000, "quantity": 3},  # 333.3 rounds
        ]
        commodities = [
            {"id": 5, "item": {"id": 10}, "unit_price": 95, "quantity": 20},
            {"id": 6, "item": {"id": 13}, "unit_price": 7, "quantity": 200},
        ]
        prices = ah_prices.reduce_auctions(regular, commodities)
        self.assertEqual(prices, {10: [90, 26], 12: [333, 3], 13: [7, 200]})

    def test_empty_and_missing_lists(self):
        self.assertEqual(ah_prices.reduce_auctions(None, []), {})

    def test_prices_json_is_compact_sorted_and_matches_the_server_format(self):
        text = ah_prices.prices_json({13: [7, 200], 10: [90, 26]})
        self.assertEqual(text, '{"10":[90,26],"13":[7,200]}')
        self.assertEqual(ah_prices.prices_json({}), "{}")
        self.assertEqual(json.loads(text), {"10": [90, 26], "13": [7, 200]})

    def test_http_dates_round_trip(self):
        self.assertEqual(ah_prices.unix_time(ah_prices.http_time(1794100000)), 1794100000)
        self.assertEqual(ah_prices.unix_time("Mon, 9 Nov 2026 00:16:25 GMT"), 1794183385)
        self.assertIsNone(ah_prices.unix_time(None))


class MappingTests(unittest.TestCase):
    def test_house_file_is_valid(self):
        config = ah_prices.load_houses()
        for region, houses in config["houses"].items():
            for house, entry in houses.items():
                self.assertTrue(house.isdigit())
                self.assertIn(str(entry["ruleset"]), config["rulesets"])
                self.assertIn(entry["faction"], ("Alliance", "Horde", "Neutral"))
                self.assertTrue(entry.get("how"), "say how house %s was matched" % house)
        for region, realms in config["realms"].items():
            for ruleset in realms.values():
                self.assertIn(str(ruleset), config["rulesets"])

    def test_mapping_for(self):
        config = {"rulesets": {"1": "PvP"}, "houses": {"us": {"113": {"ruleset": 1, "faction": "Horde"}}}}
        self.assertEqual(ah_prices.mapping_for(config, "us", 113), (1, "PvP", "Horde"))
        self.assertEqual(ah_prices.mapping_for(config, "us", 110), (None, None, None))
        self.assertEqual(ah_prices.mapping_for(config, "eu", 113), (None, None, None))

    def test_score_counts_matching_lowest_prices(self):
        scan = {1: 100, 2: 200, 3: 300, 4: 400}
        house = {1: [100, 5], 2: [201, 1], 3: [999, 1], 9: [1, 1]}
        self.assertEqual(ah_prices.score(scan, house), (3, 2 / 3))
        self.assertEqual(ah_prices.score(scan, {}), (0, 0.0))


if __name__ == "__main__":
    unittest.main()
