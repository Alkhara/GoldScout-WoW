#!/usr/bin/env python3
"""Release notes from CHANGELOG.md.

  python tools/changelog.py notes v1.2.3     the notes for that release
  python tools/changelog.py check v1.2.3     fail unless CHANGELOG.md has them

A hand-made release needs its own "## v1.2.3" section (rename "Unreleased"
before releasing; tools/release.py checks). A weekly data release (tagged by
the Data release workflow without editing any file) has no section of its own:
its notes say it ships fresh price estimates and how much community data it
has, plus anything still under "Unreleased", since it ships main as it is.
The release workflow writes the notes to RELEASE_NOTES.md, which the packager
publishes on GitHub, CurseForge and Wago (.pkgmeta manual-changelog).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
COMMUNITY = ROOT / "GoldScout" / "Data_Community.lua"
HEADING = re.compile(r"^## (.+?)\s*$", re.M)


def sections(text):
    """{heading: body} for every "## heading" in the changelog."""
    found = {}
    matches = list(HEADING.finditer(text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end]
        body = re.split(r"^Older releases:", body, flags=re.M)[0]
        found[match.group(1).strip()] = body.strip()
    return found


def community_counts(path=COMMUNITY):
    """(mobs, contributors) in the community data file."""
    text = path.read_text(encoding="utf-8")
    community = text.split("ns.COMMUNITY_SOURCES", 1)
    mobs = len(re.findall(r"^  \[\d+\] = \{", community[0], re.M))
    contributors = len(re.findall(r'^  \["\w+"\] = \d+,', community[1], re.M)) if len(community) > 1 else 0
    return mobs, contributors


def notes(tag, text=None, counts=None):
    """The release notes for tag (markdown)."""
    found = sections(text if text is not None else CHANGELOG.read_text(encoding="utf-8"))
    if found.get(tag):
        return "## What's new in GoldScout %s\n\n%s\n" % (tag, found[tag])
    mobs, contributors = counts or community_counts()
    lines = ["## What's new in GoldScout %s" % tag, "",
             "- **Latest community drop data:** drop rates for %d mobs, shared by %d %s." % (
                 mobs, contributors, "player" if contributors == 1 else "players"),
             "- **Fresh regional price estimates,** so the Farm list works before you scan "
             "or install GoldScout Companion."]
    if found.get("Unreleased"):
        lines += ["", "Also in this release:", "", found["Unreleased"]]
    return "\n".join(lines) + "\n"


def check(tag, text=None):
    """None if the changelog has notes for tag, else the problem."""
    found = sections(text if text is not None else CHANGELOG.read_text(encoding="utf-8"))
    if found.get(tag):
        return None
    if found.get("Unreleased"):
        return "CHANGELOG.md: rename \"## Unreleased\" to \"## %s\" (its notes become the release notes)" % tag
    return "CHANGELOG.md has no \"## %s\" section: write what's new for players first" % tag


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("notes", "check"):
        sys.exit(__doc__)
    command, tag = sys.argv[1], sys.argv[2]
    if command == "notes":
        sys.stdout.buffer.write(notes(tag).encode("utf-8"))   # UTF-8 on every console
        return
    problem = check(tag)
    if problem:
        sys.exit("FAIL: " + problem)
    print("ok   CHANGELOG.md has notes for %s" % tag)


if __name__ == "__main__":
    main()
