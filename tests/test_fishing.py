"""Fishing: what the addon records from each catch (zone, open water or which
fishing pool, skill, items, where), how it's exported, checked and merged into
the community data, and the Farm rows it makes."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import merge_data  # noqa: E402
import submission  # noqa: E402
import test_community_lua as community_tests  # noqa: E402
import test_engine_lua as engine_tests  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

BOBBER = "GameObject-0-1-2-3-35591-00000000%02d"
POOL = "GameObject-0-1-2-3-180683-00000000%02d"   # a kind of fishing pool
HEADER = "GoldScout-export 5^abcdefghijkl^3"

FISHING_STUBS = """
GAME.fishing, GAME.map, GAME.x, GAME.y, GAME.skill = true, 1413, 0.42, 0.67, 120
IsFishingLoot = function() return GAME.fishing end
C_Map = {
  GetBestMapForUnit = function() return GAME.map end,
  GetPlayerMapPosition = function() return { GetXY = function() return GAME.x, GAME.y end } end,
  GetMapInfo = function(id) return { name = "Zone " .. id } end,
}
local ns = ...
ns.SKILL = { FISHING = 356 }
ns.Professions = { Skills = function() return { [356] = { rank = GAME.skill } } end }
"""


@unittest.skipIf(lua51 is None, "lupa is not installed")
class CatchTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.lua.execute("return loadstring(...)", community_tests.GAME_STUBS)(self.ns)
        self.lua.execute("return loadstring(...)", FISHING_STUBS)(self.ns)
        for name in ("Community.lua", "Learn.lua"):
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)
        self.ns.COMMUNITY = self.lua.table()
        self.ns.db = self.lua.eval("{ settings = { learnDrops = true }, drops = {} }")
        self.ns.handlers["DB_READY"]()
        self.game = self.lua.globals().GAME

    def catch(self, guid, *items):
        self.game.loot = self.lua.table_from([self.lua.table_from({"item": i, "guid": guid}) for i in items])
        self.ns.events["LOOT_READY"]()
        self.ns.events["LOOT_OPENED"]()          # both fire for one window: one catch
        for slot in range(1, len(items) + 1):
            self.ns.events["LOOT_SLOT_CLEARED"](slot)
        self.ns.events["LOOT_CLOSED"]()

    def spot(self, spot, map_id=1413):
        zone = self.ns.db.fish[map_id]
        entry = zone and zone[spot]
        if entry is None:
            return None
        return (entry.n, entry.s, {item: (stat.d, stat.q) for item, stat in entry.i.items()}, dict(entry.a.items()))

    def test_open_water_and_pools_are_separate_spots(self):
        self.catch(BOBBER % 1, 6303)
        self.game.skill = 95
        self.catch(BOBBER % 2, 6303, 6303)            # two slots of one item: once, quantity 2
        self.catch(POOL % 3, 6358)
        cell = 13 * 20 + 8                            # x 0.42, y 0.67 on a 20x20 grid
        self.assertEqual(self.spot(0), (2, 95, {6303: (2, 3)}, {cell: 2}))
        self.assertEqual(self.spot(180683), (1, 95, {6358: (1, 1)}, {cell: 1}))
        self.assertEqual(self.ns.db.drops[35591], None)       # not a mob
        self.assertEqual(self.ns.db.names.maps[1413], "Zone 1413")
        self.assertEqual(list(self.ns.fired.values()).count("LOOT_ACTION"), 3)

    def test_each_zone_has_its_own_spots(self):
        self.catch(BOBBER % 1, 6303)
        self.game.map = 1440
        self.catch(BOBBER % 2, 6291)
        self.assertEqual(self.spot(0)[2], {6303: (1, 1)})
        self.assertEqual(self.spot(0, 1440)[2], {6291: (1, 1)})

    def test_nothing_is_recorded_with_learning_off(self):
        self.ns.db.settings.learnDrops = False
        self.catch(BOBBER % 1, 6303)
        self.assertIsNone(self.spot(0))
        self.assertIn("LOOT_ACTION", list(self.ns.fired.values()))   # a running hunt still counts it

    def test_fishing_only_export_is_valid(self):
        self.catch(BOBBER % 1, 6303)
        self.catch(POOL % 2, 6358, 6358)
        learn = self.ns.Learn
        text, mobs, spots = learn.ExportString(learn)
        self.assertEqual((mobs, spots), (0, 2))
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual([(f.m, f.spot, f.n, f.s) for f in result.fishing], [(1413, 0, 1, 120), (1413, 180683, 1, 120)])
        self.assertEqual(result.fishing[1].i, {6358: (1, 2)})
        self.assertEqual(result.map_names, {1413: "Zone 1413"})
        self.assertEqual(submission.parse(result.text()).text(), result.text())   # rebuilds identically
        _, _, mobs_back, fishing = self.ns.Community.ParseExport(text)
        self.assertEqual(fishing[1413][180683].i[6358].q, 2)

    def test_long_sessions_export_within_the_limit(self):
        self.catch(BOBBER % 1, 6303)
        entry = self.ns.db.fish[1413][0]
        entry.n, entry.i[6303].d, entry.i[6303].q = 12000, 9000, 9000
        cell = list(entry.a.keys())[0]
        entry.a[cell] = 12000
        result = submission.parse(self.ns.Learn.ExportString(self.ns.Learn)[0])
        self.assertEqual(result.errors, [])
        self.assertEqual((result.fishing[0].n, result.fishing[0].i[6303], result.fishing[0].a[cell]),
                         (5000, (3750, 3750), 5000))

    def test_own_shared_fishing_is_taken_back_out(self):
        self.catch(BOBBER % 1, 6303)
        learn = self.ns.Learn
        learn.Snapshot(learn)
        sources = self.lua.table()
        sources[self.ns.db.installID] = self.ns.db.exports.seq
        community = self.lua.eval("{ [1413] = { [0] = { n = 11, i = { [6303] = { d = 9, q = 9 } }, a = {} } } }")
        self.ns.Community.RemoveOwn(self.ns.COMMUNITY, sources, 1000, self.ns.db.installID, self.ns.db.exports,
                                    self.ns.db.drops, community, self.ns.db.fish)
        self.assertEqual((community[1413][0].n, community[1413][0].i[6303].d), (10, 8))


class SubmissionTests(unittest.TestCase):
    def parse(self, *lines):
        return submission.parse("\n".join((HEADER,) + lines) + "\n")

    def test_fishing_lines(self):
        result = self.parse("@f^1413^0^20^75^6303:12:12,6291:5:5^335:10,336:8", "@f^1413^180683^6^0^6358:6:9^")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.fishing[0].a, {335: 10, 336: 8})
        self.assertEqual(result.fishing[1].s, 0)

    def test_bad_fishing_lines(self):
        for line, error in (
                ("@f^1413^0^20^75^6303:21:21^", "dropped 21 times in only 20"),
                ("@f^1413^0^20^75^^335:30", "more catch positions than catches"),
                ("@f^1413^0^20^999^^", "outside"),
                ("@f^0^0^20^75^^", "outside"),
                ("@f^1413^0^0^75^^", "outside"),
                ("@f^1413^0^20^75^6303:2:2", "7 fields"),
                ("@f^1413^0^20^75^^400:1", "cells 0-399")):
            with self.subTest(line):
                self.assertIn(error, " ".join(self.parse(line).errors))
        twice = self.parse("@f^1413^0^2^0^^", "@f^1413^0^3^0^^")
        self.assertIn("more than one fishing line", " ".join(twice.errors))
        old = submission.parse("GoldScout-export 4^abcdefghijkl^3\n@f^1413^0^2^0^^\n")
        self.assertIn("need a version 5 export", " ".join(old.errors))

    def test_an_export_needs_mobs_or_fishing(self):
        self.assertIn("no mobs or fishing", " ".join(self.parse("@l^0^enUS").errors))


class MergeTests(unittest.TestCase):
    def test_fishing_is_merged_per_zone_and_spot_with_a_cap(self):
        def player(install, *lines):
            return submission.parse("\n".join(["GoldScout-export 5^%s^1" % install] + list(lines)) + "\n")

        first = player("aaaaaaaaaaaa", "@f^1413^0^4000^90^6303:3000:3000^1:4000")
        second = player("bbbbbbbbbbbb", "@f^1413^0^10^60^6303:5:5,6291:5:5^1:10", "@f^1413^180683^3^0^6358:3:3^")
        self.assertEqual((first.errors, second.errors), ([], []))
        merged = merge_data.merge_fish([first.fishing, second.fishing], 1000)
        open_water = merged[(1413, 0)]
        self.assertEqual((open_water["n"], open_water["s"]), (1010, 60))
        self.assertEqual(dict(open_water["i"]), {6303: [755, 755], 6291: [5, 5]})   # 3000 scaled to 750
        self.assertEqual(dict(open_water["a"]), {1: 1010.0})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Data_Community.lua"
            merge_data.write_lua({}, 5, path, 2, fish=merged)
            text = path.read_text(encoding="utf-8")
        self.assertIn("  [1413] = {\n    [0] = { n = 1010, s = 60, i = { [6291] = { d = 5, q = 5 }, "
                      "[6303] = { d = 755, q = 755 } }, a = { [1] = 1010 } },\n  },", text)
        self.assertNotIn("[180683]", text)                      # 3 catches: under --min-attempts


@unittest.skipIf(lua51 is None, "lupa is not installed")
class FishRowTests(engine_tests.FarmRulesTests.__bases__[0]):
    setUp = engine_tests.FarmRulesTests.setUp
    run_lua = engine_tests.FarmRulesTests.run_lua
    run_file = engine_tests.FarmRulesTests.run_file
    item = engine_tests.FarmRulesTests.item
    rows = engine_tests.FarmRulesTests.rows

    def fishing(self, rank):
        self.run_lua("local ns = ...; ns.Professions.Skills = function() return { [356] = { rank = %d } } end"
                     % rank)

    def fished(self, spot, catches, items, skill=0, map_id=1413):
        table = self.lua.eval("{ n = %d, s = %d, i = {}, a = { [268] = %d } }" % (catches, skill, catches))
        for item_id, times in items.items():
            table.i[item_id] = self.lua.table_from({"d": times, "q": times})
        zone = self.ns.db.fish[map_id] or self.lua.table()
        zone[spot] = table
        self.ns.db.fish[map_id] = zone

    def test_fishing_rows_need_the_skill_or_other_profs(self):
        self.item(6303, price=400)
        self.fished(0, 50, {6303: 40})
        self.assertNotIn(("Fish", 6303), self.rows())
        self.settings.showOtherProfs = True
        self.assertTrue(self.rows()[("Fish", 6303)].needsProfession)
        self.settings.showOtherProfs = False
        self.fishing(150)
        self.assertIsNone(self.rows()[("Fish", 6303)].needsProfession)

    def test_value_per_catch_and_per_hour(self):
        self.fishing(150)
        self.item(6303, price=400)              # 380 after the AH cut
        self.item(6291, price=0, sell=10)       # no AH price: its vendor price
        self.fished(0, 98, {6303: 49, 6291: 49}, skill=75)
        row = self.rows()[("Fish", 6303)]
        each = (380 * 0.5 + 10 * 0.5) * 98 / 100     # cautious over 98 catches
        self.assertAlmostEqual(row.each, each)
        self.assertAlmostEqual(row.hour, each * 200)
        self.assertEqual((row.per, row.chance, row.seenTrials, row.source), ("catch", 0.5, 98, "Open water"))
        self.assertEqual(row.hunt.spots[1][1], 1413)
        self.assertEqual((row.hunt.spots[1][2], row.hunt.spots[1][3]), (42.5, 67.5))   # cell 268's center

    def test_the_catch_is_listed_most_common_first(self):
        # A sort rule that broke ties wrongly made Lua's sort fail now and then
        # ("attempt to index local 'b'"), depending on the order pairs() gave.
        self.fishing(150)
        items = {6000 + i: (i * 7) % 23 + 1 for i in range(40)}      # mixed rates, some tied
        for item_id in items:
            self.item(item_id, price=100)
        self.fished(0, 1000, items)
        for _ in range(20):
            fish = [row for key, row in self.rows().items() if key[0] == "Fish"]
            self.assertEqual(len(fish), 1)
            catch = fish[0].catch
            order = [(catch[i].rate, catch[i].item) for i in range(1, len(catch) + 1)]
            self.assertEqual(order, sorted(order, key=lambda pair: (-pair[0], pair[1])))
            self.assertEqual(len(order), 40)

    def test_pools_are_their_own_rows_at_half_the_pace(self):
        self.fishing(150)
        self.item(6358, price=1000)
        self.fished(180683, 10, {6358: 10})
        row = self.rows()[("Fish", 6358)]
        self.assertEqual(row.source, "Fishing pool")
        self.assertAlmostEqual(row.hour, row.each * 100)

    def test_too_little_skill_is_marked(self):
        self.fishing(100)
        self.item(6359, price=1000)
        self.fished(0, 10, {6359: 10}, skill=205, map_id=1440)
        self.assertTrue(self.rows()[("Fish", 6359)].needsProfession)

    def test_community_and_own_catches_add_up(self):
        self.fishing(150)
        self.item(6303, price=400)
        self.fished(0, 10, {6303: 5})
        self.ns.COMMUNITY_FISH = self.lua.eval("{ [1413] = { [0] = { n = 30, i = { [6303] = { d = 25, q = 25 } } } } }")
        row = self.rows()[("Fish", 6303)]
        self.assertEqual((row.seenTrials, row.chance), (40, 0.75))


if __name__ == "__main__":
    unittest.main()
