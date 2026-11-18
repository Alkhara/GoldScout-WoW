"""Written notes for the gold guides' farms: a few sentences on how to run each farm, written weekly by Claude
from the farm's fact sheet (tools/write_farm_notes.py) and kept in site/farm_notes.json.

A note may only use what the fact sheet says: the mob, the item, the zone, the mob's levels, map coordinates
where players loot it, and the mob's other drops. It never quotes prices, gold per hour or drop chances (the
live tables beside it show those, and they change daily), and it never describes how the game behaves (respawns,
patrols, elites ...), which nothing here can check. check() enforces that, both when a note is written and
every time the site builds: a note whose numbers or names no longer match the farm's current facts isn't shown
until the next weekly run rewrites it.
"""
import json
import re
from pathlib import Path

import data_pages

NOTES_FILE = Path(__file__).resolve().parent / "farm_notes.json"
MIN_WORDS, MAX_WORDS = 35, 130
OTHER_DROPS = 4             # the mob's other drops a fact sheet lists, most likely first
# Words of the guides and the add-on a note may name besides the farm's own names.
ALLOWED_NAMES = {"GoldScout", "Hunt", "Farm", "Drop", "Rates", "WoW", "Forever", "Blizzard", "Horde",
                 "Alliance", "I", "Skinning", "Herbalism", "Mining", "Fishing", "Pickpocket", "Pickpocketing",
                 "World", "Warcraft", "Auction", "House"}
# Claims about how the game behaves that no fact sheet can back.
FORBIDDEN = ("respawn", "patrol", "elite", "caster", "flee", "rare spawn", "quest", "dungeon", "raid",
             "instance", "boss", "aggro", "pull", "spawn rate", "nerf", "hotfix", "patch", "wowhead")

WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def key(farm):
    """"1109:2673": a note belongs to a mob and the item it's farmed for."""
    return "%d:%d" % (farm["npc"], farm["parts"][0]["item"])


def facts(data, farm):
    """Everything a note may use about one farm."""
    npc, item = farm["npc"], farm["parts"][0]["item"]
    cells = data.mob_area(npc)
    placed = sum(cells.values()) >= data_pages.AREA_MIN_LOOTS
    entry = data.mobs[npc]
    others = [data.item_name(other) for other, _, _ in data.drops(npc)
              if other != item and data.kind(other) not in ("gray", "unknown")][:OTHER_DROPS]
    return {
        "mob": data.mob_name(npc),
        "item": data.item_name(item),
        "zone": data.zone(npc),
        "levels": data.levels(npc),
        "level_low": entry["lmin"] or None,
        "level_high": entry["lmax"] or None,
        "busiest_spot": data_pages.square_coords(data_pages.busiest(cells)) if placed else None,
        "other_spots": sorted(data_pages.square_coords(cell) for cell in cells) if placed else [],
        "other_drops": others,
        "item_is_crafting_reagent": data.kind(item) == "reagent",
    }


def names_in(sheet):
    return [name for name in [sheet["mob"], sheet["item"], sheet["zone"], *sheet["other_drops"]] if name]


def allowed_numbers(sheet):
    found = set()
    for value in [sheet["levels"], sheet["busiest_spot"] or "", *sheet["other_spots"], *names_in(sheet)]:
        found.update(NUMBER.findall(str(value)))
    for level in (sheet["level_low"], sheet["level_high"]):
        if level:
            found.add(str(level))
    return found


def known_name_words(data):
    """Lowercased words of every item, mob and zone name the site knows, for spotting names a note invents."""
    words = set()
    for name in list(data.item_names.values()) + list(data.map_names.values()) + [
            data.mob_name(npc) for npc in data.mobs]:
        words.update(word.lower() for word in WORD.findall(name))
    return words


def check(text, sheet, known_words):
    """Problems with a note, [] when it may be shown: its length, numbers and names the fact sheet doesn't
    give, and claims about the game's behaviour."""
    problems = []
    words = WORD.findall(text)
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        problems.append("%d words; a note has %d to %d" % (len(words), MIN_WORDS, MAX_WORDS))
    numbers = allowed_numbers(sheet)
    for number in NUMBER.findall(text):
        if number not in numbers:
            problems.append("the number %s isn't in the facts" % number)
    if "%" in text or re.search(r"\d\s*[gsc]\b", text):
        problems.append("prices and percentages belong in the live tables")
    lowered = text.lower()
    for claim in FORBIDDEN:
        if re.search(r"\b%s" % re.escape(claim), lowered):
            problems.append("'%s' is a claim the facts can't back" % claim)
    vocabulary = {word for name in names_in(sheet) for word in WORD.findall(name)} | ALLOWED_NAMES
    for match in WORD.finditer(text):
        word = re.sub(r"['’]s?$", "", match.group(0))     # GoldScout's, Coyotes'
        plural = word[:-1] if word.endswith("s") else word
        if not word[0].isupper() or word in vocabulary or plural in vocabulary:
            continue
        before = text[:match.start()].rstrip()
        sentence_start = not before or before[-1] in ".!?:"
        if sentence_start and word.lower() not in known_words:
            continue        # an ordinary word starting a sentence
        problems.append("the name '%s' isn't in the facts" % word)
    return problems


def load(path=NOTES_FILE):
    """{"npc:item": {"text": ..., "written": "YYYY-MM-DD"}} from site/farm_notes.json, or {}."""
    try:
        notes = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in notes.items() if isinstance(v, dict) and isinstance(v.get("text"), str)}


def save(notes, path=NOTES_FILE):
    Path(path).write_text(json.dumps(dict(sorted(notes.items())), indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")


def note_for(data, farm, notes, known_words):
    """A farm's note if it still matches the farm's current facts, else None."""
    note = notes.get(key(farm))
    if not note or check(note["text"], facts(data, farm), known_words):
        return None
    return note["text"]
