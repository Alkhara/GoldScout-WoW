#!/usr/bin/env python3
"""Runs every check GoldScout's code must pass. CI runs it on every push, and
the pre-push hook (tools/hooks/pre-push) runs it before anything is pushed.

  python tools/check.py

Checks, in order:
  1. Lua syntax of the addon (tools/luacheck_lite.py)
  2. Python lint with pyflakes (skipped with a warning if it isn't installed)
  3. Every file in data/submissions/ passes the export validator
  4. All tests (the Lua tests need lupa; without it they're skipped)

To get everything locally: pip install pyflakes lupa
"""
import glob
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_PATHS = ["companion", "tools", "tests", "site"]


def run(title, command):
    print("== %s" % title, flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print("!! %s failed" % title, flush=True)
    return result.returncode == 0


def has_module(name):
    return subprocess.run([sys.executable, "-c", "import %s" % name], cwd=ROOT,
                          capture_output=True).returncode == 0


def check_submissions():
    print("== Community data files", flush=True)
    sys.path.insert(0, str(ROOT / "tools"))
    import submission
    bad = 0
    files = sorted((ROOT / "data" / "submissions").glob("*.txt"))
    for path in files:
        for error in submission.parse(path.read_text(encoding="utf-8")).errors:
            print("%s: %s" % (path.name, error))
            bad += 1
    print("%d file(s) checked" % len(files))
    if bad:
        print("!! Community data files failed")
    return bad == 0


def main():
    lua_files = sorted(glob.glob(str(ROOT / "GoldScout" / "*.lua")))
    results = [run("Lua syntax", [sys.executable, str(ROOT / "tools" / "luacheck_lite.py"), *lua_files])]
    if has_module("pyflakes"):
        py_files = [str(p) for d in PYTHON_PATHS for p in sorted((ROOT / d).glob("*.py"))]
        results.append(run("Python lint", [sys.executable, "-m", "pyflakes", *py_files]))
    else:
        print("== Python lint skipped: pip install pyflakes")
    results.append(check_submissions())
    if not has_module("lupa"):
        print("   (lupa isn't installed, so the Lua tests will be skipped: pip install lupa)")
    results.append(run("Tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]))
    if all(results):
        print("All checks passed.")
        return 0
    print("Some checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
