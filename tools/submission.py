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
Version 4 adds:
  @q^itemID^quality:class:reagent   item quality, item class ID and the
                                    Crafting Reagent flag (1, 0 or x unknown)
Versions 2 (no @ lines) and 3 are still accepted; version 1 (no install ID)
isn't.
"""
import math
import re
from collections import defaultdict

HEADER = "GoldScout-export"
HEADER_RE = re.compile(r"^GoldScout-export ([234])\^([a-z0-9]{12})\^([1-9][0-9]{0,8})$")
ITEM_META_RE = re.compile(r"^([0-9]):([0-9]{1,2}):([01x])$")


def header(install_id, seq, version=3):
    return "%s %d^%s^%d" % (HEADER, version, install_id, seq)

# Limits. Anything outside them is a hard error.
MAX_BYTES = 60000           # GitHub issue bodies top out at 65536 characters
MAX_MOBS = 1500
MAX_ID = 2_000_000          # NPC, item and map IDs
MAX_ATTEMPTS = 5000         # kills or pickpockets of one mob in one export
MAX_LEVEL = 63              # Forever's level cap is 60; bosses show as 63
MAX_LEVEL_SPREAD = 15       # one mob ID rarely spans more levels than this
MAX_ITEMS_PER_MOB = 150
MAX_DROPS_PER_ATTEMPT = 8   # items one corpse or pocket can hold
MAX_QUANTITY_PER_DROP = 100 # average stack size per drop
MAX_NAME_LENGTH = 64
MAX_EXTRA_LINES = 5000      # @ lines (names and crafted items) in one export

# Rate checks against data already accepted from other players.
OUTLIER_MIN_ATTEMPTS = 30   # both sides need at least this many attempts
OUTLIER_Z = 6.0             # how far apart two drop rates must be to flag

INT = re.compile(r"^(0|[1-9][0-9]{0,8})$")
COORD = re.compile(r"^(0|1)\.[0-9]{1,6}$")
NAME_PUNCTUATION = set(" '-.()!?&")
ITEM_NAME_PUNCTUATION = NAME_PUNCTUATION | set(":,")


class Mob:
    __slots__ = ("npc", "k", "p", "lmin", "lmax", "m", "x", "y", "c", "n", "i", "pi")

    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)

    def to_line(self):
        def items(table):
            return ",".join("%d:%d:%d" % (item, d, q) for item, (d, q) in sorted(table.items()))
        return "^".join([
            str(self.npc), str(self.k), str(self.p), str(self.lmin), str(self.lmax), str(self.m),
            "%.4f" % self.x, "%.4f" % self.y, str(self.c), self.n, items(self.i), items(self.pi),
        ])


class Result:
    def __init__(self):
        self.mobs = []
        self.errors = []
        self.warnings = []
        self.install_id = None
        self.seq = None
        self.version = 3
        self.item_names = {}
        self.map_names = {}
        self.crafted = set()
        self.item_meta = {}  # itemID -> (quality, classID, reagent: True/False/None)

    def text(self):
        """The export rebuilt from the validated data."""
        lines = [header(self.install_id, self.seq, self.version)] + [mob.to_line() for mob in self.mobs]
        lines += ["@i^%d^%s" % (item, name) for item, name in sorted(self.item_names.items())]
        lines += ["@q^%d^%d:%d:%s" % (item, quality, class_id, {True: "1", False: "0"}.get(reagent, "x"))
                  for item, (quality, class_id, reagent) in sorted(self.item_meta.items())]
        lines += ["@m^%d^%s" % (map_id, name) for map_id, name in sorted(self.map_names.items())]
        lines += ["@c^%d^" % item for item in sorted(self.crafted)]
        return "\n".join(lines) + "\n"

    @property
    def ok(self):
        return not self.errors


def _int(text, what, line_no, result, low=0, high=MAX_ID):
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
    for char in text:
        if not (char.isalpha() or char.isdigit() or char in NAME_PUNCTUATION):
            result.errors.append("Line %d: mob name contains a character that isn't allowed." % line_no)
            return None
    return text.strip()


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
    elif positions == 0 or positions > kills:
        result.errors.append("Line %d: %d positions for %d kills." % (line_no, positions, kills))
        return None

    name = _name(fields[9], line_no, result)
    drops = _items(fields[10], "drops", kills, line_no, result)
    pick_drops = _items(fields[11], "pickpocket items", picks, line_no, result)
    if name is None or drops is None or pick_drops is None:
        return None
    if kills == 0 and drops:
        result.errors.append("Line %d: drops listed with no kills." % line_no)
        return None
    if picks == 0 and pick_drops:
        result.errors.append("Line %d: pickpocket items listed with no pickpockets." % line_no)
        return None
    return Mob(npc=npc, k=kills, p=picks, lmin=lmin, lmax=lmax, m=map_id, x=x, y=y, c=positions,
               n=name, i=drops, pi=pick_drops)


def _parse_extra(line, line_no, result):
    """One @ line: an item name, item details, a zone name or a crafted item."""
    fields = line.split("^")
    if len(fields) != 3 or fields[0] not in ("@i", "@m", "@c", "@q"):
        result.errors.append("Line %d: expected @i, @q, @m or @c followed by an ID and a value." % line_no)
        return
    kind, id_text, name = fields
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
    if any(not (c.isalpha() or c.isdigit() or c in ITEM_NAME_PUNCTUATION) for c in name):
        result.errors.append("Line %d: the name contains a character that isn't allowed." % line_no)
        return
    (result.item_names if kind == "@i" else result.map_names)[some_id] = name


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
    if not mob_lines:
        result.errors.append("The export has no mobs in it.")
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
    return result


def _z(drops_a, attempts_a, drops_b, attempts_b):
    pooled = (drops_a + drops_b) / (attempts_a + attempts_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / attempts_a + 1 / attempts_b))
    if spread == 0:
        return 0.0
    return (drops_a / attempts_a - drops_b / attempts_b) / spread


def compare(result, others):
    """Adds a warning for every drop rate far from what other players recorded.

    others is a list of mob lists from accepted submissions (not including
    this player's). Rates are compared per mob and item, with a z-test on the
    two proportions."""
    totals = defaultdict(lambda: {"k": 0, "p": 0, "i": defaultdict(int), "pi": defaultdict(int)})
    for mobs in others:
        for mob in mobs:
            entry = totals[mob.npc]
            entry["k"] += mob.k
            entry["p"] += mob.p
            for item, (d, _) in mob.i.items():
                entry["i"][item] += d
            for item, (d, _) in mob.pi.items():
                entry["pi"][item] += d
    flagged = 0
    for mob in result.mobs:
        entry = totals.get(mob.npc)
        if not entry:
            continue
        for key, attempts, other_attempts in (("i", mob.k, entry["k"]), ("pi", mob.p, entry["p"])):
            if attempts < OUTLIER_MIN_ATTEMPTS or other_attempts < OUTLIER_MIN_ATTEMPTS:
                continue
            mine = getattr(mob, key)
            for item in set(mine) | set(entry[key]):
                drops = mine.get(item, (0, 0))[0]
                z = _z(drops, attempts, entry[key].get(item, 0), other_attempts)
                if abs(z) >= OUTLIER_Z:
                    flagged += 1
                    if flagged <= 15:
                        result.warnings.append(
                            "NPC %d, item %d: %.1f%% over %d attempts, other players recorded %.1f%% over %d."
                            % (mob.npc, item, 100 * drops / attempts, attempts,
                               100 * entry[key].get(item, 0) / other_attempts, other_attempts))
    if flagged > 15:
        result.warnings.append("...and %d more rates that differ sharply." % (flagged - 15))
    return result
