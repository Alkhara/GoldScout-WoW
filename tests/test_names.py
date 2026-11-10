"""Mob, item and zone names across languages: exports say which language they
were written in (version 5), the shared data and website keep only English
names, and the addon shows each player names in their own language."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import submission  # noqa: E402
from test_site import V4  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None

V5 = V4.replace("export 4^", "export 5^") + "@l^0^enUS\n"
KOREAN = V5.replace("Ashenvale Bear", "잿빛 골짜기 곰").replace("@l^0^enUS", "@l^0^koKR")


class NewerFormatTests(unittest.TestCase):
    """An out-of-date companion shares exports from a newer GoldScout as they
    are (the server, always updated first, checks them) instead of holding a
    player's data back."""

    def test_recognises_newer_exports(self):
        self.assertFalse(submission.newer_format(V5))                      # known: checked here
        self.assertFalse(submission.newer_format(V4))
        self.assertTrue(submission.newer_format(V5.replace("export 5^", "export 6^")))
        self.assertTrue(submission.newer_format(V5 + "@z^1^something new\n"))
        self.assertFalse(submission.newer_format("not an export"))
        self.assertFalse(submission.newer_format(V5.replace("abcdefghijkl", "BAD")))   # a broken header isn't "newer"


class LanguageLineTests(unittest.TestCase):
    def test_version_five_says_its_language(self):
        result = submission.parse(V5)
        self.assertEqual((result.errors, result.version, result.locale), ([], 5, "enUS"))
        self.assertEqual(submission.parse(result.text()).text(), result.text())   # round trip

    def test_language_line_rules(self):
        self.assertTrue(submission.parse(V4 + "@l^0^enUS\n").errors)               # version 4 can't
        for bad in ("@l^1^enUS", "@l^0^english", "@l^0^EN", "@l^0^"):
            with self.subTest(bad):
                self.assertTrue(submission.parse(V5.replace("@l^0^enUS", bad)).errors)

    def test_shared_names_stay_english(self):
        english = submission.keep_english_names(submission.parse(V5))
        self.assertEqual(english.mobs[0].n, "Ashenvale Bear")
        self.assertEqual(english.item_names[3730], "Big Bear Meat")
        korean = submission.keep_english_names(submission.parse(KOREAN))
        self.assertEqual((korean.mobs[0].n, korean.item_names, korean.map_names), ("", {}, {}))
        self.assertEqual(korean.mobs[0].k, 20)                       # drop data still counts
        german = submission.keep_english_names(submission.parse(V5.replace("@l^0^enUS", "@l^0^deDE")))
        self.assertEqual(german.mobs[0].n, "")

    def test_older_exports_keep_latin_names_only(self):
        mixed = submission.keep_english_names(submission.parse(V4.replace("Ashenvale Bear", "잿빛 골짜기 곰")))
        self.assertEqual(mixed.mobs[0].n, "")
        self.assertEqual(mixed.mobs[1].n, "Laughing Sister & Co's")


@unittest.skipIf(lua51 is None, "lupa is not installed")
class MobNameTests(unittest.TestCase):
    def addon(self, locale, known=None):
        """Core.lua's ns.MobName with a game that knows the creatures in known {npcID: name}."""
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        lua.execute("GetLocale = function() return '%s' end" % locale)
        lua.execute("KNOWN = {}")
        for npc, name in (known or {}).items():
            lua.globals().KNOWN[npc] = name
        lua.execute("""
          C_TooltipInfo = { GetHyperlink = function(link)
            local id = tonumber(link:match("^unit:Creature%-0%-0%-0%-0%-(%d+)%-"))
            if KNOWN[id] then return { lines = { { leftText = KNOWN[id] } } } end
          end }
        """)
        ns = lua.table()
        for name in ("Locale.lua", "Locale_koKR.lua"):
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            lua.execute("return loadstring(...)", source)("GoldScout", ns)
        core = (ROOT / "GoldScout" / "Core.lua").read_text(encoding="utf-8")
        start = core.index("local mobNames = {}")
        end = core.index("function ns.ItemName")
        lua.execute("return loadstring(...)", "local ns = ...\nlocal L = ns.L\nns.Plain = function(v) return v end\n"
                    + core[start:end])(ns)
        return ns

    def test_the_game_names_mobs_in_your_language(self):
        ns = self.addon("koKR", {834: "코요테"})
        self.assertEqual(ns.MobName(834, None, "Coyote"), "코요테")

    def test_the_games_name_beats_a_name_recorded_in_another_language(self):
        # Recorded while the game was in English; now it runs in German.
        ns = self.addon("deDE", {833: "Kojotenrudelführer"})
        self.assertEqual(ns.MobName(833, "Coyote Packleader", None), "Kojotenrudelführer")
        # A creature the game can't name: the player's own recorded name.
        self.assertEqual(ns.MobName(4818, "Murloc Oracle", "Murloc"), "Murloc Oracle")

    def test_english_shared_names_only_for_english_players(self):
        self.assertEqual(self.addon("enUS").MobName(4818, None, "Murloc"), "Murloc")
        self.assertEqual(self.addon("enGB").MobName(4818, None, "Murloc"), "Murloc")
        self.assertEqual(self.addon("koKR").MobName(4818, None, "Murloc"), "몹 #4818")
        self.assertEqual(self.addon("enUS").MobName(4818, None, None), "Mob #4818")


if __name__ == "__main__":
    unittest.main()
