"""The contributor leaderboard: scores from the validated submissions
(tools/leaderboard.py), the companion's rank line and the ranks it hands
GoldScout through the GoldScout_Prices data addon. The server's routes are
tested in test_server.py."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "companion"))

import auction_prices as ap  # noqa: E402
import leaderboard  # noqa: E402

try:
    import app  # noqa: E402  (needs tkinter)
except ImportError:
    app = None

NOW = 1_800_000_000
PVP = "CAMWOWUS2Realm2PvP-Horde"


def mob(k, p=0):
    return SimpleNamespace(k=k, p=p)


def submission(install_id, *mobs):
    return SimpleNamespace(install_id=install_id, mobs=list(mobs))


class ScoreTests(unittest.TestCase):
    def test_kills_and_mobs_per_install(self):
        table = leaderboard.scores([submission("aaaaaaaaaaaa", mob(10), mob(5)), submission("bbbbbbbbbbbb", mob(3))])
        self.assertEqual(table, {"aaaaaaaaaaaa": [15, 2], "bbbbbbbbbbbb": [3, 1]})

    def test_each_mob_counts_up_to_the_community_data_cap(self):
        # Like merge_data.py: no one player's grind of one mob outweighs the rest.
        table = leaderboard.scores([submission("aaaaaaaaaaaa", mob(5000), mob(20))], cap=1000)
        self.assertEqual(table, {"aaaaaaaaaaaa": [1020, 2]})

    def test_pickpocket_only_installs_are_left_out(self):
        table = leaderboard.scores([submission("aaaaaaaaaaaa", mob(0, p=50)), submission("bbbbbbbbbbbb")])
        self.assertEqual(table, {})

    def test_scores_the_shipped_submissions(self):
        table = leaderboard.scores(leaderboard.merge_data.load(ROOT / "data" / "submissions"))
        self.assertTrue(table)
        self.assertTrue(all(len(i) == 12 and kills > 0 and mobs > 0 for i, (kills, mobs) in table.items()))


@unittest.skipUnless(app, "tkinter isn't available")
class RankTextTests(unittest.TestCase):
    def test_anonymous(self):
        text = app.rank_text({"rank": 4, "contributors": 30, "kills": 12345, "public": False})
        self.assertEqual(text, "Contributor rank: #4 of 30, with 12,345 kills counted. "
                               "You're anonymous on the public board.")

    def test_shown_under_the_alias_until_the_name_is_approved(self):
        info = {"rank": 1, "contributors": 30, "kills": 900, "public": True, "alias": "Patient Boar",
                "name": "Goldfinger", "approved": False}
        self.assertIn("Shown publicly as Patient Boar until Goldfinger is approved.", app.rank_text(info))
        info["approved"] = True
        self.assertIn("Shown publicly as Goldfinger.", app.rank_text(info))

    def test_not_ranked_yet(self):
        self.assertIn("once they're in the community data", app.rank_text({"rank": None, "public": False}))
        self.assertEqual(app.rank_text(None), "")

    def test_ranks_for_the_game_are_this_pcs_ranked_installs(self):
        config = {"leaderboard": {
            "aaaaaaaaaaaa": {"time": 1, "info": {"rank": 2, "contributors": 9, "kills": 70}},
            "bbbbbbbbbbbb": {"time": 1, "info": {"rank": None}},
            "cccccccccccc": {"time": 1}}}
        self.assertEqual(app.contributor_ranks(config, ["aaaaaaaaaaaa", "bbbbbbbbbbbb", "cccccccccccc", "dddddddddddd"]),
                         {"aaaaaaaaaaaa": {"rank": 2, "of": 9, "kills": 70}})


class FakeAccount:
    markets, market_regions = {}, {}

    def __init__(self):
        self.seen_markets = {PVP: NOW}


class PricesFileTests(unittest.TestCase):
    def server(self, path):
        info = {"region": "us", "house": 113, "name": "Auction House", "ruleset": 1, "rulesetName": "PvP",
                "faction": "Horde", "snapshot": NOW - 600, "fetched": NOW - 300, "items": 1}
        if path == "/v1/prices":
            return {"houses": [info], "realms": {"us": {"CAMWOWUS2Realm2PvP": 1}}}
        return dict(info, prices={"2589": [18, 5]})

    def test_ranks_are_written_for_goldscout_and_rewritten_when_they_change(self):
        with tempfile.TemporaryDirectory() as temp:
            forever = Path(temp) / "_forever_"
            (forever / "Interface" / "AddOns" / "GoldScout").mkdir(parents=True)
            data = forever / "Interface" / "AddOns" / ap.DATA_ADDON / ap.DATA_FILE
            state, ranks = {}, {"abcdefghijkl": {"rank": 3, "of": 40, "kills": 1200}}
            self.assertTrue(ap.update(forever, [FakeAccount()], state, NOW, self.server, contributors=ranks)["wrote"])
            self.assertIn('["abcdefghijkl"] = { rank = 3, of = 40, kills = 1200 },', data.read_text(encoding="utf-8"))
            # Same prices and ranks: nothing to write.
            self.assertFalse(ap.update(forever, [FakeAccount()], state, NOW + 60, self.server,
                                       contributors=ranks)["wrote"])
            # A new rank alone rewrites the file.
            ranks = {"abcdefghijkl": {"rank": 2, "of": 41, "kills": 1500}}
            self.assertTrue(ap.update(forever, [FakeAccount()], state, NOW + 120, self.server,
                                      contributors=ranks)["wrote"])
            self.assertIn("rank = 2, of = 41, kills = 1500", data.read_text(encoding="utf-8"))

    def test_no_ranks_no_table(self):
        text = ap.lua_text({}, NOW)
        self.assertNotIn("contributors", text)


if __name__ == "__main__":
    unittest.main()
