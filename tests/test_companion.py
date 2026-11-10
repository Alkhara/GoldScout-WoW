"""Tests for the companion's SavedVariables reader."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))

import savedvars  # noqa: E402
import submission  # noqa: E402

EXPORT = ("GoldScout-export 2^abcdefghijkl^4\n"
          "3812^11^0^19^20^1440^0.1179^0.2989^11^Clattering Crawler^2674:4:4,3010:7:7^")

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
["installID"] = "abcdefghijkl",
["exports"] = {
["seq"] = 4,
["list"] = {
[3] = "GoldScout-export 2^abcdefghijkl^3\n3812^5^0^19^20^1440^0.1179^0.2989^5^Clattering Crawler^3010:3:3^",
[4] = "GoldScout-export 2^abcdefghijkl^4\n3812^11^0^19^20^1440^0.1179^0.2989^11^Clattering Crawler^2674:4:4,3010:7:7^",
},
},
["drops"] = {
[3812] = {
["k"] = 11,
["p"] = 0,
["i"] = {
[3010] = {
["q"] = 7,
["d"] = 7,
},
},
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
        self.assertEqual(db["exports"]["list"][4], EXPORT)
        self.assertIsNone(variables["GoldScoutCharDB"])

    def test_decimal_escapes_are_utf8(self):
        variables = savedvars.parse_saved_variables('X = { ["n"] = "Caf\\195\\169", }')
        self.assertEqual(variables["X"]["n"], "Café")

    def test_rejects_code(self):
        with self.assertRaises(savedvars.LuaError):
            savedvars.parse_saved_variables("X = os.execute('calc')")


class AccountTests(unittest.TestCase):
    def make_install(self, tmp, saved_text, account="ACCOUNT1"):
        forever = Path(tmp) / "World of Warcraft" / "_forever_"
        folder = forever / "WTF" / "Account" / account / "SavedVariables"
        folder.mkdir(parents=True)
        (folder / "GoldScout.lua").write_text(saved_text, encoding="utf-8")
        return forever

    def test_reads_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            forever = self.make_install(tmp, SAVED)
            accounts = savedvars.read_accounts(forever)
            self.assertEqual(len(accounts), 1)
            account = accounts[0]
            self.assertEqual((account.name, account.install_id, account.seq), ("ACCOUNT1", "abcdefghijkl", 4))
            self.assertEqual(account.export, EXPORT)
            self.assertTrue(account.has_loot)
            self.assertEqual(submission.parse(account.export).errors, [])

    def test_old_addon_without_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            forever = self.make_install(tmp, 'GoldScoutDB = { ["drops"] = { [1] = { ["k"] = 3, }, }, }')
            account = savedvars.read_accounts(forever)[0]
            self.assertIsNone(account.export)
            self.assertTrue(account.has_loot)

    def test_region_is_the_most_recently_played(self):
        saved = (SAVED.replace("GoldScoutDB = {", 'GoldScoutDB = {\n["seenMarkets"] = { ["A-Horde"] = 100, '
                               '["B-Horde"] = 200 },\n["marketRegions"] = { ["A-Horde"] = "us", '
                               '["B-Horde"] = "eu", ["C-Horde"] = "mars" },', 1))
        with tempfile.TemporaryDirectory() as tmp:
            account = savedvars.read_accounts(self.make_install(tmp, saved))[0]
            self.assertEqual(account.region, "eu")
            account.market_regions = {}
            self.assertIsNone(account.region)   # an addon from before 0.9.0

    def test_finds_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            forever = self.make_install(tmp, SAVED)
            self.assertEqual(savedvars.normalize_wow_folder(Path(tmp) / "World of Warcraft"), forever)
            self.assertEqual(savedvars.normalize_wow_folder(forever / "WTF" / "Account"), forever)
            self.assertIsNone(savedvars.normalize_wow_folder(Path(tmp)))
            self.assertEqual(len(savedvars.saved_variables_files(forever)), 1)


class GameRunningTests(unittest.TestCase):
    """Update notifications wait while any WoW client is open."""

    def test_any_wow_client_counts(self):
        import system
        for name in ("wow.exe", "wowclassic.exe"):
            self.assertTrue(system.game_running({"explorer.exe", name}))
        self.assertFalse(system.game_running({"explorer.exe", "battle.net.exe", "wowup.exe"}))

    def test_mac_clients_count(self):
        import system
        names = system.parse_ps("/sbin/launchd\n/Applications/World of Warcraft/_forever_/World of Warcraft.app/"
                                "Contents/MacOS/World of Warcraft\n/Applications/Battle.net.app/Contents/MacOS/"
                                "Battle.net\n")
        self.assertIn("world of warcraft", names)
        self.assertTrue(system.game_running(names))
        self.assertTrue(system.game_running({"world of warcraft classic"}))
        self.assertFalse(system.game_running(system.parse_ps("/sbin/launchd\n/Applications/Battle.net.app/"
                                                             "Contents/MacOS/Battle.net\n")))

    def test_ps_failure_means_nothing_running(self):
        import system

        def broken(*args, **kwargs):
            raise OSError("no ps")
        self.assertEqual(system._ps_process_names(run=broken), set())

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_sees_this_process(self):
        import system
        names = system.running_process_names()
        self.assertIn(Path(sys.executable).name.lower(), names)
        self.assertTrue(all(name == name.lower() for name in names))


if __name__ == "__main__":
    unittest.main()
