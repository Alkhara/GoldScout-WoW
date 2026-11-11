"""Where mobs are looted, as squares of a 20x20 grid over the zone map: the
addon records them, version 5 exports carry them, the validator checks them,
and the merge adds them up per mob for the world-map hunting area."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import merge_data  # noqa: E402
import submission  # noqa: E402
from test_community_lua import BEAR, GAME_STUBS, LEARN_STUBS  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

MOB = "3809^20^0^21^22^1440^0.5400^0.5400^20^Ashenvale Bear^3730:8:8^"
V5 = "GoldScout-export 5^abcdefghijkl^3\n%s\n@a^3809^%s\n@l^0^enUS\n"


class AreaLineTests(unittest.TestCase):
    def test_cells_parse_and_round_trip(self):
        result = submission.parse(V5 % (MOB, "205:12,206:8"))
        self.assertEqual(result.errors, [])
        self.assertEqual(result.mobs[0].a, {205: 12, 206: 8})
        self.assertEqual(submission.parse(result.text()).text(), result.text())

    def test_bad_cells_are_rejected(self):
        for bad in ("400:1", "205:0", "205:1,205:2", "205", "a:1", ""):
            with self.subTest(bad):
                self.assertTrue(submission.parse(V5 % (MOB, bad)).errors)
        version4 = (V5 % (MOB, "205:1")).replace("export 5^", "export 4^").replace("@l^0^enUS\n", "")
        self.assertTrue(submission.parse(version4).errors)                  # version 5 only
        stray = (V5 % (MOB, "205:1")).replace("@a^3809^", "@a^1234^")
        self.assertTrue(submission.parse(stray).errors)                      # a mob not in the export

    def test_merge_adds_cells_on_the_mobs_map(self):
        first = submission.parse(V5 % (MOB, "205:12,206:8"))
        second = submission.parse((V5 % (MOB, "206:4,300:1")).replace("abcdefghijkl", "mnopqrstuvwx"))
        merged = merge_data.merge([first.mobs, second.mobs], 1000)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Data_Community.lua"
            merge_data.write_lua(merged, 1, path, 2)
            text = path.read_text(encoding="utf-8")
        self.assertIn("a = { [205] = 12, [206] = 12, [300] = 1 }", text)

    def test_one_player_cant_outweigh_the_rest(self):
        heavy = submission.parse(V5 % (MOB, "205:5000"))
        merged = merge_data.merge([heavy.mobs], 1000)
        self.assertEqual(merged[3809]["areas"][1440][205], 1000)


@unittest.skipIf(lua51 is None, "lupa is not installed")
class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.lua.execute("return loadstring(...)", GAME_STUBS)(self.ns)
        self.lua.execute("""
          POSITION = { map = 1440, x = 0.27, y = 0.51 }
          C_Map = {
            GetBestMapForUnit = function() return POSITION.map end,
            GetPlayerMapPosition = function() return { GetXY = function() return POSITION.x, POSITION.y end } end,
            GetMapInfo = function() return { name = "Ashenvale" } end,
          }
        """)
        for name in ("Community.lua", "Learn.lua"):
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            self.lua.execute("return loadstring(...)", source)("GoldScout", self.ns)
        self.ns.COMMUNITY = self.lua.table()
        self.ns.db = self.lua.eval("{ settings = { learnDrops = true }, drops = {} }")
        self.ns.handlers["DB_READY"]()
        self.game = self.lua.globals().GAME

    def loot(self, guid, x, y):
        position = self.lua.globals().POSITION
        position.x, position.y = x, y
        self.game.loot = self.lua.table_from([self.lua.table_from({"item": 3730, "guid": guid})])
        self.ns.events["LOOT_READY"]()
        self.ns.events["LOOT_SLOT_CLEARED"](1)
        self.ns.events["LOOT_CLOSED"]()

    def test_loot_spots_land_in_grid_squares(self):
        self.loot(BEAR, 0.27, 0.51)                       # row 10, column 5 -> 205
        self.loot(BEAR.replace("0001", "0002"), 0.28, 0.52)
        self.loot(BEAR.replace("0001", "0003"), 0.999, 0.999)   # the far corner -> 399
        area = self.ns.db.drops[3809].a
        self.assertEqual(dict(area.items()), {205: 2, 399: 1})


@unittest.skipIf(lua51 is None, "lupa is not installed")
class VersionFiveExportTests(unittest.TestCase):
    """GoldScout writes version 5 unless this player's own companion is too old for it."""

    def export(self, prices_data=None):
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        ns = lua.table()
        lua.execute("return loadstring(...)", LEARN_STUBS)(ns)
        if prices_data:
            lua.execute("GoldScoutPricesData = " + prices_data)
        for name in ("Community.lua", "Learn.lua"):
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            lua.execute("return loadstring(...)", source)("GoldScout", ns)
        ns.COMMUNITY = lua.table()
        ns.LOCALE = "deDE"
        ns.db = lua.eval("""{ settings = { learnDrops = true }, drops = {
          [3812] = { k = 11, p = 0, c = 11, m = 1440, sx = 1.29, sy = 3.28, lmin = 19, lmax = 20,
                     n = "Klappernder Kriecher", i = { [3010] = { d = 7, q = 7 } }, pi = {}, a = { [205] = 9, [206] = 2 } },
        } }""")
        ns.handlers["DB_READY"]()
        text = ns.Learn.ExportString(ns.Learn)[0]
        return ns, text

    def test_versions_follow_the_players_companion(self):
        cases = {
            None: 5,                                                         # no companion here, or prices off
            "{ markets = {} }": 4,                                           # a companion before 0.10.0
            '{ markets = {}, companion = "0.9.0" }': 4,
            '{ markets = {}, companion = "0.10.0" }': 5,
            '{ markets = {}, companion = "1.2.0" }': 5,
        }
        for prices_data, version in cases.items():
            with self.subTest(prices_data):
                _, text = self.export(prices_data)
                result = submission.parse(text)
                self.assertEqual((result.errors, result.version), ([], version))
                self.assertEqual("@a^" in text, version == 5)    # areas and language only in version 5

    def test_the_addons_version_5_export_is_valid(self):
        ns, text = self.export()
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertEqual((result.version, result.locale), (5, "deDE"))
        self.assertEqual(result.mobs[0].a, {205: 9, 206: 2})
        install, _, mobs, _ = ns.Community.ParseExport(text)         # the addon's own parser skips @ lines
        self.assertEqual(sorted(mobs.keys()), [3812])


if __name__ == "__main__":
    unittest.main()
