#!/usr/bin/env python3
"""Announces a GoldScout release on Discord: the version, where to get it, and its patch notes.

  python tools/announce.py v1.2.3            posts to the webhook in DISCORD_ANNOUNCE_WEBHOOK
  python tools/announce.py v1.2.3 --dry-run  prints the message instead

The release workflow runs this after a release is published and verified. Only hand-made releases are
announced (a "## v1.2.3" section in CHANGELOG.md); the daily data releases, which only ship fresh drop data
and prices, aren't, so the channel isn't a daily feed.

Patch notes are public, so they never spell out a security problem: a fix is "Security fix" or "Security and
stability fixes", never what leaked, what could be bypassed or how. sensitive() spots wording that does;
tools/release.py refuses to release with it and the tests check every section of CHANGELOG.md, and if any
slipped through, the announcement replaces those lines with "Security and stability fixes." The message
never pings anyone (allowed_mentions is empty), whatever the notes say.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import changelog  # noqa: E402

REPO = "https://github.com/Alkhara/GoldScout-WoW"
CURSEFORGE = "https://www.curseforge.com/projects/1790110"   # as on the website
COMPANION = "https://wowgoldscout.com/companion"
GOLD = 0xF2C255
MAX_DESCRIPTION = 3800      # Discord's limit for an embed description is 4096
SAFE_LINE = "- Security and stability fixes."
# Wording that says too much about a security problem. Notes say "Security fix" instead.
SENSITIVE = [
    r"passwords?", r"passwd", r"credentials?", r"secrets?", r"api keys?", r"private keys?", r"tokens?",
    r"leak(?:s|ed|ing)?", r"exploit(?:s|ed|able)?", r"vulnerab\w*", r"cve-\d+(?:-\d+)?", r"injection", r"xss", r"csrf",
    r"rce", r"remote code", r"bypass(?:es|ed)?", r"unauthori[sz]ed", r"privilege", r"escalat\w*",
    r"exposed", r"exposure", r"ip address(?:es)?", r"attacker", r"malicious", r"hijack\w*", r"impersonat\w*",
    r"steal\w*|stolen", r"brute.?force",
]
SENSITIVE_RE = re.compile(r"\b(?:%s)\b" % "|".join(SENSITIVE), re.I)


def sensitive(text):
    """The sensitive words in some patch notes, [] if they're fine to publish."""
    return sorted({match.group(0).lower() for match in SENSITIVE_RE.finditer(text or "")})


def bullets(body):
    """A section's text split into its top-level items (a "- " line and the lines continuing it)."""
    items, current = [], []
    for line in body.splitlines():
        if line.startswith("- ") and current:
            items.append("\n".join(current))
            current = []
        if line.strip() or current:
            current.append(line)
    if current:
        items.append("\n".join(current).rstrip())
    return items


def safe_notes(body):
    """The notes with any item that says too much about a security problem replaced (once)."""
    out, replaced = [], False
    for item in bullets(body):
        if sensitive(item):
            if not replaced:
                out.append(SAFE_LINE)
                replaced = True
            continue
        out.append(" ".join(part.strip() for part in item.splitlines()))
    return "\n".join(out)


def message(tag, text=None):
    """The Discord webhook payload for a release, or None for a release without its own notes."""
    notes = changelog.sections(text if text is not None else changelog.CHANGELOG.read_text(encoding="utf-8"))
    body = notes.get(tag)
    if not body:
        return None
    description = safe_notes(body)
    if len(description) > MAX_DESCRIPTION:
        cut = description[:MAX_DESCRIPTION].rsplit("\n", 1)[0]
        description = cut + "\n- ...and more: see the full notes on GitHub."
    release = "%s/releases/tag/%s" % (REPO, tag)
    return {
        "username": "GoldScout",
        "allowed_mentions": {"parse": []},     # never @everyone, @here, a role or a user, whatever the notes say
        "embeds": [{
            "title": "GoldScout %s is out" % tag,
            "url": release,
            "color": GOLD,
            "description": description,
            "fields": [{
                "name": "Get it",
                "value": "[CurseForge](%s), or update it in the CurseForge app. [GoldScout Companion](%s) offers "
                         "its own update. [Full notes](%s)" % (CURSEFORGE, COMPANION, release),
            }],
        }],
    }


def post(webhook, payload, opener=urllib.request.urlopen):
    request = urllib.request.Request(webhook, data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "GoldScout-release/1.0 (+%s)" % REPO})
    with opener(request, timeout=20) as response:
        return response.status


def main():
    args = sys.argv[1:]
    if not args or not re.fullmatch(r"v\d+\.\d+\.\d+", args[0]):
        sys.exit(__doc__)
    tag = args[0]
    payload = message(tag)
    if payload is None:
        print("%s is a data release with no notes of its own: not announced." % tag)
        return 0
    if "--dry-run" in args:
        sys.stdout.buffer.write(json.dumps(payload, indent=1, ensure_ascii=False).encode("utf-8") + b"\n")
        return 0
    import os
    webhook = os.environ.get("DISCORD_ANNOUNCE_WEBHOOK", "").strip()
    if not webhook:
        print("DISCORD_ANNOUNCE_WEBHOOK isn't set: %s wasn't announced." % tag)
        return 0
    try:
        status = post(webhook, payload)
    except OSError as error:          # urllib's HTTP and network errors; the webhook URL is never printed
        print("Couldn't post the announcement for %s (%s)." % (tag, type(error).__name__))
        return 1
    print("Announced %s on Discord (HTTP %d)." % (tag, status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
