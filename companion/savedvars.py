"""Reads GoldScout's SavedVariables and builds a drop data export from them.

The companion only ever reads these files. (The one thing it writes in the WoW
folder is the GoldScout_Prices data addon; see auction_prices.py.)
"""
import re
import string
import sys

REGIONS = ("us", "eu", "kr", "tw", "cn")
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


def mac_roots(home=None):
    """Where Battle.net installs World of Warcraft on a Mac."""
    home = Path(home or Path.home())
    return [Path("/Applications/World of Warcraft"), home / "Applications" / "World of Warcraft"]


def find_forever_folders():
    """Every WoW Forever folder (the _forever_ directory) found on this computer."""
    candidates = list(_registry_roots())
    if sys.platform == "darwin":
        candidates += mac_roots()
    else:
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
# Reading GoldScout's data
# ---------------------------------------------------------------------------
class Account:
    """One WoW account's GoldScout data: its install ID and latest export.

    The addon writes each export as a numbered snapshot (GoldScoutDB.exports)
    when you log out, /reload or use /gscout export. The companion shares that
    exact text, so the community data can record which snapshot it includes.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.parent.parent.name  # the WTF\Account\<name> folder
        variables = parse_saved_variables(self.path.read_text(encoding="utf-8", errors="replace"))
        database = variables.get("GoldScoutDB") or {}
        self.install_id = database.get("installID")
        exports = database.get("exports") or {}
        self.seq = exports.get("seq") if isinstance(exports.get("seq"), int) else 0
        self.export = (exports.get("list") or {}).get(self.seq)
        drops = database.get("drops") or {}
        self.has_loot = any(isinstance(entry, dict) and (entry.get("k") or entry.get("p"))
                            for entry in drops.values())
        # Your own auction house scans and the realms you've played, so the
        # companion knows which auction houses' prices to fetch for you.
        self.markets = database.get("markets") if isinstance(database.get("markets"), dict) else {}
        self.seen_markets = database.get("seenMarkets") if isinstance(database.get("seenMarkets"), dict) else {}
        regions = database.get("marketRegions")
        self.market_regions = regions if isinstance(regions, dict) else {}

    @property
    def region(self):
        """The region ("us", "eu", "kr", "tw" or "cn") of the realm this WoW
        account played most recently, as GoldScout recorded it, or None."""
        known = [(self.seen_markets.get(key) if isinstance(self.seen_markets.get(key), (int, float)) else 0, region)
                 for key, region in self.market_regions.items() if region in REGIONS]
        return max(known)[1] if known else None


def read_accounts(forever):
    return [Account(path) for path in saved_variables_files(forever)]
