"""Tests for the companion's SavedVariables reader and export builder."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))

import savedvars  # noqa: E402
import submission  # noqa: E402

# Shaped like a real GoldScout.lua, with the quirks WoW writes: array index
# comments, escapes, nested tables, booleans and a second variable.
SAVED = r'''
GoldScoutDB = {
["settings"] = {
["autoScan"] = true,
["killsPerHour"] = 70,
},
["hunts"] = {
{
["item"] = 3685,
["label"] = "Say \"hi\"\\ok",
}, -- [1]
},
["drops"] = {
[3812] = {
["lmin"] = 19,
["p"] = 0,
["c"] = 11,
["i"] = {
[3010] = {
["q"] = 7,
["d"] = 7,
},
[2674] = {
["q"] = 4,
["d"] = 4,
},
},
["k"] = 11,
["sy"] = 3.287432551383972,
["sx"] = 1.297431349754334,
["m"] = 1440,
["lmax"] = 20,
["pi"] = {
},
["n"] = "Clattering Crawler",
},
[1234] = {
["p"] = 4,
["k"] = 0,
["i"] = {
},
["pi"] = {
[16882] = {
["q"] = 1,
["d"] = 9,
},
},
["n"] = "Bad|Name: \"x\"",
},
},
}
GoldScoutCharDB = nil
'''


class LuaReaderTests(unittest.TestCase):
    def test_parses_saved_variables(self):
        variables = savedvars.parse_saved_variables(SAVED)
        db = variables["GoldScoutDB"]
        self.assertIs(db["settings"]["autoScan"], True)
        self.assertEqual(db["hunts"][1]["label"], 'Say "hi"\\ok')
        self.assertEqual(db["drops"][3812]["i"][3010], {"q": 7, "d": 7})
        self.assertAlmostEqual(db["drops"][3812]["sx"], 1.297431349754334)
        self.assertIsNone(variables["GoldScoutCharDB"])

    def test_decimal_escapes_are_utf8(self):
        variables = savedvars.parse_saved_variables('X = { ["n"] = "Caf\\195\\169", }')
        self.assertEqual(variables["X"]["n"], "Café")

    def test_rejects_code(self):
        with self.assertRaises(savedvars.LuaError):
            savedvars.parse_saved_variables("X = os.execute('calc')")


class ExportTests(unittest.TestCase):
    def mobs(self, *tables):
        return savedvars.combine_drops(tables)

    def test_export_matches_game_format_and_validates(self):
        drops = savedvars.parse_saved_variables(SAVED)["GoldScoutDB"]["drops"]
        text = savedvars.export_text(self.mobs(drops))
        self.assertIn("3812^11^0^19^20^1440^0.1179^0.2989^11^Clattering Crawler^2674:4:4,3010:7:7^", text)
        result = submission.parse(text)
        self.assertEqual(result.errors, [])

    def test_cleans_impossible_counts_and_names(self):
        drops = savedvars.parse_saved_variables(SAVED)["GoldScoutDB"]["drops"]
        line = [l for l in savedvars.export_text(self.mobs(drops)).splitlines() if l.startswith("1234^")][0]
        self.assertIn("^Bad Name x^", line)       # unsafe characters dropped
        self.assertTrue(line.endswith("^16882:4:4"))  # 9 drops in 4 picks clamped to 4

    def test_combines_accounts(self):
        drops = savedvars.parse_saved_variables(SAVED)["GoldScoutDB"]["drops"]
        mobs = self.mobs(drops, drops)
        self.assertEqual(mobs[3812]["k"], 22)
        self.assertEqual(mobs[3812]["i"][3010], (14, 14))
        self.assertEqual(mobs[3812]["c"], 22)

    def test_finds_saved_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            forever = Path(tmp) / "World of Warcraft" / "_forever_"
            saved = forever / "WTF" / "Account" / "ACCOUNT1" / "SavedVariables"
            saved.mkdir(parents=True)
            (saved / "GoldScout.lua").write_text(SAVED, encoding="utf-8")
            self.assertEqual(savedvars.normalize_wow_folder(Path(tmp) / "World of Warcraft"), forever)
            self.assertEqual(savedvars.normalize_wow_folder(forever / "WTF" / "Account"), forever)
            self.assertIsNone(savedvars.normalize_wow_folder(Path(tmp)))
            self.assertEqual(len(savedvars.saved_variables_files(forever)), 1)
            self.assertIn(3812, savedvars.read_drops(savedvars.saved_variables_files(forever)[0]))


if __name__ == "__main__":
    unittest.main()
