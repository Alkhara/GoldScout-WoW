#!/usr/bin/env python3
"""Releases GoldScout in one command, with every safety check.

  python tools/release.py v0.5.5            release main's current commit
  python tools/release.py --verify v0.5.4   only check an existing release

Steps: main is clean and matches origin; the CurseForge description is
reviewed for this version (tools/store_page.py); Tests passed on GitHub for this exact
commit; the upload server accepts this build's export format; tag and push;
follow the Release workflow; download the release and verify it (zip version
and contents, companion signature). Stops at the first problem.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "Alkhara/GoldScout-WoW"
API = "https://api.github.com/repos/" + REPO
sys.path.insert(0, str(ROOT / "tools"))
import announce  # noqa: E402
import changelog  # noqa: E402
import store_page  # noqa: E402
import verify_release  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def api(path):
    request = urllib.request.Request(API + path, headers={"User-Agent": "GoldScout-release"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def say(message):
    print(message, flush=True)


def wait(what, check, timeout=900, every=15):
    """Calls check() until it returns a value other than None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = check()
        if result is not None:
            return result
        time.sleep(every)
    verify_release.fail("timed out waiting for " + what)


def version_key(tag):
    return tuple(int(part) for part in tag[1:].split("."))


def preflight(tag):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        verify_release.fail("version must look like v1.2.3")
    git("fetch", "--quiet", "--tags", "origin")
    tags = [t for t in git("tag", "--list", "v*").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    if tag in tags:
        verify_release.fail("%s already exists" % tag)
    latest = max(tags, key=version_key) if tags else None
    if latest and version_key(tag) <= version_key(latest):
        verify_release.fail("%s isn't newer than the latest release %s" % (tag, latest))
    app = (ROOT / "companion" / "app.py").read_text(encoding="utf-8")
    companion = re.search(r'^VERSION = "([^"]+)"', app, re.M)
    if not companion or "v" + companion.group(1) != tag:
        verify_release.fail("companion/app.py VERSION is %r; set it to %s first"
                            % (companion and companion.group(1), tag[1:]))
    problem = changelog.check(tag)
    if problem:
        verify_release.fail(problem)
    # The notes go out on GitHub, CurseForge and Discord: a security fix is "Security fix", never its details.
    words = announce.sensitive(changelog.sections(changelog.CHANGELOG.read_text(encoding="utf-8")).get(tag, ""))
    if words:
        verify_release.fail("CHANGELOG.md %s says too much about a security problem (%s): write \"Security fix\" "
                            "instead" % (tag, ", ".join(words)))
    problem = store_page.check(tag)
    if problem:
        verify_release.fail(problem)
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        verify_release.fail("not on main")
    if git("status", "--porcelain", "--untracked-files=no"):
        verify_release.fail("uncommitted changes")
    head = git("rev-parse", "HEAD")
    if head != git("rev-parse", "origin/main"):
        verify_release.fail("main isn't the same as origin/main; push or pull first")
    say("ok   main %s is clean and pushed (latest release %s)" % (head[:7], latest))
    return head, latest


def paste_reminder(latest):
    """Whether the CurseForge description needs pasting again after this release."""
    if latest and not store_page.changed_since(latest):
        say("ok   the CurseForge description hasn't changed since %s: nothing to paste" % latest)
    else:
        say("**   the CurseForge description changed: open docs/curseforge-description.md, copy it all and "
            "paste it into the project's description on CurseForge")


def tests_passed(head):
    def check():
        runs = api("/actions/workflows/tests.yml/runs?branch=main&per_page=20")["workflow_runs"]
        mine = [r for r in runs if r["head_sha"] == head]
        if not mine:
            return None
        run = mine[0]
        if run["status"] != "completed":
            return None
        return run["conclusion"]
    say("..   waiting for Tests on %s" % head[:7])
    result = wait("Tests", check)
    if result != "success":
        verify_release.fail("Tests ended as %s on %s" % (result, head[:7]))
    say("ok   Tests passed on %s" % head[:7])


def follow_release(tag):
    def check():
        runs = api("/actions/workflows/release.yml/runs?per_page=10")["workflow_runs"]
        mine = [r for r in runs if r["head_branch"] == tag]
        if not mine or mine[0]["status"] != "completed":
            return None
        return mine[0]
    say("..   waiting for the Release workflow")
    run = wait("the Release workflow", check, timeout=1500)
    jobs = api("/actions/runs/%d/jobs" % run["id"])["jobs"]
    for job in jobs:
        say("     job %-10s %s" % (job["name"], job["conclusion"]))
    if run["conclusion"] != "success":
        verify_release.fail("Release ended as %s: %s" % (run["conclusion"], run["html_url"]))
    say("ok   Release workflow passed")


def verify(tag):
    release = api("/releases/tags/" + tag)
    with tempfile.TemporaryDirectory() as folder:
        for asset in release.get("assets", []):
            if asset["name"].endswith((".zip", ".exe")):
                request = urllib.request.Request(asset["browser_download_url"],
                                                 headers={"User-Agent": "GoldScout-release"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    (Path(folder) / asset["name"]).write_bytes(response.read())
        verify_release.check_assets(folder, tag)
    say("ok   %s verified: %s" % (tag, release.get("html_url")))


def main():
    parser = argparse.ArgumentParser(description="Release GoldScout with every check.")
    parser.add_argument("version", help="for example v0.5.5")
    parser.add_argument("--verify", action="store_true", help="only verify an existing release")
    args = parser.parse_args()
    if args.verify:
        verify(args.version)
        return
    head, latest = preflight(args.version)
    tests_passed(head)
    verify_release.check_server()
    git("tag", "-a", args.version, "-m", "GoldScout " + args.version)
    git("push", "origin", args.version)
    say("ok   tagged and pushed %s" % args.version)
    follow_release(args.version)
    verify(args.version)
    paste_reminder(latest)
    say("Done. CurseForge lists the new file after its own processing.")


if __name__ == "__main__":
    main()
