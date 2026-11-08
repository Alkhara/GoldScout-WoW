#!/usr/bin/env python3
"""Prints the errors GoldScout recorded in its saved data (its own Lua errors
and actions the game blocked), with their stacks.

  python tools/errors.py            every WoW account on this PC
  python tools/errors.py --forever "D:\\Games\\World of Warcraft\\_forever_"

WoW writes saved data when you log out or /reload, so new errors show up here
after that.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
import savedvars  # noqa: E402


def forever_folder(explicit):
    if explicit:
        return savedvars.normalize_wow_folder(explicit)
    local = ROOT / ".addons-path"
    if local.is_file():
        found = savedvars.normalize_wow_folder(local.read_text(encoding="utf-8").strip())
        if found:
            return found
    folders = savedvars.find_forever_folders()
    return folders[0] if folders else None


def main():
    parser = argparse.ArgumentParser(description="Show GoldScout's recorded errors.")
    parser.add_argument("--forever", help="the WoW Forever folder (_forever_)")
    args = parser.parse_args()
    forever = forever_folder(args.forever)
    if not forever:
        sys.exit("WoW Forever folder not found; pass --forever.")
    files = savedvars.saved_variables_files(forever)
    if not files:
        sys.exit("No GoldScout saved data under %s" % forever)
    total = 0
    for path in files:
        database = savedvars.parse_saved_variables(path.read_text(encoding="utf-8", errors="replace"))
        errors = (database.get("GoldScoutDB") or {}).get("errors") or {}
        entries = [errors[i] for i in sorted(errors)] if isinstance(errors, dict) else list(errors)
        print("== %s (saved %s): %d error(s)" % (path.parent.parent.name,
              time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime)), len(entries)))
        for entry in entries:
            total += 1
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.get("t") or 0))
            print("\n[%s] x%d  version %s" % (when, entry.get("n") or 1, entry.get("v") or "?"))
            print(entry.get("m") or "?")
            stack = (entry.get("s") or "").strip()
            if stack:
                print("  " + stack.replace("\n", "\n  "))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
