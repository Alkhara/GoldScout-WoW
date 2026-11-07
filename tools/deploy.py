#!/usr/bin/env python3
"""Check GoldScout's Lua files, then copy the addon into the WoW Forever AddOns folder.

The repository holds the development copy; the game loads a separate installed
copy. This script mirrors GoldScout/ into <AddOns>/GoldScout: it copies new and
changed files and removes files that no longer exist in the repository. It never
touches anything outside <AddOns>/GoldScout.

Usage:
  python tools/deploy.py              check the Lua, then deploy
  python tools/deploy.py --dry-run    show what would change, copy nothing
  python tools/deploy.py --addons PATH

The AddOns folder is, in order: --addons, the GOLDSCOUT_ADDONS environment
variable, the path in a .addons-path file at the repository root (git ignores
it), or the default Forever install location.
"""
import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ADDON = "GoldScout"
PERSONAL_ONLY = []  # files left out of public builds; keep in sync with .pkgmeta's ignore list
DEFAULT_ADDONS = r"C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns"


def default_addons(root):
    if os.environ.get("GOLDSCOUT_ADDONS"):
        return os.environ["GOLDSCOUT_ADDONS"]
    local = root / ".addons-path"
    if local.is_file():
        text = local.read_text(encoding="utf-8").strip()
        if text:
            return text
    return DEFAULT_ADDONS


def lint(root, source):
    lua_files = sorted(str(path) for path in source.glob("*.lua"))
    checker = root / "tools" / "luacheck_lite.py"
    result = subprocess.run([sys.executable, "-I", str(checker), *lua_files],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        return False
    print("Lua check passed for %d files." % len(lua_files))
    return True


def public_build(source, staging):
    """Copies the addon the way the release packager does: files listed in
    .pkgmeta's ignore list and #@do-not-package@ blocks in the .toc are left out."""
    shutil.copytree(source, staging)
    for name in PERSONAL_ONLY:
        (staging / name).unlink(missing_ok=True)
    toc = staging / (ADDON + ".toc")
    kept, skipping = [], False
    for line in toc.read_text(encoding="utf-8").splitlines():
        if line.strip() == "#@do-not-package@":
            skipping = True
        elif line.strip() == "#@end-do-not-package@":
            skipping = False
        elif not skipping:
            kept.append(line)
    toc.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return staging


def plan(source, target):
    """Works out which relative paths to copy, remove, or leave alone."""
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    target_files = set()
    if target.exists():
        target_files = {path.relative_to(target) for path in target.rglob("*") if path.is_file()}
    to_copy, unchanged = [], []
    for rel in sorted(source_files):
        dest = target / rel
        if dest.is_file() and filecmp.cmp(source / rel, dest, shallow=False):
            unchanged.append(rel)
        else:
            to_copy.append(rel)
    to_remove = sorted(target_files - source_files)
    return to_copy, to_remove, unchanged, target_files


def main():
    parser = argparse.ArgumentParser(description="Check and deploy the GoldScout addon.")
    parser.add_argument("--addons", default=default_addons(Path(__file__).resolve().parent.parent),
                        help="the WoW Forever Interface\\AddOns folder (default: %(default)s)")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without copying")
    parser.add_argument("--skip-lint", action="store_true", help="deploy without the Lua syntax check")
    parser.add_argument("--public", action="store_true",
                        help="deploy what a public release contains (files in PERSONAL_ONLY left out)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    source = root / ADDON
    if not (source / (ADDON + ".toc")).is_file():
        sys.exit("Can't find %s.toc in %s" % (ADDON, source))
    addons = Path(args.addons)
    if not addons.is_dir():
        sys.exit("AddOns folder not found: %s (use --addons or set GOLDSCOUT_ADDONS)" % addons)
    target = addons / ADDON

    if not args.skip_lint and not lint(root, source):
        sys.exit("Lua check failed; nothing was deployed.")

    if args.public:
        staging = Path(tempfile.mkdtemp(prefix="goldscout-public-"))
        source = public_build(source, staging / ADDON)
        print("Public build: personal-only files left out.")

    to_copy, to_remove, unchanged, existing = plan(source, target)
    verb_copy = "would copy" if args.dry_run else "copy"
    verb_remove = "would remove" if args.dry_run else "remove"
    for rel in to_copy:
        print("  %s %s" % (verb_copy, rel))
    for rel in to_remove:
        print("  %s %s" % (verb_remove, rel))
    if args.dry_run:
        print("Dry run for %s: %d to copy, %d to remove, %d unchanged."
              % (target, len(to_copy), len(to_remove), len(unchanged)))
        return

    for rel in to_copy:
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dest)
    for rel in to_remove:
        (target / rel).unlink()
    print("Deployed to %s: %d copied, %d removed, %d unchanged."
          % (target, len(to_copy), len(to_remove), len(unchanged)))

    new_files = [rel for rel in to_copy if rel not in existing]
    if new_files:
        print("New files were added, so restart the game fully; /reload won't load them.")
    elif to_copy or to_remove:
        print("Type /reload in game to load the changes.")


if __name__ == "__main__":
    main()
