"""Parsing and validation for GoldScout drop data exports (/gscout export).

Every export goes through validate() before it can reach Data_Community.lua.
Hard errors reject the whole submission. Warnings mean the data parses but
looks unusual (for example a drop rate far from what other players recorded),
so a maintainer has to approve it by hand.

Export format, one header line then one line per mob:
  GoldScout-export 3^<install ID>^<snapshot number>
  npcID^kills^picks^minLevel^maxLevel^uiMapID^x^y^positions^name^drops^pickDrops
where drops and pickDrops are "itemID:times:quantity" joined by commas. The
install ID is 12 random lowercase letters and digits identifying one WoW
account's GoldScout data; the snapshot number goes up each time that data
changes.

Version 3 adds optional lines after the mobs:
  @i^itemID^name       an item's name, as the player's game client shows it
  @m^uiMapID^name      a zone's name
  @c^itemID^           an item some recipe makes (so it isn't a world drop)
  @l^0^locale          the game client's language ("enUS", "deDE", "koKR"...),
                       version 5 and later; names are in that language
  @a^npcID^cell:count,...  where that mob was looted, as squares of a 20x20
                       grid over its zone map (cell = row * 20 + column),
                       version 5 and later
Version 4 adds:
  @q^itemID^quality:class:reagent   item quality, item class ID and the
                                    Crafting Reagent flag (1, 0 or x unknown)
Version 5 exports can also hold what was fished up, one line per zone and spot:
  @f^uiMapID^spot^catches^skill^items^cells
where spot is 0 for open water or the fishing pool's object ID, catches is how
many loot windows fishing opened there, skill the lowest Fishing skill a catch
came at (0 if unknown), items "itemID:times:quantity" as for mobs, and cells
where the catches were, as for @a. An export can hold only fishing lines.
Version 6 lets a mob line give a zone without a position (x, y and the position
count 0): inside dungeons the game gives addons no map position, only the zone.
Version 7 adds how fast players kill each mob:
  @t^npcID^timed:seconds   timed kills of that mob, and the seconds they took
                           (from the kill before, at most PACE_GAP; longer gaps
                           are breaks and aren't timed), scaled to the pace on
                           mobs of your own level (GoldScout/Learn.lua PaceFactor)
Version 9 changes no line either, only what @t times: a gap between kills over
PACE_GAP still isn't timed, unless both kills were in the same zone at most
HUNT_GAP apart (Learn.lua), so looking for the next one counts. Its times are
only those recorded since (Learn.lua FreshPace); tools/merge_data.py prefers
them, mob by mob, once there are enough.
Version 8 changes no line, only what a rogue's dungeon mobs hold: before
GoldScout v0.12.48 a Pick Pocket inside a dungeon counted as a kill, and those
kills stay in a player's saved data. On an account that pickpockets, version 8
shares only the dungeon loot recorded since that version started them over
(Learn.lua FreshDungeons). From older exports of such an account, dungeon mobs
are left out (fresh_rogue_dungeons).
Versions 2 (no @ lines) and 3 are still accepted; version 1 (no install ID)
isn't.
"""
import math
import re
import unicodedata
from collections import defaultdict

HEADER = "GoldScout-export"
HEADER_RE = re.compile(r"^GoldScout-export ([2-9])\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$")
LOCALE_RE = re.compile(r"^[a-z]{2}[A-Z]{2}$")
AREA_RE = re.compile(r"^\d{1,3}:\d{1,6}(?:,\d{1,3}:\d{1,6})*$")
AREA_CELLS = 400            # a 20x20 grid
KNOWN_VERSION = 9           # the newest export version this copy understands
KNOWN_EXTRA = ("@i", "@m", "@c", "@q", "@l", "@a", "@f", "@t")
NEWER_HEADER_RE = re.compile(r"^GoldScout-export (\d+)\^[a-z0-9]{12}\^[1-9][0-9]{0,8}$")
ITEM_META_RE = re.compile(r"^([0-9]):([0-9]{1,2}):([01x])$")
PACE_RE = re.compile(r"^([0-9]{1,6}):([0-9]{1,9})$")
# A timed kill took at most PACE_GAP seconds (GoldScout/Learn.lua), from version 9 HUNT_GAP, scaled by at most 2
# for the level gap.
MAX_PACE_SECONDS = 180 * 2
MAX_HUNT_SECONDS = 600 * 2
HUNT_PACE = 9               # from this version, kill times count the hunt between kills (Learn.lua HUNT_GAP)


def header(install_id, seq, version=3):
    return "%s %d^%s^%d" % (HEADER, version, install_id, seq)

# Limits. Anything outside them is a hard error.
# One export: GoldScout Companion uploads up to this (the server's limit too, server/src/index.js MAX_BYTES).
# A long-time player's export passes 60 KB: hundreds of mobs, item names and details, crafted items, areas.
MAX_BYTES = 250_000
FORM_MAX_BYTES = 60_000     # through the share form: GitHub issue bodies top out at 65,536 characters
MAX_MOBS = 1500
MAX_ID = 2_000_000          # NPC, item and map IDs
MAX_ATTEMPTS = 5000         # kills or pickpockets of one mob in one export
MAX_LEVEL = 63              # Forever's level cap is 60; bosses show as 63
MAX_LEVEL_SPREAD = 15       # one mob ID rarely spans more levels than this
MAX_ITEMS_PER_MOB = 150
MAX_DROPS_PER_ATTEMPT = 8   # items one corpse or pocket can hold
MAX_QUANTITY_PER_DROP = 250 # average stack size per drop: some bosses drop a full stack of 200 ammo
                            # (Lord Roccor, Shadow Hunter Vosh'gajin, Cannon Master Willey), and some
                            # event mobs a full stack of a quest item (213 Well Cursed Bone)
MAX_NAME_LENGTH = 64
MAX_EXTRA_LINES = 20_000    # @ lines (names, item details, crafted items, areas, fishing) in one export
MAX_FISH_SKILL = 450        # Fishing skill, with lures and gear on top of 300
MAX_ITEMS_PER_SPOT = 100    # different items fished up at one spot

# Rate checks against data already accepted from other players.
OUTLIER_MIN_ATTEMPTS = 30   # both sides need at least this many attempts
OUTLIER_Z = 6.0             # how far apart two drop rates must be to flag
# A rate higher than everyone else's takes at least this many drops to count as unusual: one lucky world drop
# (a green from a Coyote nobody else saw) isn't evidence of anything, and held uploads for review.
OUTLIER_MIN_DROPS = 2

INT = re.compile(r"^(0|[1-9][0-9]{0,8})$")
COORD = re.compile(r"^(0|1)\.[0-9]{1,6}$")
NAME_PUNCTUATION = set(" '-.()!?&·")    # the middle dot: Chinese clients write transliterated names with it
ITEM_NAME_PUNCTUATION = NAME_PUNCTUATION | set(":,")
# Typography the game's languages use, as the plain characters above. French writes a no-break space before ":"
# and curly apostrophes; Chinese and Korean clients use full-width punctuation (NFKC turns those into plain ones).
NAME_LOOKALIKES = str.maketrans({
    "‘": "'", "’": "'", "ʼ": "'", "´": "'", "`": "'",
    "«": "'", "»": "'", "“": "'", "”": "'", "„": "'",
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "…": "...",
})


def clean_name(text, allowed=ITEM_NAME_PUNCTUATION):
    """A name as GoldScout keeps it: typographic and full-width punctuation as plain characters, any other
    character that isn't a letter, digit or allowed punctuation as a space, and spaces collapsed. One odd
    character in a name never costs a player their whole export."""
    text = unicodedata.normalize("NFKC", text.translate(NAME_LOOKALIKES)).translate(NAME_LOOKALIKES)
    text = "".join(c if c.isalpha() or c.isdigit() or c in allowed else " " for c in text)
    return " ".join(text.split())


class Mob:
    __slots__ = ("npc", "k", "p", "lmin", "lmax", "m", "x", "y", "c", "n", "i", "pi", "a", "t", "s", "hunt")

    def __init__(self, **fields):
        self.a = {}          # area cells {cell: count} on map m (version 5)
        self.t, self.s = 0, 0   # timed kills and the seconds they took, at your own level's pace (version 7)
        self.hunt = False       # timed with the hunt between kills (version 9, HUNT_PACE)
        for key, value in fields.items():
            setattr(self, key, value)

    def to_line(self):
        def items(table):
            return ",".join("%d:%d:%d" % (item, d, q) for item, (d, q) in sorted(table.items()))
        return "^".join([
            str(self.npc), str(self.k), str(self.p), str(self.lmin), str(self.lmax), str(self.m),
            "%.4f" % self.x, "%.4f" % self.y, str(self.c), self.n, items(self.i), items(self.pi),
        ])


class Fish:
    """What was fished up at one spot (open water is spot 0) on one map."""
    __slots__ = ("m", "spot", "n", "s", "i", "a")

    def __init__(self, m, spot, n, s, i, a):
        self.m, self.spot, self.n, self.s, self.i, self.a = m, spot, n, s, i, a

    def to_line(self):
        return "^".join(["@f", str(self.m), str(self.spot), str(self.n), str(self.s),
                         ",".join("%d:%d:%d" % (item, d, q) for item, (d, q) in sorted(self.i.items())),
                         ",".join("%d:%d" % pair for pair in sorted(self.a.items()))])


class Result:
    def __init__(self):
        self.mobs = []
        self.errors = []
        self.warnings = []
        self.outliers = []   # compare(): every rate far from other players', as Outlier
        self.install_id = None
        self.seq = None
        self.version = 3
        self.item_names = {}
        self.map_names = {}
        self.crafted = set()
        self.item_meta = {}  # itemID -> (quality, classID, reagent: True/False/None)
        self.locale = None   # the client's language (version 5+); None for older exports
        self.areas = {}      # npcID -> {cell: count} from @a lines, attached to the mobs
        self.paces = {}      # npcID -> (timed kills, seconds) from @t lines, attached to the mobs
        self.pocket_loot = False   # PICKPOCKET_ONLY items were taken out of kill loot: this account pickpockets
        self.left_out = 0    # dungeon mobs fresh_rogue_dungeons() took out
        self.fishing = []    # Fish from @f lines
        # Names keep_english_names() took out of a non-English export, kept apart for the website's
        # pages in that language: {"items": {itemID: name}, "maps": {...}, "mobs": {npcID: name}}.
        self.local_names = {}

    def text(self):
        """The export rebuilt from the validated data."""
        lines = [header(self.install_id, self.seq, self.version)] + [mob.to_line() for mob in self.mobs]
        lines += ["@i^%d^%s" % (item, name) for item, name in sorted(self.item_names.items())]
        lines += ["@q^%d^%d:%d:%s" % (item, quality, class_id, {True: "1", False: "0"}.get(reagent, "x"))
                  for item, (quality, class_id, reagent) in sorted(self.item_meta.items())]
        lines += ["@m^%d^%s" % (map_id, name) for map_id, name in sorted(self.map_names.items())]
        lines += ["@c^%d^" % item for item in sorted(self.crafted)]
        for mob in self.mobs:
            if mob.a:
                lines.append("@a^%d^%s" % (mob.npc, ",".join("%d:%d" % pair for pair in sorted(mob.a.items()))))
        lines += ["@t^%d^%d:%d" % (mob.npc, mob.t, mob.s) for mob in self.mobs if mob.t]
        lines += [fish.to_line() for fish in sorted(self.fishing, key=lambda f: (f.m, f.spot))]
        if self.locale:
            lines.append("@l^0^%s" % self.locale)
        return "\n".join(lines) + "\n"

    @property
    def ok(self):
        return not self.errors


def _int(text, what, line_no, result, low=0, high=MAX_ID):
    if text == "-0":
        text = "0"   # Lua writes a negative zero this way; it's still zero (one player's exports had it)
    if not INT.match(text):
        result.errors.append("Line %d: %s is not a whole number." % (line_no, what))
        return None
    value = int(text)
    if value < low or value > high:
        result.errors.append("Line %d: %s %d is outside %d-%d." % (line_no, what, value, low, high))
        return None
    return value


def _name(text, line_no, result):
    if len(text) > MAX_NAME_LENGTH:
        result.errors.append("Line %d: mob name is longer than %d characters." % (line_no, MAX_NAME_LENGTH))
        return None
    return clean_name(text, NAME_PUNCTUATION)


def _items(text, what, attempts, line_no, result):
    items = {}
    if text == "":
        return items
    parts = text.split(",")
    if len(parts) > MAX_ITEMS_PER_MOB:
        result.errors.append("Line %d: more than %d different %s." % (line_no, MAX_ITEMS_PER_MOB, what))
        return None
    total = 0
    for part in parts:
        pieces = part.split(":")
        if len(pieces) != 3:
            result.errors.append("Line %d: a %s entry isn't itemID:times:quantity." % (line_no, what))
            return None
        item = _int(pieces[0], "item ID", line_no, result, low=1)
        times = _int(pieces[1], "drop count", line_no, result, low=1, high=MAX_ATTEMPTS)
        quantity = _int(pieces[2], "quantity", line_no, result, low=1,
                        high=MAX_ATTEMPTS * MAX_QUANTITY_PER_DROP)
        if item is None or times is None or quantity is None:
            return None
        if item in items:
            result.errors.append("Line %d: item %d is listed twice in %s." % (line_no, item, what))
            return None
        if times > attempts:
            result.errors.append("Line %d: item %d dropped %d times in only %d attempts."
                                 % (line_no, item, times, attempts))
            return None
        if quantity < times or quantity > times * MAX_QUANTITY_PER_DROP:
            result.errors.append("Line %d: item %d has an impossible quantity (%d from %d drops)."
                                 % (line_no, item, quantity, times))
            return None
        items[item] = (times, quantity)
        total += times
    if total > attempts * MAX_DROPS_PER_ATTEMPT:
        result.errors.append("Line %d: more %s than a mob can carry over %d attempts." % (line_no, what, attempts))
        return None
    return items


def _parse_line(line, line_no, result):
    fields = line.split("^")
    if len(fields) != 12:
        result.errors.append("Line %d: expected 12 fields separated by ^, found %d." % (line_no, len(fields)))
        return None
    npc = _int(fields[0], "NPC ID", line_no, result, low=1)
    kills = _int(fields[1], "kill count", line_no, result, high=MAX_ATTEMPTS)
    picks = _int(fields[2], "pickpocket count", line_no, result, high=MAX_ATTEMPTS)
    lmin = _int(fields[3], "minimum level", line_no, result, high=MAX_LEVEL)
    lmax = _int(fields[4], "maximum level", line_no, result, high=MAX_LEVEL)
    map_id = _int(fields[5], "map ID", line_no, result)
    positions = _int(fields[8], "position count", line_no, result, high=MAX_ATTEMPTS)
    if None in (npc, kills, picks, lmin, lmax, map_id, positions):
        return None
    if kills + picks == 0:
        result.errors.append("Line %d: no kills or pickpockets recorded." % line_no)
        return None
    if (lmin == 0) != (lmax == 0) or lmin > lmax or lmax - lmin > MAX_LEVEL_SPREAD:
        result.errors.append("Line %d: levels %d-%d don't make sense." % (line_no, lmin, lmax))
        return None

    if not COORD.match(fields[6]) or not COORD.match(fields[7]):
        result.errors.append("Line %d: map position isn't a decimal between 0 and 1." % line_no)
        return None
    x, y = float(fields[6]), float(fields[7])
    if x > 1 or y > 1:
        result.errors.append("Line %d: map position is outside the map." % line_no)
        return None
    if map_id == 0:
        if positions or x or y:
            result.errors.append("Line %d: has a position but no map." % line_no)
            return None
    elif positions == 0 and not (x or y) and result.version >= 6:
        pass    # a zone without a position: inside a dungeon
    elif positions == 0 or positions > kills:
        result.errors.append("Line %d: %d positions for %d kills." % (line_no, positions, kills))
        return None

    name = _name(fields[9], line_no, result)
    drops = _items(fields[10], "drops", kills, line_no, result)
    pick_drops = _items(fields[11], "pickpocket items", picks, line_no, result)
    if name is None or drops is None or pick_drops is None:
        return None
    for item in PICKPOCKET_ONLY & set(drops):
        del drops[item]
        result.pocket_loot = True
    if kills == 0 and drops:
        result.errors.append("Line %d: drops listed with no kills." % line_no)
        return None
    if picks == 0 and pick_drops:
        result.errors.append("Line %d: pickpocket items listed with no pickpockets." % line_no)
        return None
    return Mob(npc=npc, k=kills, p=picks, lmin=lmin, lmax=lmax, m=map_id, x=x, y=y, c=positions,
               n=name, i=drops, pi=pick_drops)


def _cells(text, line_no, result):
    """ "cell:count,..." -> {cell: count}, or None (with an error) if it's malformed."""
    pairs = [p.split(":") for p in text.split(",")] if AREA_RE.match(text) else None
    if not pairs or any(int(c) >= AREA_CELLS or int(n) < 1 for c, n in pairs) or \
            len({int(c) for c, _ in pairs}) != len(pairs):
        result.errors.append("Line %d: area cells must look like cell:count,... (cells 0-399)." % line_no)
        return None
    return {int(c): int(n) for c, n in pairs}


def _parse_fish(line, line_no, result):
    """One @f line: what was fished up at a spot."""
    fields = line.split("^")
    if result.version < 5:
        result.errors.append("Line %d: fishing lines need a version 5 export." % line_no)
        return
    if len(fields) != 7:
        result.errors.append("Line %d: a fishing line has 7 fields separated by ^, found %d." % (line_no, len(fields)))
        return
    map_id = _int(fields[1], "map ID", line_no, result, low=1)
    spot = _int(fields[2], "fishing spot", line_no, result)
    catches = _int(fields[3], "catch count", line_no, result, low=1, high=MAX_ATTEMPTS)
    skill = _int(fields[4], "Fishing skill", line_no, result, high=MAX_FISH_SKILL)
    if None in (map_id, spot, catches, skill):
        return
    if len(fields[5].split(",")) > MAX_ITEMS_PER_SPOT:
        result.errors.append("Line %d: more than %d different items fished up." % (line_no, MAX_ITEMS_PER_SPOT))
        return
    items = _items(fields[5], "catches", catches, line_no, result)
    if items is None:
        return
    cells = _cells(fields[6], line_no, result) if fields[6] else {}
    if cells is None:
        return
    if sum(cells.values()) > catches:
        result.errors.append("Line %d: more catch positions than catches." % line_no)
        return
    if any(f.m == map_id and f.spot == spot for f in result.fishing):
        result.errors.append("Line %d: map %d spot %d has more than one fishing line." % (line_no, map_id, spot))
        return
    result.fishing.append(Fish(map_id, spot, catches, skill, items, cells))


def _parse_pace(fields, line_no, result):
    """One @t line: how many kills of a mob were timed, and how long they took."""
    if result.version < 7:
        result.errors.append("Line %d: kill time lines need a version 7 export." % line_no)
        return
    npc = _int(fields[1], "NPC ID", line_no, result, low=1)
    match = PACE_RE.match(fields[2])
    if npc is None:
        return
    if not match:
        result.errors.append("Line %d: a kill time line must look like @t^npcID^kills:seconds." % line_no)
        return
    timed, seconds = int(match.group(1)), int(match.group(2))
    most = MAX_HUNT_SECONDS if result.version >= HUNT_PACE else MAX_PACE_SECONDS
    if timed < 1 or seconds > timed * most:
        result.errors.append("Line %d: NPC %d's kill times are out of range." % (line_no, npc))
    elif npc in result.paces:
        result.errors.append("Line %d: NPC %d has more than one kill time line." % (line_no, npc))
    else:
        result.paces[npc] = (timed, seconds)


def _parse_extra(line, line_no, result):
    """One @ line: an item name, item details, a zone name or a crafted item."""
    fields = line.split("^")
    if fields[0] == "@f":
        _parse_fish(line, line_no, result)
        return
    if fields[0] == "@t" and len(fields) == 3:
        _parse_pace(fields, line_no, result)
        return
    if len(fields) != 3 or fields[0] not in ("@i", "@m", "@c", "@q", "@l", "@a"):
        result.errors.append("Line %d: expected @i, @q, @m, @c, @l or @a followed by an ID and a value." % line_no)
        return
    kind, id_text, name = fields
    if kind == "@a":
        npc = _int(id_text, "NPC ID", line_no, result, low=1) if result.version >= 5 else None
        if result.version < 5:
            result.errors.append("Line %d: area lines need a version 5 export." % line_no)
        elif npc is not None:
            cells = _cells(name, line_no, result)
            if cells is None:
                pass
            elif npc in result.areas:
                result.errors.append("Line %d: NPC %d has more than one area line." % (line_no, npc))
            else:
                result.areas[npc] = cells
        return
    if kind == "@l":
        if result.version < 5:
            result.errors.append("Line %d: a language line needs a version 5 export." % line_no)
        elif id_text != "0" or not LOCALE_RE.match(name):
            result.errors.append("Line %d: the language line must look like @l^0^enUS." % line_no)
        else:
            result.locale = name
        return
    if kind == "@q" and result.version < 4:
        result.errors.append("Line %d: item detail lines need a version 4 export." % line_no)
        return
    some_id = _int(id_text, "ID", line_no, result, low=1)
    if some_id is None:
        return
    if kind == "@q":
        match = ITEM_META_RE.match(name)
        if not match:
            result.errors.append("Line %d: item details must look like quality:class:reagent." % line_no)
            return
        reagent = {"1": True, "0": False}.get(match.group(3))
        result.item_meta[some_id] = (int(match.group(1)), int(match.group(2)), reagent)
        return
    if kind == "@c":
        if name:
            result.errors.append("Line %d: a crafted-item line has no name." % line_no)
            return
        result.crafted.add(some_id)
        return
    if not name or len(name) > MAX_NAME_LENGTH or name != name.strip():
        result.errors.append("Line %d: the name is empty, too long or padded." % line_no)
        return
    name = clean_name(name)
    if not name:
        result.errors.append("Line %d: the name has no letters or digits." % line_no)
        return
    (result.item_names if kind == "@i" else result.map_names)[some_id] = name


def newer_format(text):
    """True for an export a newer GoldScout wrote: a higher version, or @ lines
    this copy doesn't know. GoldScout Companion shares those as they are and
    lets the server (always updated first) check them, so an out-of-date
    companion never holds a player's data back."""
    lines = [line.strip() for line in (text or "").replace("\r", "").split("\n") if line.strip()]
    match = NEWER_HEADER_RE.match(lines[0]) if lines else None
    if not match:
        return False
    if int(match.group(1)) > KNOWN_VERSION:
        return True
    return any(line.startswith("@") and line.split("^")[0] not in KNOWN_EXTRA for line in lines[1:])


def latin(name):
    """True when a name uses only Latin letters (English, and most of German and French)."""
    return all(ord(c) < 0x250 for c in name)


def keep_english_names(result):
    """Drops the names in a result that aren't English, in place, so the shared
    data and the website stay English: every name in a non-English export, and
    in older exports (no language line) any name in a non-Latin script. Drop
    counts and everything else are kept. A non-English export's names are kept
    apart in result.local_names, for the website's pages in that language."""
    english = result.locale is None or result.locale.startswith("en")

    def keep(name):
        return english and (result.locale is not None or latin(name))

    if result.locale and not english:
        result.local_names = {"items": dict(result.item_names), "maps": dict(result.map_names),
                              "mobs": {mob.npc: mob.n for mob in result.mobs if mob.n}}
    for mob in result.mobs:
        if mob.n and not keep(mob.n):
            mob.n = ""
    result.item_names = {k: v for k, v in result.item_names.items() if keep(v)}
    result.map_names = {k: v for k, v in result.map_names.items() if keep(v)}
    return result


def parse(text):
    """Parses and checks one export. Returns a Result with mobs and any errors."""
    result = Result()
    if len(text.encode("utf-8")) > MAX_BYTES:
        result.errors.append("The export is larger than %d bytes." % MAX_BYTES)
        return result
    lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]
    match = HEADER_RE.match(lines[0]) if lines else None
    if not match:
        if lines and lines[0] == "GoldScout-export 1":
            result.errors.append("This export is from an older GoldScout. Update GoldScout, log in, "
                                 "and export again.")
        else:
            result.errors.append("The first line must look like 'GoldScout-export 3^<install ID>^<number>'.")
        return result
    result.version, result.install_id, result.seq = int(match.group(1)), match.group(2), int(match.group(3))
    mob_lines = [(n, line) for n, line in enumerate(lines[1:], start=2) if not line.startswith("@")]
    extra_lines = [(n, line) for n, line in enumerate(lines[1:], start=2) if line.startswith("@")]
    if not mob_lines and not any(line.startswith("@f^") for _, line in extra_lines):
        result.errors.append("The export has no mobs or fishing in it.")
        return result
    if len(mob_lines) > MAX_MOBS:
        result.errors.append("The export has more than %d mobs." % MAX_MOBS)
        return result
    if extra_lines and result.version < 3:
        result.errors.append("Line %d: name lines need a version 3 export." % extra_lines[0][0])
        return result
    if len(extra_lines) > MAX_EXTRA_LINES:
        result.errors.append("The export has more than %d name lines." % MAX_EXTRA_LINES)
        return result
    for line_no, line in extra_lines:
        _parse_extra(line, line_no, result)
        if len(result.errors) >= 20:
            result.errors.append("Stopped checking after 20 errors.")
            return result
    seen = set()
    for line_no, line in mob_lines:
        mob = _parse_line(line, line_no, result)
        if mob is None:
            if len(result.errors) >= 20:
                result.errors.append("Stopped checking after 20 errors.")
                break
            continue
        if mob.npc in seen:
            result.errors.append("Line %d: NPC %d appears more than once." % (line_no, mob.npc))
            continue
        seen.add(mob.npc)
        result.mobs.append(mob)
    for npc in result.areas:
        if npc not in seen:
            result.errors.append("An area line is for NPC %d, which isn't in the export." % npc)
    for npc, (timed, _) in result.paces.items():
        mob = next((mob for mob in result.mobs if mob.npc == npc), None)
        if mob is None:
            result.errors.append("A kill time line is for NPC %d, which isn't in the export." % npc)
        elif timed > mob.k:
            result.errors.append("NPC %d has more timed kills (%d) than kills (%d)." % (npc, timed, mob.k))
    for mob in result.mobs:
        if mob.m and mob.c:     # cells are on the mob's map; without one they mean nothing
            mob.a = result.areas.get(mob.npc, {})
        mob.t, mob.s = result.paces.get(mob.npc, (0, 0))
        mob.hunt = result.version >= HUNT_PACE
    fresh_rogue_dungeons(result)
    return result


# The export version from which a pickpocketing account's dungeon mobs hold only loot recorded since GoldScout
# started them over (GoldScout/Learn.lua FreshDungeons).
FRESH_ROGUE_DUNGEONS = 8


def fresh_rogue_dungeons(result):
    """Takes the dungeon mobs (kills with no position) out of an export older than FRESH_ROGUE_DUNGEONS from an
    account that pickpockets. Before GoldScout v0.12.48 a Pick Pocket inside a dungeon counted as a kill, so such a
    player's dungeon mobs have up to twice their real kills (checked 2026-11-26: rogues' dungeon kills held 0.87 of
    the loot other players got from the same mobs, 0.97 outdoors), and nothing in the export tells those kills
    apart. Mobs with only pickpocketing stay: picks were never counted wrongly."""
    if result.version >= FRESH_ROGUE_DUNGEONS or not (result.pocket_loot or any(mob.p for mob in result.mobs)):
        return
    kept = [mob for mob in result.mobs if mob.c or not mob.k]
    result.left_out = len(result.mobs) - len(kept)
    result.mobs = kept


def _z(drops_a, attempts_a, drops_b, attempts_b):
    pooled = (drops_a + drops_b) / (attempts_a + attempts_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / attempts_a + 1 / attempts_b))
    if spread == 0:
        return 0.0
    return (drops_a / attempts_a - drops_b / attempts_b) / spread


QUEST_ITEM_CLASS = 12   # Blizzard's item class for quest items

# Items that come only from picking pockets. In a mob's kill loot they're a rogue's pickpocket recorded as a kill
# (GoldScout before v0.12.40 missed picks of a mob you hadn't targeted, and pockets a Cheap Shot macro left full
# turn up on the corpse), so they're dropped from kill loot as an export is read. Besides the junkboxes, the
# community data shows these: picked from mobs that players who never pickpocket killed 430 to 4,800 times
# without one dropping, while every one in kill loot came from a rogue (checked 2026-11-21; An Exotic Cookbook and
# Hickory Pipe 2026-11-26, none in 25,000 to 29,000 kills by players who never pickpocket).
PICKPOCKET_ONLY = frozenset((
    16882, 16883, 16884, 16885,   # Battered, Worn, Sturdy and Heavy Junkbox
    5373, 5374, 5379, 5430,       # Lucky Charm, Small Pocket Watch, Boot Knife, Intricate Bauble
    5428, 5432,                   # An Exotic Cookbook, Hickory Pipe
    10457, 17124,                 # Empty Sea Snail Shell, Syndicate Emblem (a rogue quest's pickpocket)
))


class Outlier:
    """One rate compare() flagged: this player's drops of item from npc (key "i" loot, "pi" pickpocket) over
    attempts, against everyone else's theirs over other_attempts."""
    __slots__ = ("npc", "key", "item", "drops", "attempts", "theirs", "other_attempts")

    def __init__(self, npc, key, item, drops, attempts, theirs, other_attempts):
        self.npc, self.key, self.item = npc, key, item
        self.drops, self.attempts, self.theirs, self.other_attempts = drops, attempts, theirs, other_attempts


def tally(mob_lists):
    """Everyone's kills, picks and drops per mob, added up once: {npc: {"k", "p", "i": {item: drops},
    "pi": {item: drops}}}. compare() takes it so a run checking many players reads every file once."""
    totals = {}
    for mobs in mob_lists:
        for mob in mobs:
            entry = totals.setdefault(mob.npc, {"k": 0, "p": 0, "i": defaultdict(int), "pi": defaultdict(int)})
            entry["k"] += mob.k
            entry["p"] += mob.p
            for item, (d, _) in mob.i.items():
                entry["i"][item] += d
            for item, (d, _) in mob.pi.items():
                entry["pi"][item] += d
    return totals


def compare(result, others, quest_items=(), totals=None, minus=None):
    """Adds a warning for every drop rate far from what other players recorded.

    others is a list of mob lists from accepted submissions (not including
    this player's). Or, for many checks in one run, totals is tally() of every
    accepted submission and minus is tally() of this player's own, taken back
    out. Rates are compared per mob and item, with a z-test on the
    two proportions. Quest items (class QUEST_ITEM_CLASS in this export's item
    details, or in quest_items, from other players') aren't compared: they drop
    only while you're on the quest, so a player who isn't sees 0% where others
    saw 40%, and they can't be sold, so their rates change no one's gold."""
    skip = set(quest_items) | {item for item, meta in result.item_meta.items() if meta[1] == QUEST_ITEM_CLASS}
    totals = tally(others) if totals is None else totals
    minus = minus or {}
    flagged = 0
    for mob in result.mobs:
        entry = totals.get(mob.npc)
        if not entry:
            continue
        own = minus.get(mob.npc, {"k": 0, "p": 0, "i": {}, "pi": {}})
        for key, attempts, other_attempts in (("i", mob.k, entry["k"] - own["k"]),
                                              ("pi", mob.p, entry["p"] - own["p"])):
            if attempts < OUTLIER_MIN_ATTEMPTS or other_attempts < OUTLIER_MIN_ATTEMPTS:
                continue
            mine = getattr(mob, key)
            for item in sorted((set(mine) | set(entry[key])) - skip):
                drops = mine.get(item, (0, 0))[0]
                theirs = entry[key].get(item, 0) - own[key].get(item, 0)
                if drops < OUTLIER_MIN_DROPS and drops * other_attempts > theirs * attempts:
                    continue    # one drop above everyone else's rate: luck, not a pattern
                z = _z(drops, attempts, theirs, other_attempts)
                if abs(z) >= OUTLIER_Z:
                    flagged += 1
                    result.outliers.append(Outlier(mob.npc, key, item, drops, attempts, theirs, other_attempts))
                    if flagged <= 15:
                        result.warnings.append(
                            "NPC %d, item %d: %.1f%% over %d attempts, other players recorded %.1f%% over %d."
                            % (mob.npc, item, 100 * drops / attempts, attempts,
                               100 * theirs / other_attempts, other_attempts))
    if flagged > 15:
        result.warnings.append("...and %d more rates that differ sharply." % (flagged - 15))
    return result
