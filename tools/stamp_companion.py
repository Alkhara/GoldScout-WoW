#!/usr/bin/env python3
"""Sets the companion's VERSION to a release tag before it's built.

  python tools/stamp_companion.py v0.8.1

The release workflow runs this, so the built companion always reports the
version of the release it's attached to. Without it, a daily data release
(which tags the next patch version without changing any code) would ship a
companion that still reports the previous version, and every copy would keep
offering the same update.
"""
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "companion" / "app.py"
LINE = re.compile(r'^VERSION = "[^"]*"', re.M)


def stamp(text, tag):
    match = re.fullmatch(r"v?(\d+\.\d+\.\d+)", tag.strip())
    if not match:
        raise ValueError("not a release tag: %r" % tag)
    stamped, count = LINE.subn('VERSION = "%s"' % match.group(1), text, count=1)
    if count != 1:
        raise ValueError("no VERSION line in companion/app.py")
    return stamped


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    text = APP.read_text(encoding="utf-8")
    try:
        stamped = stamp(text, sys.argv[1])
    except ValueError as error:
        sys.exit(str(error))
    APP.write_text(stamped, encoding="utf-8", newline="")
    print(LINE.search(stamped).group(0))


if __name__ == "__main__":
    main()
