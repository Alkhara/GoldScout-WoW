#!/usr/bin/env python3
"""GoldScout's translations: what needs translating, and what's missing.

  python tools/l10n.py keys              every English text the addon looks up
  python tools/l10n.py missing deDE      texts deDE doesn't translate yet
  python tools/l10n.py check             every Locale_*.lua: no unknown or broken entries

The addon looks text up as L["English text"] (GoldScout/Locale.lua). Each
GoldScout/Locale_<locale>.lua file holds one language as
    ["English text"] = "translation",
lines. A translation must keep the English text's placeholders (%s, %d, %g,
%%; "%1$s" style positions may reorder them), |c colour codes and \\n breaks.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADDON = ROOT / "GoldScout"
LOCALES = ("deDE", "frFR", "koKR", "zhTW")
LIT = r'"(?:[^"\\\n]|\\.)*"'
LOOKUP = re.compile(r"\bL\[(" + LIT + r"(?:\s*\.\.\s*" + LIT + r")*)\]")
ENTRY = re.compile(r'^\s*\[(' + LIT + r')\]\s*=\s*(' + LIT + r'),\s*$')
PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-+ #0]*\d*(?:\.\d+)?([sdgfx%])")

# Texts the addon looks up from a variable (L[row.kind], L[faction], ...).
DYNAMIC = [
    # Farm kinds (Type column)
    "Drop", "Pickpocket", "Learned", "Market", "Cloth", "Herb", "Ore", "Skin", "Loot",
    # Per-what words
    "kill", "pick", "node", "skin", "item", "try",
    # Factions and rulesets (auction house names: "%s %s" = ruleset, faction)
    "Alliance", "Horde", "Blackwater", "faction", "PvP", "Normal", "Roleplay", "Roleplay PvP", "%s %s",
]


def unquote(literal):
    """A Lua double-quoted literal's text, escapes kept as written (\\n stays \\n)."""
    return literal[1:-1]


def keys():
    """Every English text, in first-seen order."""
    found = {}
    for path in sorted(ADDON.glob("*.lua")):
        if path.name.startswith("Locale"):
            continue
        for match in LOOKUP.finditer(path.read_text(encoding="utf-8")):
            text = "".join(unquote(s) for s in re.findall(LIT, match.group(1)))
            found.setdefault(text, path.name)
    for text in DYNAMIC:
        found.setdefault(text, "(dynamic)")
    return found


def entries(locale):
    """{English: translation} from GoldScout/Locale_<locale>.lua, plus problems."""
    path = ADDON / ("Locale_%s.lua" % locale)
    out, problems = {}, []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = ENTRY.match(line)
        if match:
            english, translated = unquote(match.group(1)), unquote(match.group(2))
            if english in out:
                problems.append("%s:%d duplicate entry %r" % (path.name, number, english[:50]))
            out[english] = translated
    return out, problems


def arguments(text):
    """The kind of each format argument in order ("%%" takes none), with
    "%2$s" positions placing a kind where it belongs; None if positions are
    mixed with plain placeholders, which string.format can't handle."""
    plain, numbered = [], {}
    for m in PLACEHOLDER.finditer(text):
        kind = m.group(1)
        if kind == "%":
            continue
        position = re.match(r"%(\d+)\$", m.group(0))
        if position:
            numbered[int(position.group(1))] = kind
        else:
            plain.append(kind)
    if numbered and plain:
        return None
    if numbered:
        return [numbered.get(i) for i in range(1, max(numbered) + 1)]
    return plain


def signature(text):
    """What a translation has to keep: each argument's kind in order, colour codes, line breaks."""
    return arguments(text), text.count("|c"), text.count("|r"), text.count("\\n")


# Text handed straight to something that shows it, without L[...]: SetText("..."),
# ns.Print("..."), print("..."), ShowTip(frame, "..."), AddLine("..."),
# AddDoubleLine("..."), also as ("..."):format(...).
DISPLAY = re.compile(r'(?:(?:SetText|ns\.Print|\bprint|ShowTip\(\s*[\w.]+\s*,|AddLine|AddDoubleLine)\(?\s*\(?'
                     r'|\b(?:title|label|tip|text)\s*=)\s*(' + LIT + r')')
WORD = re.compile(r"[A-Za-z]{2,}")


def bare_texts():
    """Player-facing English text that skips the translation table: (file, line, text)."""
    found = []
    for path in sorted(ADDON.glob("*.lua")):
        if path.name.startswith("Locale"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().startswith("--"):
                continue
            for match in DISPLAY.finditer(line):
                text = re.sub(r"\|c[0-9a-fA-F]{8}|\|r|%[-0-9.]*[sdg]", "", unquote(match.group(1)))
                if WORD.search(text) and "GoldScout" != text.strip(" :"):
                    found.append((path.name, number, unquote(match.group(1))))
    return found


def check():
    known = keys()
    problems = ["%s:%d shows text without L[...]: %r" % found for found in bare_texts()]
    for locale in LOCALES:
        translated, found = entries(locale)
        problems += found
        for english, text in translated.items():
            if english not in known:
                problems.append("%s: not used by the addon: %r" % (locale, english[:60]))
            elif signature(english) != signature(text):
                problems.append("%s: placeholders or codes differ: %r" % (locale, english[:60]))
    return problems


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    if command == "keys":
        for text, where in keys().items():
            print("%-14s %s" % (where, text))
    elif command == "missing":
        translated, _ = entries(sys.argv[2])
        for text in keys():
            if text not in translated:
                print(text)
    else:
        problems = check()
        for problem in problems:
            print(problem)
        counts = {locale: len(entries(locale)[0]) for locale in LOCALES}
        print("%d texts; translated: %s" % (len(keys()), ", ".join("%s %d" % item for item in counts.items())))
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
