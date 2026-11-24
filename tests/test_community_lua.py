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
        install, seq, mobs, _ = ns.Community.ParseExport(OTHER)
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
        self.ns.COMMUNITY_FISH = self.lua.table()   # not the shipped data
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
        text, count, _ = learn.ExportString(learn)
        self.assertEqual(count, 2)
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.install_id, self.ns.db.installID)
        self.assertEqual(result.seq, 1)
        self.assertEqual([m.npc for m in result.mobs], [3812, 3814])  # sorted
        self.assertIn("^Spined Crawler^", text)                      # unsafe | removed
        self.assertIn("2674:7:9", text)                               # 9 drops in 7 kills clamped
        again = learn.Snapshot(learn)[0]
        self.assertEqual(again, text)                                 # no change, same snapshot
        self.ns.db.drops[3812].k = 12
        newer = learn.Snapshot(learn)[0]
        self.assertEqual(submission.parse(newer).seq, 2)

    def test_kill_times_are_exported_and_valid(self):
        self.ns.db.drops[3812].t, self.ns.db.drops[3812].ts = 9, 540.4
        self.ns.db.drops[3814].t, self.ns.db.drops[3814].ts = 10, 600   # more than its 7 kills: clamped
        learn = self.ns.Learn
        text = learn.ExportString(learn)[0]
        self.assertIn("@t^3812^9:540\n", text)
        self.assertIn("@t^3814^7:420", text)
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual({mob.npc: (mob.t, mob.s) for mob in result.mobs}, {3812: (9, 540), 3814: (7, 420)})

    def test_recovery_secret_stays_out_of_exports(self):
        learn = self.ns.Learn
        self.assertIsNone(self.ns.db.recoverySecret)        # made at the first export, not at login
        text = learn.ExportString(learn)[0]
        secret = self.ns.db.recoverySecret
        self.assertRegex(secret, r"^[a-z0-9]{32}$")
        self.assertNotEqual(secret[:12], self.ns.db.installID)
        self.assertNotIn(secret, text)
        self.ns.db.drops[3812].k = 12
        self.assertNotIn(secret, learn.Snapshot(learn)[0])
        self.assertEqual(self.ns.db.recoverySecret, secret)  # kept for good

    def test_a_negative_zero_count_exports_as_zero(self):
        # One player's saved data had every pickpocket count as -0, which Lua writes as "-0".
        self.lua.execute("for _, entry in pairs(...) do entry.p = -0.0 end", self.ns.db.drops)
        learn = self.ns.Learn
        text = learn.ExportString(learn)[0]
        self.assertNotIn("^-0^", text)
        self.assertEqual(submission.parse(text).errors, [])

    def test_snapshot_carries_names_and_crafted_items(self):
        self.ns.db.names["items"][3010] = "Crawler Meat"
        self.ns.db.names["items"][5569] = "Pattern: Hillman's Cloak, Belt"
        self.ns.db.names.maps[1440] = "Ashenvale"
        self.ns.db.crafted[2996] = True
        self.ns.db.names.meta[3010] = "1:7:1"
        learn = self.ns.Learn
        text, count, _ = learn.ExportString(learn)
        self.assertEqual(count, 2)
        self.assertTrue(text.startswith("GoldScout-export 7^"))   # no old companion here
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.item_meta, {3010: (1, 7, True)})
        self.assertEqual(result.item_names, {3010: "Crawler Meat", 5569: "Pattern: Hillman's Cloak, Belt"})
        self.assertEqual(result.map_names, {1440: "Ashenvale"})
        self.assertEqual(result.crafted, {2996})
        # The client's own parser skips the @ lines and still reads both mobs.
        install, seq, mobs, _ = self.ns.Community.ParseExport(text)
        self.assertEqual((install, seq), (self.ns.db.installID, result.seq))
        self.assertEqual(sorted(mobs.keys()), [3812, 3814])

    def test_snapshot_writes_other_languages_typography_plainly(self):
        # French no-break spaces, curly apostrophes and guillemets; Chinese full-width punctuation. Before, an
        # older companion refused the whole export over one of them.
        self.ns.db.drops[3812].n = "Ours d\u2019Orneval"
        self.ns.db.names["items"][3010] = "Patron\u00a0: Cape \u00ab\u00a0Rouge\u00a0\u00bb"
        self.ns.db.names.maps[1440] = "\u517b\u6b96\u573a\uff1a\u6d4b\u8bd5"
        learn = self.ns.Learn
        text, _, _ = learn.ExportString(learn)
        self.assertIn("^Ours d'Orneval^", text)
        self.assertIn("@i^3010^Patron : Cape ' Rouge '\n", text)
        self.assertIn("@m^1440^\u517b\u6b96\u573a:\u6d4b\u8bd5\n", text)
        self.assertEqual(submission.parse(text).errors, [])

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
        self.ns.COMMUNITY_FISH = self.lua.table()   # not the shipped data
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

    def open_window(self, guid, *items, take=()):
        """Opens a corpse's loot window, takes only the slots in take (from 1), and closes it."""
        self.game.loot = self.lua.table_from([self.lua.table_from({"item": i, "guid": guid}) for i in items])
        self.ns.events["LOOT_READY"]()
        for slot in take:
            self.ns.events["LOOT_SLOT_CLEARED"](slot)
        self.ns.events["LOOT_CLOSED"]()

    def test_loot_left_on_the_corpse_still_counts(self):
        # Full bags (or junk not worth taking): what dropped counts, taken or not.
        self.open_window(BEAR, 3730, 2940, take=(1,))
        self.open_window(BEAR2, 3730, 2940)
        self.assertEqual(self.bear(), (2, {3730: 2, 2940: 2}))

    def test_coming_back_for_left_loot_doesnt_count_twice(self):
        self.open_window(BEAR, 3730, 2940)
        self.open_window(BEAR, 3730, 2940, take=(1, 2))   # bags emptied, back to the corpse
        self.assertEqual(self.bear(), (1, {3730: 1, 2940: 1}))

    def test_an_item_filling_two_slots_is_one_drop(self):
        self.open_window(BEAR, 3730, 3730, take=(1, 2))
        stat = self.ns.db.drops[3809].i[3730]
        self.assertEqual((stat.d, stat.q), (1, 2))

    def test_the_hunt_hears_only_what_you_take(self):
        # The hunt panel's earnings and drop count are what reached your bags.
        self.open_window(BEAR, 3730, 2940, take=(2,))
        fired = list(self.ns.fired.values())
        self.assertEqual((fired.count("LOOT_GAINED"), fired.count("LOOT_DROP")), (1, 1))

    # Kill times: how long from one solo kill to the next, scaled to the pace on mobs of your own level.
    def kill(self, n, after=0):
        self.game.now += after
        guid = "Creature-0-1-2-3-3809-00000001%02d" % n
        self.game.units["target"] = self.lua.table_from({"guid": guid, "dead": True})   # a level 22 bear
        self.loot(guid, 3730)

    def pace(self):
        entry = self.ns.db.drops[3809]
        return entry.t, entry.ts

    def test_kills_are_timed_from_the_kill_before(self):
        self.kill(1)                          # the first kill has nothing before it
        self.assertEqual(self.pace(), (None, None))
        self.kill(2, after=30)
        self.kill(3, after=45)
        self.assertEqual(self.pace(), (2, 75))
        self.kill(4, after=181)               # a break: not timed
        self.kill(5, after=20)
        self.assertEqual(self.pace(), (3, 95))
        self.assertEqual(self.bear()[0], 5)

    def test_kill_times_are_scaled_to_your_own_level(self):
        # Ten levels above the bears you kill twice as fast: each kill counts as twice as long at your level.
        self.lua.execute("UnitLevel = function(unit) return unit == 'player' and 32 or 22 end")
        self.kill(1)
        self.kill(2, after=30)
        self.assertEqual(self.pace(), (1, 60))

    def test_a_mob_without_a_level_isnt_timed(self):
        self.kill(1)
        self.game.now += 30
        self.game.units["target"] = None
        self.loot("Creature-0-1-2-3-4000-0000000001", 3730)   # not targeted: no level known
        self.assertEqual(self.ns.db.drops[4000].t, None)

    def test_group_and_dungeon_kills_arent_timed(self):
        self.kill(1)
        self.game.inGroup = True
        self.kill(2, after=30)
        self.game.inGroup = False
        self.lua.execute("IsInInstance = function() return true end")
        self.kill(3, after=30)
        self.lua.execute("IsInInstance = nil")
        self.kill(4, after=30)
        self.assertEqual(self.pace(), (1, 30))

    def test_a_kill_counted_at_death_is_timed_once(self):
        self.kill(1)
        self.game.now += 30
        self.dies(BEAR)                       # no CanLootUnit: counted at death
        self.loot(BEAR, 3730)                 # looting it after doesn't time it again
        self.assertEqual(self.pace(), (1, 30))

    # Pick Pocket, as rogues play it: often macroed with Cheap Shot or Ambush, at a mob that isn't the target.
    JUNKBOX, HIP_FLASK, HIDE = 16882, 5431, 3730

    def cast_pick(self, guid, spell_id=921, unit="mouseover", name="Ashenvale Bear", succeed=True):
        # The cast names its mob by name only; the mob is the unit with that name (a mouseover macro here).
        g = self.lua.globals()
        g.GetSpellInfo = lambda spell: "Pick Pocket" if spell in (921, 99921) else None
        g.UnitName = lambda u: (self.game.units[u].name or "Ashenvale Bear") if self.game.units[u] else None
        if unit:
            self.game.units[unit] = self.lua.table_from({"guid": guid, "dead": False, "name": "Ashenvale Bear"})
        self.ns.events["UNIT_SPELLCAST_SENT"]("player", name, "Cast-1", spell_id)
        if succeed:
            self.ns.events["UNIT_SPELLCAST_SUCCEEDED"]("player", "Cast-1", spell_id)

    def picks(self):
        entry = self.ns.db.drops[3809]
        return (entry.p, {item: stat.d for item, stat in entry.pi.items()}) if entry else (None, {})

    def test_a_pickpocket_window_from_a_mob_you_didnt_target_is_a_pickpocket(self):
        self.cast_pick(BEAR)
        self.loot(BEAR, self.JUNKBOX)                   # no target: a mouseover macro
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))
        self.assertEqual(self.bear(), (0, {}))
        self.game.now += 20
        self.loot(BEAR, self.HIDE)                      # its corpse later: its own loot, counted as a kill
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))

    def test_this_clients_own_pick_pocket_spell_id_counts_by_its_name(self):
        self.cast_pick(BEAR, spell_id=99921)
        self.loot(BEAR, self.JUNKBOX)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))

    def test_goldscout_never_listens_to_the_combat_log(self):
        # On Midnight-era clients only Blizzard's interface may register it: an add-on that does gets the
        # game's "blocked from an action only available to the Blizzard UI" warning at every load.
        for path in (ROOT / "GoldScout").rglob("*.lua"):
            self.assertNotIn("COMBAT_LOG_EVENT", path.read_text(encoding="utf-8"), path.name)

    def test_the_pick_is_the_unit_the_cast_names_not_just_the_target(self):
        wolf = "Creature-0-1-1-1-525-0000000002"
        self.game.units["target"] = self.lua.table_from({"guid": wolf, "dead": False, "name": "Mangy Wolf"})
        self.cast_pick(BEAR)
        self.game.units["target"] = None
        self.loot(BEAR, self.JUNKBOX)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))

    def test_a_cast_at_no_unit_you_can_see_records_nothing(self):
        self.cast_pick(BEAR, unit=None, name="Someone Else")
        self.game.now += 20
        self.loot(BEAR, self.HIDE)
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))

    # Inside an instance every mob's name and GUID is secret: the cast can't be tied to its mob.
    def cast_blind_pick(self):
        self.cast_pick(BEAR, unit=None, name=None)

    def test_inside_an_instance_the_window_right_after_a_pick_is_its_pockets(self):
        self.cast_blind_pick()
        self.loot(BEAR, self.JUNKBOX)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))
        self.assertEqual(self.bear(), (0, {}))
        self.game.now += 20
        self.loot(BEAR, self.HIDE)                      # its corpse later is a kill
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))

    def test_an_unplaced_pick_claims_only_the_window_right_after_it(self):
        self.cast_blind_pick()
        self.game.now += 2
        self.loot(BEAR, self.HIDE)
        self.assertEqual((self.bear(), self.picks()[0]), ((1, {self.HIDE: 1}), 0))

    def test_an_unplaced_pick_claims_one_window_once(self):
        self.cast_blind_pick()
        self.loot(BEAR, self.JUNKBOX)
        self.loot(BEAR2, self.HIDE)                     # the next window, still within the second, is a kill
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1}))
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))

    def test_an_unplaced_pick_never_claims_a_window_from_several_mobs(self):
        # Area loot from two corpses isn't a pickpocket window.
        self.cast_blind_pick()
        self.game.loot = self.lua.table_from([self.lua.table_from({"item": self.HIDE, "guid": BEAR}),
                                              self.lua.table_from({"item": self.HIDE, "guid": BEAR2})])
        self.ns.events["LOOT_READY"]()
        self.ns.events["LOOT_CLOSED"]()
        self.assertEqual((self.bear(), self.picks()[0]), ((2, {self.HIDE: 2}), 0))

    def test_an_untargeted_corpse_is_named_by_its_guid(self):
        g = self.lua.globals()
        g.UnitNameFromGUID = lambda guid: "Golem Lord Argelmach" if guid == BEAR else None
        self.loot(BEAR, self.HIDE)                      # no target: a group's kill
        entry = self.ns.db.drops[3809]
        self.assertEqual((entry.n, entry.lmin), ("Golem Lord Argelmach", None))

    def test_a_guid_lookup_that_fails_names_nothing(self):
        self.lua.execute("UnitNameFromGUID = function() error('secret') end")
        self.loot(BEAR, self.HIDE)
        self.assertEqual((self.bear(), self.ns.db.drops[3809].n), ((1, {self.HIDE: 1}), None))

    def test_a_pick_pocket_that_never_goes_off_records_nothing(self):
        self.cast_pick(BEAR, succeed=False)
        self.game.now += 20
        self.loot(BEAR, self.HIDE)
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))

    def test_other_casts_dont_count_as_pickpocketing(self):
        self.cast_pick(BEAR, spell_id=1833)
        self.loot(BEAR, self.HIDE)
        self.assertEqual((self.bear(), self.picks()[0]), ((1, {self.HIDE: 1}), 0))

    def test_a_corpse_whose_pockets_were_never_opened_isnt_recorded(self):
        # Cheap Shot closed the pickpocket window before it opened: its loot is on the corpse with the mob's own.
        self.cast_pick(BEAR)
        self.game.now += 20
        self.loot(BEAR, self.JUNKBOX, self.HIDE)
        self.assertEqual((self.bear(), self.picks()), ((None, {}), (None, {})))
        self.assertIn("LOOT_ACTION", list(self.ns.fired.values()))   # the hunt panel still counts the kill
        self.loot(BEAR, self.HIDE)                                    # and reopening it doesn't count it either
        self.assertEqual(self.bear(), (None, {}))

    def test_a_corpse_with_pickpocket_loot_left_in_it_isnt_recorded(self):
        self.cast_pick(BEAR)
        self.open_window(BEAR, self.JUNKBOX, self.HIP_FLASK, take=(1,))   # bags full: the flask stays
        self.game.now += 20
        self.loot(BEAR, self.HIP_FLASK, self.HIDE)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1, self.HIP_FLASK: 1}))
        self.assertEqual(self.bear(), (0, {}))

    def test_a_pickpocket_window_closed_untouched_counts_once(self):
        # It opens, Cheap Shot closes it, nothing taken: its loot counts as the pick, and its corpse not at all.
        self.cast_pick(BEAR)
        self.open_window(BEAR, self.JUNKBOX, self.HIP_FLASK)
        self.game.now += 20
        self.loot(BEAR, self.JUNKBOX, self.HIP_FLASK, self.HIDE)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1, self.HIP_FLASK: 1}))
        self.assertEqual(self.bear(), (0, {}))

    def test_reopening_the_pockets_untargeted_isnt_a_kill(self):
        # The second window has no fresh cast behind it and the mob isn't targeted; it still isn't counted twice.
        self.cast_pick(BEAR)
        self.open_window(BEAR, self.JUNKBOX, self.HIP_FLASK)
        self.open_window(BEAR, self.JUNKBOX, self.HIP_FLASK, take=(1, 2))
        self.game.now += 20
        self.loot(BEAR, self.HIDE)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1, self.HIP_FLASK: 1}))
        self.assertEqual(self.bear(), (0, {}))

    def test_a_corpse_whose_pockets_were_emptied_counts(self):
        self.cast_pick(BEAR)
        self.loot(BEAR, self.JUNKBOX)
        self.game.now += 20
        self.loot(BEAR, self.HIDE)
        self.assertEqual(self.bear(), (1, {self.HIDE: 1}))

    def test_the_old_targeted_pickpocket_still_counts_and_guards_its_corpse(self):
        self.game.units["target"] = self.lua.table_from({"guid": BEAR, "dead": False})
        self.open_window(BEAR, self.JUNKBOX, self.HIP_FLASK, take=(1,))
        self.game.units["target"] = self.lua.table_from({"guid": BEAR, "dead": True})
        self.loot(BEAR, self.HIP_FLASK, self.HIDE)
        self.assertEqual(self.picks(), (1, {self.JUNKBOX: 1, self.HIP_FLASK: 1}))
        self.assertEqual(self.bear(), (0, {}))

    def test_a_kill_counted_at_death_is_taken_back_when_its_corpse_is_mixed(self):
        # Without CanLootUnit every solo kill counts at death.
        self.cast_pick(BEAR)
        self.game.now += 20
        self.dies(BEAR)
        self.assertEqual(self.bear(), (1, {}))
        self.loot(BEAR, self.JUNKBOX, self.HIDE)
        self.assertEqual(self.bear(), (0, {}))

    def test_a_pick_cast_doesnt_make_its_corpse_a_pickpocket(self):
        # Killed within seconds of the cast, as your dead target: the corpse, not its pockets.
        self.cast_pick(BEAR)
        self.game.units["target"] = self.lua.table_from({"guid": BEAR, "dead": True})
        self.loot(BEAR, self.JUNKBOX, self.HIDE)
        self.assertEqual(self.picks(), (None, {}))
        self.assertEqual(self.bear(), (None, {}))   # pockets never emptied: not recorded

    def test_a_death_is_judged_once(self):
        self.dies(BEAR)
        self.dies(BEAR, unit="nameplate3")
        self.assertEqual(self.bear(), (1, {}))
