#!/usr/bin/env python3
"""GoldScout's CurseForge description, kept current with every release.

  python tools/store_page.py check v1.2.3   fail unless it's reviewed for v1.2.3 and ready to paste

docs/curseforge-description.md is the description itself: the whole file is
pasted into CurseForge's description editor by hand, since CurseForge's API
can't change a project's description. docs/store-page.md holds the rest of
the page and the version the description was last brought up to date for
("**Description reviewed for:** v1.2.3"). tools/release.py checks both before
a hand-made release, and says afterwards whether there's a new copy to paste.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = ROOT / "docs" / "curseforge-description.md"
PAGE = ROOT / "docs" / "store-page.md"
REVIEWED = re.compile(r"^\*\*Description reviewed for:\*\* (v\d+\.\d+\.\d+)\s*$", re.M)
LINKS_HEADING = "### Links"


def reviewed(page=None):
    """The version the description was last reviewed for, or None."""
    match = REVIEWED.search(page if page is not None else PAGE.read_text(encoding="utf-8"))
    return match and match.group(1)


def problems(description=None):
    """What would stop the description being pasted as it is: a list of problems (empty when it's ready)."""
    text = description if description is not None else DESCRIPTION.read_text(encoding="utf-8")
    found = []
    if text.lstrip().startswith("# "):
        found.append("it starts with a page title; the description starts with its own text")
    if "<!--" in text:
        found.append("it has an HTML comment, which CurseForge would show")
    if LINKS_HEADING not in text:
        found.append("it has no %r section at the end" % LINKS_HEADING)
    else:
        body = text.split(LINKS_HEADING, 1)[0]
        if re.search(r"https?://", body):
            found.append("it links to a website before %r (CurseForge wants outside links at the bottom)"
                         % LINKS_HEADING)
    if re.search(r"https?://\S+\.(exe|zip|dmg)\b", text, re.I):
        found.append("it links straight to a download (CurseForge doesn't allow files hosted elsewhere)")
    if re.search(r"\bwago\b", text, re.I):
        found.append("it mentions Wago, where GoldScout isn't listed any more")
    if re.search(r"\bfree\b", text, re.I):
        found.append("it says \"free\" (left out of GoldScout's promotional text)")
    return found


def check(tag, page=None, description=None):
    """None if the description is reviewed for tag and ready to paste, else the problem."""
    version = reviewed(page)
    if version != tag:
        return ("docs/store-page.md: the CurseForge description was last reviewed for %s; bring "
                "docs/curseforge-description.md up to date with %s's changes, then set "
                "\"**Description reviewed for:** %s\"" % (version or "no version", tag, tag))
    found = problems(description)
    if found:
        return "docs/curseforge-description.md: " + "; ".join(found)
    return None


def changed_since(tag):
    """True if the description file changed since the release tag (so there's a new copy to paste)."""
    result = subprocess.run(["git", "diff", "--quiet", tag, "HEAD", "--", str(DESCRIPTION.relative_to(ROOT))],
                            cwd=ROOT)
    return result.returncode != 0


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "check":
        sys.exit(__doc__)
    problem = check(sys.argv[2])
    if problem:
        sys.exit("FAIL: " + problem)
    print("ok   the CurseForge description is reviewed for %s and ready to paste" % sys.argv[2])


if __name__ == "__main__":
    main()
