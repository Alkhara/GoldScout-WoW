"""GoldScout's translations: every language file only translates texts the
addon uses, keeps their placeholders in a usable order, and actually loads in
game (German and French run here; Korean and Chinese use %1$s positions,
which WoW's string.format supports and plain Lua 5.1 doesn't)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import l10n  # noqa: E402

try:
    from lupa import lua51
except ImportError:  # pragma: no cover
    lua51 = None


class CheckTests(unittest.TestCase):
    def test_every_language_file_is_valid(self):
        self.assertEqual(l10n.check(), [])

    def test_argument_order_is_checked(self):
        self.assertEqual(l10n.arguments("%d prices for the %s auction house"), ["d", "s"])
        self.assertEqual(l10n.arguments("%2$s 경매장 가격 %1$d개"), ["d", "s"])
        self.assertIsNone(l10n.arguments("%2$s and %s"))          # mixed: string.format can't do it
        self.assertEqual(l10n.arguments("5%% off %s"), ["s"])
        self.assertNotEqual(l10n.signature("%d %s"), l10n.signature("%s %d"))

    def test_finds_the_addons_texts(self):
        keys = l10n.keys()
        self.assertIn("Scan AH", keys)
        self.assertIn("Cleared saved prices for the %s auction house.", keys)
        self.assertIn("Learned", keys)            # looked up from a variable
        self.assertNotIn("Button", keys)          # a frame type, not text

    def test_toc_loads_the_language_files_first(self):
        toc = (ROOT / "GoldScout" / "GoldScout.toc").read_text(encoding="utf-8").split()
        files = [name for name in toc if name.endswith(".lua")]
        self.assertEqual(files[:5], ["Locale.lua"] + ["Locale_%s.lua" % locale for locale in l10n.LOCALES])


@unittest.skipIf(lua51 is None, "lupa is not installed")
class InGameTests(unittest.TestCase):
    def load(self, locale):
        lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        ns = lua.table()
        lua.execute("GetLocale = function() return '%s' end" % locale)
        for name in ["Locale.lua"] + ["Locale_%s.lua" % code for code in l10n.LOCALES]:
            source = (ROOT / "GoldScout" / name).read_text(encoding="utf-8")
            lua.execute("return loadstring(...)", source)("GoldScout", ns)
        return lua, ns

    def test_only_the_games_language_is_used(self):
        _, german = self.load("deDE")
        self.assertEqual(german.L["Scan AH"], "AH scannen")
        self.assertEqual(german.L["Not translated anywhere"], "Not translated anywhere")
        _, english = self.load("enUS")
        self.assertEqual(english.L["Scan AH"], "Scan AH")
        _, korean = self.load("koKR")
        self.assertEqual(korean.L["Scan AH"], "경매장 검색")

    def test_german_and_french_format(self):
        for locale in ("deDE", "frFR"):
            lua, ns = self.load(locale)
            fmt = lua.eval("function(text, ...) return text:format(...) end")
            translated, _ = l10n.entries(locale)
            for english in translated:
                kinds = l10n.arguments(english)
                if not kinds:
                    continue              # plain text, never formatted ("5% AH cut")
                values = [7 if kind in "dg" else "x" for kind in kinds]
                with self.subTest(locale=locale, text=english[:40]):
                    fmt(ns.L[english], *values)        # raises if a placeholder is broken


if __name__ == "__main__":
    unittest.main()
