"""Optional error reports: what leaves the player's PC, and only when it should."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))

import error_reports as er  # noqa: E402
import savedvars  # noqa: E402

STACK = (
    "[string \"@Interface/AddOns/GoldScout/UI.lua\"]:812: in function 'Refresh'\n"
    "[string \"@Interface/AddOns/SomeOtherAddon/Core.lua\"]:5: in function <...>\n"
    "C:\\Program Files (x86)\\World of Warcraft\\_forever_\\Interface\\AddOns\\GoldScout\\Engine.lua:44: in function 'Farms'\n"
    "[C]: in function 'xpcall'"
)


class Account:
    def __init__(self, errors):
        self.errors = errors


class CleaningTests(unittest.TestCase):
    def test_messages_lose_folder_paths(self):
        windows = er.clean_message("C:\\Users\\Chris\\Games\\World of Warcraft\\_forever_\\Interface\\AddOns\\"
                                   "GoldScout\\UI.lua:12: attempt to index a nil value")
        self.assertEqual(windows, "GoldScout/UI.lua:12: attempt to index a nil value")
        mac = er.clean_message("/Users/chris/Applications/World of Warcraft/x.lua:3: oops")
        self.assertNotIn("chris", mac)

    def test_stacks_keep_only_goldscout_lines(self):
        stack = er.clean_stack(STACK)
        self.assertEqual(stack.splitlines(), ["GoldScout/UI.lua:812: in function 'Refresh'",
                                              "GoldScout/Engine.lua:44: in function 'Farms'"])
        self.assertNotIn("SomeOtherAddon", stack)
        self.assertNotIn("Program Files", stack)

    def test_one_error_as_sent(self):
        report = er.clean({"m": "Interface/AddOns/GoldScout/UI.lua:1: boom", "s": STACK, "n": 3, "t": 100,
                           "v": "v0.10.1"})
        self.assertEqual(set(report), {"m", "s", "n", "v"})                # no time, nothing else
        self.assertEqual((report["m"], report["n"], report["v"]), ("GoldScout/UI.lua:1: boom", 3, "v0.10.1"))
        self.assertNotIn("v", er.clean({"m": "x", "v": "not a version!"}))
        self.assertIsNone(er.clean({"m": ""}))
        self.assertEqual(er.clean({"m": "x", "n": -4})["n"], 1)

    def test_other_addons_errors_saved_by_old_versions_are_not_sent(self):
        # Before v0.11.1 each saved stack started with GoldScout's error handler.
        handler = "Interface/AddOns/GoldScout/Core.lua:319: in function <Interface/AddOns/GoldScout/Core.lua:318>\n"
        questie = {"m": "GetAuraDataByIndex(): Auras cannot be accessed when secret while tainted by 'Questie'",
                   "s": handler + "Interface/AddOns/Questie/Modules/Auras.lua:40: in function 'Scan'", "v": "v0.6.4"}
        self.assertIsNone(er.clean(questie))
        ours = dict(questie, s=handler + "Interface/AddOns/GoldScout/UI.lua:812: in function 'Refresh'")
        self.assertEqual(er.clean(ours)["s"], "GoldScout/UI.lua:812: in function 'Refresh'")
        fixed = dict(questie, s="Interface/AddOns/GoldScout/Core.lua:50: in function 'X'", v="v0.11.1")
        self.assertEqual(er.clean(fixed)["s"], "GoldScout/Core.lua:50: in function 'X'")   # a real Core.lua error

    def test_only_errors_newer_than_the_last_report(self):
        accounts = [Account([{"m": "old", "t": 50}, {"m": "new", "t": 150}]), Account([{"m": "newer", "t": 200}])]
        errors, newest = er.new_errors(accounts, since=100)
        self.assertEqual([e["m"] for e in errors], ["newer", "new"])       # newest first
        self.assertEqual(newest, 200)
        self.assertEqual(er.new_errors(accounts, since=200), ([], 200))
        many = [Account([{"m": "e%d" % i, "t": i} for i in range(1, 60)])]
        self.assertEqual(len(er.new_errors(many, since=0)[0]), er.MAX_ERRORS)

    def test_the_reporter_id_is_random(self):
        first, second = er.new_reporter_id(), er.new_reporter_id()
        self.assertRegex(first, r"^[0-9a-f]{16}$")
        self.assertNotEqual(first, second)


class SavedErrorsTests(unittest.TestCase):
    def test_reads_goldscouts_error_log(self):
        saved = ('GoldScoutDB = {\n["installID"] = "abcdefghijkl",\n["errors"] = {\n'
                 '{\n["m"] = "boom",\n["s"] = "stack",\n["n"] = 2,\n["t"] = 1800000000,\n["v"] = "v0.10.1",\n}, -- [1]\n'
                 '},\n}\n')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "_forever_" / "WTF" / "Account" / "A" / "SavedVariables"
            folder.mkdir(parents=True)
            (folder / "GoldScout.lua").write_text(saved, encoding="utf-8")
            account = savedvars.read_accounts(Path(tmp) / "_forever_")[0]
        self.assertEqual(len(account.errors), 1)
        self.assertEqual((account.errors[0]["m"], account.errors[0]["n"]), ("boom", 2))


if __name__ == "__main__":
    unittest.main()
