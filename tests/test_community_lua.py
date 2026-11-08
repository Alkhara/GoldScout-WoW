"""Runs GoldScout/Community.lua in a real Lua 5.1 interpreter (via lupa) and
checks that a player's client takes exactly its own shared loot back out of
the community data that tools/merge_data.py builds.

Skipped when lupa isn't installed:  pip install lupa
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import merge_data  # noqa: E402
import submission  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

MINE = """GoldScout-export 2^mineminemine^5
3812^2000^0^19^20^1440^0.1100^0.3000^1500^Clattering Crawler^2674:700:700,3010:1203:1205^
3814^7^0^20^21^1440^0.1215^0.3092^7^Spined Crawler^5569:4:4,2674:4:4^
1234^0^9^25^26^0^0.0000^0.0000^0^Defias Pillager^^16882:3:3
"""
OTHER = """GoldScout-export 2^otherotherot^2
3812^40^0^19^20^1440^0.1300^0.2800^40^Clattering Crawler^2674:12:12,3010:25:26,4874:2:2^
3814^30^0^20^21^1440^0.1200^0.3100^30^Spined Crawler^5569:9:9^
"""


@unittest.skipIf(lua51 is None, "lupa is not installed")
class CommunityLuaTests(unittest.TestCase):
    def load(self, *exports):
        """Builds Data_Community.lua from exports, then loads it and Community.lua."""
        results = [submission.parse(text) for text in exports]
        for result in results:
            self.assertEqual(result.errors, [])
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        ns = lua.table()
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "Data_Community.lua"
            merge_data.write_lua(merge_data.merge([r.mobs for r in results], 1000), 1, data, len(results),
                                 merge_data.sources_of(results), 1000)
            for path in (data, ROOT / "GoldScout" / "Community.lua"):
                chunk = lua.execute("return loadstring(...)", path.read_text(encoding="utf-8"))
                chunk("GoldScout", ns)
        return lua, ns

    def community(self, lua, ns):
        """ns.COMMUNITY as plain Python dicts."""
        out = {}
        for npc, entry in ns.COMMUNITY.items():
            out[npc] = {
                "k": entry.k, "p": entry.p, "c": entry.c, "x": entry.x, "y": entry.y,
                "i": {item: (s.d, s.q) for item, s in (entry.i or lua.table()).items()},
                "pi": {item: (s.d, s.q) for item, s in (entry.pi or lua.table()).items()},
            }
        return out

    def exports_table(self, lua, seq, text):
        exports = lua.table()
        exports.seq = seq
        exports.list = lua.table()
        exports.list[seq] = text
        return exports

    def test_removing_own_snapshot_leaves_only_other_players(self):
        lua, ns = self.load(MINE, OTHER)
        how = ns.Community.RemoveOwn(ns.COMMUNITY, ns.COMMUNITY_SOURCES, ns.COMMUNITY_CAP,
                                     "mineminemine", self.exports_table(lua, 5, MINE), lua.table())
        self.assertEqual(how, "snapshot")
        after = self.community(lua, ns)

        lua_only, ns_only = self.load(OTHER)
        expected = self.community(lua_only, ns_only)
        self.assertEqual(sorted(after), sorted(expected))  # 1234 (only mine) is gone
        for npc in expected:
            for key in ("k", "p", "c", "i", "pi"):
                self.assertEqual(after[npc][key], expected[npc][key], (npc, key))
            self.assertAlmostEqual(after[npc]["x"], expected[npc]["x"], delta=0.002)
            self.assertAlmostEqual(after[npc]["y"], expected[npc]["y"], delta=0.002)

    def test_other_players_are_untouched(self):
        lua, ns = self.load(MINE, OTHER)
        before = self.community(lua, ns)
        how = ns.Community.RemoveOwn(ns.COMMUNITY, ns.COMMUNITY_SOURCES, ns.COMMUNITY_CAP,
                                     "notincludedxx", self.exports_table(lua, 1, MINE), lua.table())
        self.assertIsNone(how)
        self.assertEqual(self.community(lua, ns), before)

    def test_missing_snapshot_falls_back_to_saved_loot(self):
        lua, ns = self.load(MINE, OTHER)
        drops = lua.eval("""{
          [3814] = { k = 7, p = 0, c = 7, m = 1440, sx = 0.8505, sy = 2.1644,
                     i = { [5569] = { d = 4, q = 4 }, [2674] = { d = 4, q = 4 } }, pi = {} },
        }""")
        how = ns.Community.RemoveOwn(ns.COMMUNITY, ns.COMMUNITY_SOURCES, ns.COMMUNITY_CAP,
                                     "mineminemine", self.exports_table(lua, 9, MINE.replace("^5\n", "^9\n")),
                                     drops)
        self.assertEqual(how, "estimate")
        after = self.community(lua, ns)
        self.assertEqual(after[3814]["k"], 30)
        self.assertEqual(after[3814]["i"], {5569: (9, 9)})

    def test_parse_export_matches_python(self):
        lua, ns = self.load(OTHER)
        install, seq, mobs = ns.Community.ParseExport(OTHER)
        self.assertEqual((install, seq), ("otherotherot", 2))
        self.assertEqual(mobs[3812].k, 40)
        self.assertEqual((mobs[3812].i[3010].d, mobs[3812].i[3010].q), (25, 26))
        self.assertIsNone(ns.Community.ParseExport("GoldScout-export 1\n3812^1^0"))


if __name__ == "__main__":
    unittest.main()


LEARN_STUBS = """
Enum = { LootSlotType = { Item = 1 } }
local ns = ...
ns.Plain = function(v) return v end
ns.On = function() end
ns.handlers = {}
ns.Listen = function(name, fn) ns.handlers[name] = fn end
ns.Fire = function() end
ns.Debounce = function() end
"""


@unittest.skipIf(lua51 is None, "lupa is not installed")
class SnapshotLuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        load = self.lua.execute("return loadstring(...)", LEARN_STUBS)
        load(self.ns)
        for name in ("Community.lua", "Learn.lua"):
            chunk = self.lua.execute("return loadstring(...)", (ROOT / "GoldScout" / name).read_text(encoding="utf-8"))
            chunk("GoldScout", self.ns)
        self.ns.COMMUNITY = self.lua.table()
        self.ns.db = self.lua.eval("""{
          settings = { learnDrops = true },
          drops = {
            [3814] = { k = 7, p = 0, c = 7, m = 1440, sx = 0.85, sy = 2.16, lmin = 20, lmax = 21,
                       n = "Spined|Crawler", i = { [5569] = { d = 4, q = 4 }, [2674] = { d = 9, q = 9 } }, pi = {} },
            [3812] = { k = 11, p = 0, c = 11, m = 1440, sx = 1.29, sy = 3.28, lmin = 19, lmax = 20,
                       n = "Clattering Crawler", i = { [3010] = { d = 7, q = 7 } }, pi = {} },
          },
        }""")
        self.ns.handlers["DB_READY"]()

    def test_snapshot_is_valid_and_stable(self):
        learn = self.ns.Learn
        text, count = learn.ExportString(learn)
        self.assertEqual(count, 2)
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.install_id, self.ns.db.installID)
        self.assertEqual(result.seq, 1)
        self.assertEqual([m.npc for m in result.mobs], [3812, 3814])  # sorted
        self.assertIn("^Spined Crawler^", text)                      # unsafe | removed
        self.assertIn("2674:7:9", text)                               # 9 drops in 7 kills clamped
        again, _ = learn.Snapshot(learn)
        self.assertEqual(again, text)                                 # no change, same snapshot
        self.ns.db.drops[3812].k = 12
        newer, _ = learn.Snapshot(learn)
        self.assertEqual(submission.parse(newer).seq, 2)

    def test_snapshot_carries_names_and_crafted_items(self):
        self.ns.db.names["items"][3010] = "Crawler Meat"
        self.ns.db.names["items"][5569] = "Pattern: Hillman's Cloak, Belt"
        self.ns.db.names.maps[1440] = "Ashenvale"
        self.ns.db.crafted[2996] = True
        self.ns.db.names.meta[3010] = "1:7:1"
        learn = self.ns.Learn
        text, count = learn.ExportString(learn)
        self.assertEqual(count, 2)
        self.assertTrue(text.startswith("GoldScout-export 4^"))
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.item_meta, {3010: (1, 7, True)})
        self.assertEqual(result.item_names, {3010: "Crawler Meat", 5569: "Pattern: Hillman's Cloak, Belt"})
        self.assertEqual(result.map_names, {1440: "Ashenvale"})
        self.assertEqual(result.crafted, {2996})
        # The client's own parser skips the @ lines and still reads both mobs.
        install, seq, mobs = self.ns.Community.ParseExport(text)
        self.assertEqual((install, seq), (self.ns.db.installID, result.seq))
        self.assertEqual(sorted(mobs.keys()), [3812, 3814])

    def test_old_snapshots_are_pruned_except_the_included_one(self):
        learn = self.ns.Learn
        learn.Snapshot(learn)
        sources = self.lua.table()
        sources[self.ns.db.installID] = 1
        self.ns.COMMUNITY_SOURCES = sources
        for kills in range(13, 40):
            self.ns.db.drops[3812].k = kills
            learn.Snapshot(learn)
        kept = sorted(self.ns.db.exports.list.keys())
        self.assertIn(1, kept)                    # what the community data includes
        self.assertEqual(len(kept), 1 + 10)       # plus the ten newest
        self.assertEqual(max(kept), self.ns.db.exports.seq)


# A fake game: loot window, units and timers, driven from the tests.
GAME_STUBS = """
Enum = { LootSlotType = { Item = 1 } }
local ns = ...
ns.Plain = function(v) return v end
ns.events, ns.handlers, ns.fired = {}, {}, {}
ns.On = function(name, fn) ns.events[name] = fn end
ns.Listen = function(name, fn) ns.handlers[name] = fn end
ns.Fire = function(name, ...) ns.fired[#ns.fired + 1] = name end
ns.Debounce = function() end
ns.SKINNING = { { leather = 2318, hide = 783 } }
ns.HERBS = { { id = 2447 } }
ns.ORES = { { id = 2770, stone = 2835 } }
GAME = { now = 100, loot = {}, units = {}, inGroup = false }
strsplit = function(sep, text)
  local parts = {}
  for part in (text .. sep):gmatch("(.-)%" .. sep) do parts[#parts + 1] = part end
  return unpack(parts)
end
GetTime = function() return GAME.now end
C_Timer = { After = function(_, fn) fn() end }
IsInGroup = function() return GAME.inGroup end
IsFishingLoot = function() return false end
GetNumLootItems = function() return #GAME.loot end
GetLootSlotType = function() return 1 end
GetLootSlotLink = function(slot) return "|cffffffff|Hitem:" .. GAME.loot[slot].item .. "::|h[Thing]|h|r" end
GetLootSlotInfo = function(slot) return nil, nil, 1 end
GetLootSourceInfo = function(slot) return GAME.loot[slot].guid, 1 end
UnitGUID = function(unit) return GAME.units[unit] and GAME.units[unit].guid end
UnitIsDead = function(unit) return GAME.units[unit] and GAME.units[unit].dead end
UnitIsTapDenied = function(unit) return GAME.units[unit] and GAME.units[unit].tapDenied or false end
UnitName = function() return "Ashenvale Bear" end
UnitLevel = function() return 22 end
"""

BEAR = "Creature-0-1-2-3-3809-0000000001"
BEAR2 = "Creature-0-1-2-3-3809-0000000002"


@unittest.skipIf(lua51 is None, "lupa is not installed")
class LootCountingLuaTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.lua.execute("return loadstring(...)", GAME_STUBS)(self.ns)
        for name in ("Community.lua", "Learn.lua"):
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)
        self.ns.COMMUNITY = self.lua.table()
        self.ns.db = self.lua.eval("{ settings = { learnDrops = true }, drops = {} }")
        self.ns.handlers["DB_READY"]()
        self.game = self.lua.globals().GAME

    def loot(self, guid, *items):
        self.game.loot = self.lua.table_from([self.lua.table_from({"item": i, "guid": guid}) for i in items])
        self.ns.events["LOOT_READY"]()
        for slot in range(1, len(items) + 1):
            self.ns.events["LOOT_SLOT_CLEARED"](slot)
        self.ns.events["LOOT_CLOSED"]()

    def dies(self, guid, unit="target", tapDenied=False):
        self.game.units[unit] = self.lua.table_from({"guid": guid, "dead": True, "tapDenied": tapDenied})
        self.ns.events["UNIT_HEALTH"](unit)

    def bear(self):
        entry = self.ns.db.drops[3809]
        if entry is None:
            return None, {}
        return entry.k, {item: stat.d for item, stat in entry.i.items()}

    def test_normal_loot_counts_kill_and_drops(self):
        self.loot(BEAR, 3730)
        self.assertEqual(self.bear(), (1, {3730: 1}))

    def test_skinning_after_cast_is_not_a_kill(self):
        self.loot(BEAR, 3730)
        self.ns.events["UNIT_SPELLCAST_SUCCEEDED"]("player", None, 8613)
        self.loot(BEAR2, 2318, 2934)   # skinned someone else's corpse, or after a /reload
        self.assertEqual(self.bear(), (1, {3730: 1}))

    def test_leather_only_window_is_a_skin_without_seeing_the_cast(self):
        self.game.now = 500
        self.loot(BEAR, 783)
        self.assertEqual(self.bear(), (None, {}))

    def test_mining_or_herbing_a_corpse_is_not_a_kill(self):
        self.loot(BEAR, 3730)
        for spell, item in ((2575, 2770), (2366, 2447)):   # Mining, Herb Gathering
            self.game.now += 10
            self.ns.events["UNIT_SPELLCAST_SUCCEEDED"]("player", None, spell)
            self.loot(BEAR2, item, 3730)   # even with something else in the window
        self.assertEqual(self.bear(), (1, {3730: 1}))

    def test_ore_or_herb_only_window_is_gathering_without_the_cast(self):
        self.game.now = 500
        self.loot(BEAR, 2770, 2835)
        self.loot(BEAR2, 2447)
        self.assertEqual(self.bear(), (None, {}))

    def test_other_casts_dont_count_as_gathering(self):
        self.ns.events["UNIT_SPELLCAST_SUCCEEDED"]("player", None, 1752)   # Sinister Strike
        self.loot(BEAR, 3730)
        self.assertEqual(self.bear(), (1, {3730: 1}))

    def test_corpse_without_loot_counts_the_kill(self):
        self.lua.globals().CanLootUnit = lambda guid: False
        self.dies(BEAR)
        self.assertEqual(self.bear(), (1, {}))

    def test_lootable_corpse_counts_when_looted_not_at_death(self):
        self.lua.globals().CanLootUnit = lambda guid: True
        self.dies(BEAR)
        self.assertEqual(self.bear(), (None, {}))
        self.loot(BEAR, 3730)
        self.assertEqual(self.bear(), (1, {3730: 1}))

    def test_counted_at_death_then_looted_counts_once_with_drops(self):
        # Without CanLootUnit every solo kill counts at death.
        self.dies(BEAR)
        self.loot(BEAR, 3730, 3702)
        self.assertEqual(self.bear(), (1, {3730: 1, 3702: 1}))
        self.loot(BEAR, 3730)          # reopening doesn't count again
        self.assertEqual(self.bear(), (1, {3730: 1, 3702: 1}))

    def test_group_and_other_players_kills_are_not_counted_at_death(self):
        self.game.inGroup = True
        self.dies(BEAR)
        self.game.inGroup = False
        self.dies(BEAR2, tapDenied=True)
        self.assertEqual(self.bear(), (None, {}))

    def test_a_death_is_judged_once(self):
        self.dies(BEAR)
        self.dies(BEAR, unit="nameplate3")
        self.assertEqual(self.bear(), (1, {}))
