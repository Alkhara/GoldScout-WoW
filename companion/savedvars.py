"""Reads GoldScout's SavedVariables and builds a drop data export from them.

The companion only ever reads these files; it never writes to the WoW folder.
"""
import re
import string
from pathlib import Path

FOREVER = "_forever_"
SAVED_FILE = "GoldScout.lua"


class LuaError(ValueError):
    pass


_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<comment>--\[(?P<eq>=*)\[.*?\](?P=eq)\]|--[^\n]*)
  | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<number>-?(?:0[xX][0-9a-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<punct>[{}\[\]=,;])
""", re.X | re.S)

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
            "\\": "\\", '"': '"', "'": "'", "\n": "\n"}


def _unescape(body):
    out, i = [], 0
    while i < len(body):
        char = body[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if nxt.isdigit():
            digits = re.match(r"\d{1,3}", body[i + 1:]).group(0)
            out.append(chr(int(digits)))
            i += 1 + len(digits)
        else:
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
    # Lua strings are bytes; WoW writes UTF-8.
    try:
        return "".join(out).encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return "".join(out)


def _tokens(text):
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match:
            raise LuaError("unexpected character at offset %d" % pos)
        pos = match.end()
        kind = match.lastgroup
        if kind in ("space", "comment", "eq"):
            continue
        yield kind, match.group(kind)


class _Parser:
    def __init__(self, text):
        self.tokens = list(_tokens(text))
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise LuaError("expected %r, found %r" % (value, token[1]))
        self.pos += 1
        return token

    def value(self):
        kind, text = self.take()
        if kind == "string":
            return _unescape(text[1:-1])
        if kind == "number":
            return int(text, 0) if re.fullmatch(r"-?(0[xX][0-9a-fA-F]+|\d+)", text) else float(text)
        if kind == "name":
            if text in ("true", "false"):
                return text == "true"
            if text == "nil":
                return None
            raise LuaError("unexpected name %r" % text)
        if text == "{":
            return self.table()
        raise LuaError("unexpected %r" % text)

    def table(self):
        result, index = {}, 1
        while self.peek()[1] != "}":
            if self.peek()[1] == "[":
                self.take("[")
                key = self.value()
                self.take("]")
                self.take("=")
                result[key] = self.value()
            elif self.peek()[0] == "name" and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][1] == "=":
                key = self.take()[1]
                self.take("=")
                result[key] = self.value()
            else:
                result[index] = self.value()
                index += 1
            if self.peek()[1] in (",", ";"):
                self.take()
        self.take("}")
        return result

    def assignments(self):
        variables = {}
        while self.peek()[0] is not None:
            kind, name = self.take()
            if kind != "name":
                raise LuaError("expected a variable name, found %r" % name)
            self.take("=")
            variables[name] = self.value()
        return variables


def parse_saved_variables(text):
    """Parses a SavedVariables file into {variable name: value}."""
    return _Parser(text).assignments()


# ---------------------------------------------------------------------------
# Finding the files
# ---------------------------------------------------------------------------
COMMON_ROOTS = ("World of Warcraft", r"Program Files (x86)\World of Warcraft",
                r"Program Files\World of Warcraft", r"Blizzard Games\World of Warcraft",
                r"Games\World of Warcraft", r"Battle.net\World of Warcraft")


def _registry_roots():
    try:
        import winreg
    except ImportError:
        return []
    roots = []
    for key_path in (r"SOFTWARE\WOW6432Node\Blizzard Entertainment\World of Warcraft",
                     r"SOFTWARE\Blizzard Entertainment\World of Warcraft"):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
                # InstallPath points at a flavor folder such as _retail_.
                roots.append(path.parent if path.name.startswith("_") else path)
        except OSError:
            pass
    return roots


def find_forever_folders():
    """Every WoW Forever folder (the _forever_ directory) found on this PC."""
    candidates = list(_registry_roots())
    for drive in string.ascii_uppercase:
        base = Path("%s:\\" % drive)
        if not base.exists():
            continue
        candidates += [base / root for root in COMMON_ROOTS]
    found = []
    for root in candidates:
        folder = root / FOREVER
        if folder.is_dir() and folder not in found:
            found.append(folder)
    return found


def normalize_wow_folder(path):
    """Accepts the World of Warcraft folder, _forever_ itself, or AddOns inside it."""
    path = Path(path)
    for candidate in (path, path / FOREVER, *path.parents):
        if candidate.name == FOREVER and candidate.is_dir():
            return candidate
    return None


def saved_variables_files(forever):
    """GoldScout's account-wide SavedVariables file for each WoW account."""
    return sorted(Path(forever).glob("WTF/Account/*/SavedVariables/" + SAVED_FILE))


# ---------------------------------------------------------------------------
# Building the export
# ---------------------------------------------------------------------------
_NAME_OK = set(" '-.()!?&")


def _clean_name(name):
    if not isinstance(name, str):
        return ""
    kept = "".join(c if (c.isalpha() or c.isdigit() or c in _NAME_OK) else " " for c in name)
    return " ".join(kept.split())[:64]


def _int(value):
    return int(value) if isinstance(value, (int, float)) and value >= 0 else 0


def _items(table, attempts):
    items = {}
    for item_id, stat in (table or {}).items():
        if not isinstance(item_id, int) or item_id <= 0 or not isinstance(stat, dict):
            continue
        drops = min(_int(stat.get("d")), attempts)
        if drops <= 0:
            continue
        items[item_id] = (drops, max(_int(stat.get("q")), drops))
    return items


def combine_drops(drop_tables):
    """Combines GoldScoutDB.drops from several accounts into one mob table."""
    mobs = {}
    for drops in drop_tables:
        for npc, entry in (drops or {}).items():
            if not isinstance(npc, int) or npc <= 0 or not isinstance(entry, dict):
                continue
            mob = mobs.setdefault(npc, {"k": 0, "p": 0, "lmin": 0, "lmax": 0, "n": "",
                                        "m": 0, "sx": 0.0, "sy": 0.0, "c": 0, "i": {}, "pi": {}})
            kills, picks = _int(entry.get("k")), _int(entry.get("p"))
            mob["k"] += kills
            mob["p"] += picks
            lmin, lmax = _int(entry.get("lmin")), _int(entry.get("lmax"))
            if lmin and lmax:
                mob["lmin"] = min(mob["lmin"] or lmin, lmin)
                mob["lmax"] = max(mob["lmax"], lmax)
            if entry.get("n") and not mob["n"]:
                mob["n"] = _clean_name(entry.get("n"))
            count = min(_int(entry.get("c")), kills)
            map_id = _int(entry.get("m"))
            if map_id and count and (not mob["m"] or mob["m"] == map_id or count > mob["c"]):
                if mob["m"] != map_id:
                    mob["m"], mob["sx"], mob["sy"], mob["c"] = map_id, 0.0, 0.0, 0
                mob["sx"] += float(entry.get("sx") or 0)
                mob["sy"] += float(entry.get("sy") or 0)
                mob["c"] += count
            for key, attempts in (("i", kills), ("pi", picks)):
                for item, (d, q) in _items(entry.get(key), attempts).items():
                    old = mob[key].get(item, (0, 0))
                    mob[key][item] = (old[0] + d, old[1] + q)
    return mobs


def export_text(mobs):
    """The export in the same format as /gscout export."""
    lines = ["GoldScout-export 1"]
    for npc in sorted(mobs):
        mob = mobs[npc]
        if mob["k"] + mob["p"] == 0:
            continue
        x = y = 0.0
        map_id, count = mob["m"], mob["c"]
        if map_id and count:
            x = min(max(mob["sx"] / count, 0.0), 1.0)
            y = min(max(mob["sy"] / count, 0.0), 1.0)
        else:
            map_id, count = 0, 0
        lmin, lmax = mob["lmin"], mob["lmax"]
        if not lmin or lmax - lmin > 15 or lmax > 63:
            lmin = lmax = 0

        def items(table):
            return ",".join("%d:%d:%d" % (item, d, q) for item, (d, q) in sorted(table.items()))
        lines.append("^".join([
            str(npc), str(mob["k"]), str(mob["p"]), str(lmin), str(lmax), str(map_id),
            "%.4f" % x, "%.4f" % y, str(count), mob["n"], items(mob["i"]), items(mob["pi"]),
        ]))
    return "\n".join(lines) + "\n"


def read_drops(path):
    """GoldScoutDB.drops from one SavedVariables file."""
    variables = parse_saved_variables(Path(path).read_text(encoding="utf-8", errors="replace"))
    database = variables.get("GoldScoutDB") or {}
    return database.get("drops") or {}
