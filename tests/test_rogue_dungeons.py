"""Rogues' dungeon loot from before GoldScout v0.12.48, when a Pick Pocket inside a dungeon counted as a kill:
older exports from an account that pickpockets leave their dungeon mobs out (tools/submission.py
fresh_rogue_dungeons); version 8 exports, which hold only what was recorded since, keep them."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import submission  # noqa: E402

OUTDOORS = "3812^40^0^19^20^1440^0.1300^0.2800^40^Clattering Crawler^3010:25:26^"
DUNGEON = "5000^30^0^40^41^291^0.0000^0.0000^0^Dungeon Ogre^1205:10:10^"
PICKED = "1234^0^9^25^26^0^0.0000^0.0000^0^Defias Pillager^^16882:3:3"
POCKET_LOOT = "1235^12^0^25^26^1440^0.2000^0.2000^12^Defias Looter^16882:2:2,2589:5:5^"


def export(version, *mobs):
    return "GoldScout-export %d^abcdefghijkl^1\n%s\n@m^291^The Deadmines\n" % (version, "\n".join(mobs))


def npcs(text):
    result = submission.parse(text)
    assert result.ok, result.errors
    return sorted(mob.npc for mob in result.mobs), result.left_out


class RogueDungeonTests(unittest.TestCase):
    def test_a_pickpocketers_older_dungeon_mobs_are_left_out(self):
        self.assertEqual(npcs(export(7, OUTDOORS, DUNGEON, PICKED)), ([1234, 3812], 1))

    def test_pocket_loot_in_kills_shows_a_pickpocketer_too(self):
        self.assertEqual(npcs(export(7, OUTDOORS, DUNGEON, POCKET_LOOT)), ([1235, 3812], 1))

    def test_other_players_dungeons_are_kept(self):
        self.assertEqual(npcs(export(7, OUTDOORS, DUNGEON)), ([3812, 5000], 0))

    def test_version_eight_keeps_a_pickpocketers_dungeons(self):
        self.assertEqual(npcs(export(8, OUTDOORS, DUNGEON, PICKED)), ([1234, 3812, 5000], 0))

    def test_stored_files_lose_the_dungeon_mobs_for_good(self):
        result = submission.parse(export(6, OUTDOORS, DUNGEON, PICKED))
        self.assertNotIn("Dungeon Ogre", result.text())
        self.assertTrue(submission.parse(result.text()).ok)

    def test_pickpocketing_alone_is_kept(self):
        # Picks were never counted wrongly: a mob only pickpocketed stays, in a dungeon too.
        self.assertEqual(npcs(export(7, DUNGEON, PICKED)), ([1234], 1))


if __name__ == "__main__":
    unittest.main()
