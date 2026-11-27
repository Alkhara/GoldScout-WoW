#!/usr/bin/env python3
"""GitHub Actions helper for drop data submissions (issue form: data-submission.yml).

  python tools/data_bot.py check EVENT_JSON
      Validates the issue in a GitHub "issues" event. Writes comment.md and
      sets the step outputs "status" (valid, needs-review, invalid, skip).

  python tools/data_bot.py collect ISSUES_JSONL
      Takes open submission issues (one JSON object per line: number, body,
      user {id, login, type}, labels [names]), re-validates them and writes each
      contributor's newest accepted export per install to
      data/submissions/<user id>-<install ID>.txt.
      Writes pr_body.md and prints how many submissions it stored.

  python tools/data_bot.py collect-uploads UPLOADS_JSON
      Takes the upload service's admin listing ({"uploads": [...]}), runs the
      same checks, writes data/submissions/c-<install ID>.txt for each accepted
      companion upload, and appends a section to pr_body.md. Uploads with rate
      warnings are held unless their install ID is in data/approved-installs.txt.

  python tools/data_bot.py merged ISSUES_JSONL
      Prints the numbers of the issues (same format as collect) whose data main
      already has, one per line, so the data merge can close them.

Issue text is untrusted: it is only ever parsed here, never run or put into a
shell command, and messages never quote it back.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_data  # noqa: E402
import submission  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS = ROOT / "data" / "submissions"

EXPORT_HEADING = "### Your /gscout export"
TERMS_HEADING = "### Contributor terms"
REQUIRED_CONSENT = (
    "I collected this data myself by playing World of Warcraft with GoldScout.",
    "I agree to the GoldScout Contributor Terms, including the license they grant for this data.",
)
APPROVED_LABEL = "data-approved"
# Contributor Terms versions the companion may upload under.
TERMS_VERSIONS = {"2026-11-07"}
FORM_URL = "https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml"


def section(body, heading):
    start = body.find(heading)
    if start < 0:
        return None
    start += len(heading)
    end = body.find("\n### ", start)
    return body[start:] if end < 0 else body[start:end]


def extract(body):
    """Returns (export text, consent ok) from an issue form body."""
    body = (body or "").replace("\r", "")
    export = section(body, EXPORT_HEADING)
    if export is not None:
        export = export.strip()
        fence = re.match(r"^```[a-z]*\n(.*?)\n?```$", export, re.S)
        if fence:
            export = fence.group(1)
    terms = section(body, TERMS_HEADING) or ""
    checked = {line.strip()[6:].strip() for line in terms.split("\n")
               if line.strip().lower().startswith("- [x] ")}
    consent = all(text in checked for text in REQUIRED_CONSENT)
    return export, consent


def others(exclude_user_id=None, exclude_install=None):
    """Accepted exports from everyone except this contributor (by GitHub user
    ID for issue submissions, or by install ID for companion uploads)."""
    mobs = []
    for path in sorted(SUBMISSIONS.glob("*.txt")):
        if exclude_user_id is not None and path.stem.split("-")[0] == str(exclude_user_id):
            continue
        if exclude_install and path.stem.endswith("-" + exclude_install):
            continue
        result = submission.parse(path.read_text(encoding="utf-8"))
        if result.ok:
            mobs.append(result.mobs)
    return mobs


def quest_items():
    """Items any accepted export's item details call quest items (submission.QUEST_ITEM_CLASS): the rate
    comparison skips them, since a player not on the quest rightly never loots one."""
    found = set()
    for path in sorted(SUBMISSIONS.glob("*.txt")):
        result = submission.parse(path.read_text(encoding="utf-8"))
        if result.ok:
            found |= {item for item, meta in result.item_meta.items() if meta[1] == submission.QUEST_ITEM_CLASS}
    return found


def review(body, user_id):
    """Validates an issue body. Returns (status, result, consent, found_export)."""
    export, consent = extract(body)
    if export is None:
        return "invalid", None, consent, False
    result = submission.parse(export)
    if result.ok and len(export.encode("utf-8")) > submission.FORM_MAX_BYTES:
        result.errors.append("The export is larger than %d bytes, too big for the share form. GoldScout Companion "
                             "can share it." % submission.FORM_MAX_BYTES)
    if result.ok:
        submission.compare(result, others(user_id), quest_items())
    if not consent or not result.ok:
        return "invalid", result, consent, True
    return ("needs-review" if result.warnings else "valid"), result, consent, True


def set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s=%s\n" % (name, value))
    print("%s=%s" % (name, value))


def check(event_path):
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    user = issue.get("user") or {}
    if user.get("type") == "Bot" or issue.get("pull_request"):
        set_output("status", "skip")
        return
    status, result, consent, found = review(issue.get("body"), user.get("id"))

    lines = []
    if not found and submission.HEADER in (issue.get("body") or ""):
        lines.append("Thanks for sharing! It looks like this export was pasted into a regular issue. "
                     "Drop data has to come through the **[Share drop data](%s)** form, so the "
                     "Contributor Terms are agreed to. Please open the form, paste the same text into "
                     "it, tick both boxes and submit; this issue can then be closed." % FORM_URL)
    elif not found:
        lines.append("I couldn't find the export in this issue. Please use the **[Share drop data](%s)** "
                     "form and paste the whole `/gscout export` text into it." % FORM_URL)
    elif status == "invalid":
        lines.append("Thanks for sharing! This submission can't be accepted yet:")
        lines.append("")
        if not consent:
            lines.append("- Both Contributor terms boxes need to be ticked.")
        for error in (result.errors if result else [])[:20]:
            lines.append("- " + error)
        lines.append("")
        lines.append("Exports should be pasted exactly as `/gscout export` shows them. Edit this issue "
                     "to fix it and I'll check again.")
    elif status == "needs-review":
        lines.append("Thanks for sharing! Your export (%d mobs) is valid, but some drop rates differ "
                     "sharply from what other players recorded, so a maintainer will review it before "
                     "it's merged:" % len(result.mobs))
        lines.append("")
        for warning in result.warnings:
            lines.append("- " + warning)
    else:
        lines.append("Thanks for sharing! Your export (%d mobs) passed every check and will be included "
                     "in the next community data update." % len(result.mobs))
    lines.append("")
    lines.append("<sub>Checked automatically by GoldScout's data bot.</sub>")
    Path("comment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    set_output("status", status)


def collect(issues_path):
    # (user id, install ID) -> (snapshot, issue number, login, result). Each
    # export holds everything one WoW account's GoldScout has learned, so only
    # the newest snapshot per player and install is kept.
    latest = {}
    accepted = {}  # issue number -> (user id, install ID)
    for raw in Path(issues_path).read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        issue = json.loads(raw)
        user = issue.get("user") or {}
        user_id = user.get("id")
        if not isinstance(user_id, int) or user.get("type") == "Bot":
            continue
        status, result, _, _ = review(issue.get("body"), user_id)
        approved = APPROVED_LABEL in (issue.get("labels") or [])
        if status == "valid" or (status == "needs-review" and approved):
            number = issue["number"]
            key = (user_id, result.install_id)
            accepted[number] = key
            if key not in latest or (result.seq, number) > latest[key][:2]:
                latest[key] = (result.seq, number, user.get("login", "?"), result)
            print("accept #%d (%s)" % (number, status))
        else:
            print("skip #%d (%s)" % (issue.get("number", 0), status))

    SUBMISSIONS.mkdir(parents=True, exist_ok=True)
    # Files that no longer pass validation (for example the old export format)
    # are removed rather than left to be skipped forever.
    for path in sorted(SUBMISSIONS.glob("*.txt")):
        if not submission.parse(path.read_text(encoding="utf-8")).ok:
            print("remove %s (no longer valid)" % path.name)
            path.unlink()
    included = []
    for (user_id, install_id), (seq, number, login, result) in sorted(latest.items(), key=lambda p: p[1][1]):
        # Store the export rebuilt from the parsed data, never the raw issue text.
        path = SUBMISSIONS / ("%d-%s.txt" % (user_id, install_id))
        path.write_text(result.text(), encoding="utf-8", newline="\n")
        included.append((number, login, len(result.mobs), len(result.warnings)))

    body = ["Community drop data from player submissions. Each file in `data/submissions/` is one "
            "player's latest export, rebuilt from validated data; `GoldScout/Data_Community.lua` is "
            "regenerated from all of them.", ""]
    body += ["### Form submissions", ""]
    if included:
        body.append("| Issue | Player | Mobs | Rate warnings |")
        body.append("|---|---|---|---|")
        for number, login, mobs, warnings in included:
            body.append("| #%d | `%s` | %d | %d |" % (number, login, mobs, warnings))
    else:
        body.append("No new form submissions.")
    body.append("")
    # Every accepted issue is either included or replaced by a newer export
    # from the same player and install, so merging closes them all.
    for number in sorted(accepted):
        body.append("Closes #%d" % number)
    Path("pr_body.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    set_output("count", len(included))


def approved_installs():
    """Install IDs a maintainer accepted despite rate warnings (one per line)."""
    path = ROOT / "data" / "approved-installs.txt"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def held_installs():
    """Install IDs a maintainer wants reviewed every time, even when their rates look fine: one taken back out
    after it was accepted without review (delete its data/submissions/c-<install ID>.txt as well)."""
    path = ROOT / "data" / "held-installs.txt"
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


# An upload whose rates differ sharply from everyone else's goes in without review when what stands out is
# small: at most AUTO_ACCEPT_RATES such rates, none of which taking it in moves by more than AUTO_ACCEPT_SHIFT
# (half a percentage point). Every upload held for rates up to then (11, all approved by hand) was one item
# dropping about twice in a few dozen kills: a lucky streak among hundreds of players. Broken or made-up data
# shows as many odd rates, or rates that would move the community's, and those still wait for review.
AUTO_ACCEPT_RATES = 2
AUTO_ACCEPT_SHIFT = 0.005
ON_HELD_LIST = "on data/held-installs.txt, so every upload from it waits for review."


def rate_shift(outlier):
    """(before, after): the community's rate for an Outlier without this player's data, and with it (counting
    at most merge_data.MAX_PER_PLAYER of their attempts, as the merge does)."""
    scale = min(1.0, merge_data.MAX_PER_PLAYER / outlier.attempts)
    before = outlier.theirs / outlier.other_attempts
    after = (outlier.theirs + outlier.drops * scale) / (outlier.other_attempts + outlier.attempts * scale)
    return before, after


def small_differences(result):
    """True when compare() flagged at most AUTO_ACCEPT_RATES rates and accepting moves none of them by more
    than AUTO_ACCEPT_SHIFT."""
    if not result.outliers or len(result.outliers) > AUTO_ACCEPT_RATES:
        return False
    return all(abs(after - before) <= AUTO_ACCEPT_SHIFT for before, after in map(rate_shift, result.outliers))


def describe_shift(outlier):
    before, after = rate_shift(outlier)
    return "NPC %d, item %d: %d in %d against %.2f%% from everyone else; the rate goes to %.2f%%" % (
        outlier.npc, outlier.item, outlier.drops, outlier.attempts, 100 * before, 100 * after)


FORM_TAKEOVER = ("first shared through the GitHub form, and install IDs from the form are public, so this upload "
                 "waits in case someone else registered it. If that player switched to the companion, approve it.")


def form_installs():
    """Install IDs with a GitHub form submission (data/submissions/<user ID>-<install>.txt)."""
    return {path.stem.split("-", 1)[1] for path in SUBMISSIONS.glob("*.txt")
            if not path.name.startswith("c-") and "-" in path.stem}


def record_install_dates(dates):
    """Adds when each new install was first registered on the upload service to data/install-dates.json,
    which tools/merge_data.py reads for its probation of new installs. Existing entries are kept."""
    path = SUBMISSIONS.parent / merge_data.INSTALL_DATES_NAME
    current = merge_data.install_dates(path)
    added = {install: when for install, when in dates.items() if install not in current}
    if added:
        current.update(added)
        path.write_text(json.dumps(dict(sorted(current.items())), indent=0) + "\n", encoding="utf-8", newline="\n")


def collect_uploads(uploads_path):
    """Adds companion uploads (the upload service's admin listing, JSON) to
    data/submissions/c-<install ID>.txt, with the same checks as issues, and
    appends a section about them to pr_body.md. An upload is held for review
    (left out until its install ID is in data/approved-installs.txt) when its
    rates differ sharply from other players', or when it's the first companion
    upload for an install first shared through the form (FORM_TAKEOVER).

    It scales with players: every accepted file is read and added up once
    (submission.tally), each check takes that player's own share back out,
    and an upload whose snapshot is already stored is skipped before any
    check (so its body needn't be in the listing at all; see
    tools/fetch_uploads.py)."""
    listing = json.loads(Path(uploads_path).read_text(encoding="utf-8") or "{}")
    approved = approved_installs()
    always_held = held_installs()
    SUBMISSIONS.mkdir(parents=True, exist_ok=True)
    from_form = form_installs()
    files = {}
    for path in sorted(SUBMISSIONS.glob("*.txt")):
        parsed = submission.parse(path.read_text(encoding="utf-8"))
        if parsed.ok:
            files[path] = parsed
    totals = submission.tally(parsed.mobs for parsed in files.values())
    quests = {item for parsed in files.values() for item, meta in parsed.item_meta.items()
              if meta[1] == submission.QUEST_ITEM_CLASS}
    stored_seq = {path.stem[2:]: parsed.seq for path, parsed in files.items() if path.name.startswith("c-")}
    stored, held, auto, rejected, dates = [], [], [], 0, {}
    for upload in listing.get("uploads") or []:
        install = str(upload.get("install_id", ""))
        seq = upload.get("seq")
        if install in stored_seq and isinstance(seq, int) and seq <= stored_seq[install]:
            if isinstance(upload.get("created_at"), int):   # already stored by an earlier run
                dates[install] = upload["created_at"]
            continue
        if "body" not in upload:
            print("skip upload %s: not in this listing" % install[:12])
            continue
        result = submission.parse(str(upload.get("body", "")))
        if not result.ok or result.install_id != install or upload.get("terms") not in TERMS_VERSIONS:
            rejected += 1
            print("reject upload %s" % install[:12])
            continue
        path = SUBMISSIONS / ("c-%s.txt" % install)
        if not result.mobs and not result.fishing:
            # Only a pickpocketer's dungeon mobs from before export version 8, which aren't shared.
            print("skip upload %s: nothing to share yet" % install[:12])
            continue
        if install in always_held and install not in approved:
            held.append((install, len(result.mobs), [ON_HELD_LIST]))
            print("hold upload %s (on the held list)" % install)
            continue
        if install in from_form and not path.exists() and install not in approved:
            held.append((install, len(result.mobs), [FORM_TAKEOVER]))
            print("hold upload %s (first shared through the form)" % install)
            continue
        own = [parsed.mobs for path, parsed in files.items() if path.stem.endswith("-" + install)]
        submission.compare(result, None, quests, totals=totals, minus=submission.tally(own))
        lucky = bool(result.warnings) and install not in approved
        if lucky and not small_differences(result):
            held.append((install, len(result.mobs), result.warnings))
            print("hold upload %s (rate warnings)" % install)
            continue
        if isinstance(upload.get("created_at"), int):
            dates[install] = upload["created_at"]
        if path.exists():
            current = submission.parse(path.read_text(encoding="utf-8"))
            if current.ok and current.seq >= result.seq:
                continue
        path.write_text(result.text(), encoding="utf-8", newline="\n")
        stored.append((install, result.seq, len(result.mobs), len(result.warnings)))
        if lucky:
            auto.append((install, len(result.mobs), result.outliers))
        print("store upload %s snapshot %d%s%s" % (install, result.seq, " (small rate differences)" if lucky else "",
                                                 " (left out NPC %s: overfull corpses)"
                                                 % ", ".join(map(str, result.overfull)) if result.overfull else ""))
    record_install_dates(dates)

    body = ["", "### Companion uploads", ""]
    if stored:
        body += ["| Install | Snapshot | Mobs | Rate warnings |", "|---|---|---|---|"]
        body += ["| `%s` | %d | %d | %d |" % row for row in stored]
    else:
        body.append("No new companion uploads.")
    if auto:   # before the held list: tools/admin_stats.py counts the "- `" lines after "Held back for review"
        body += ["", "Accepted without review: each differs sharply from other players on at most %d rates, and "
                 "moves none by more than %.1f points. To take one back out, add its install ID to "
                 "`data/held-installs.txt` and delete its `data/submissions/c-<install ID>.txt`:"
                 % (AUTO_ACCEPT_RATES, 100 * AUTO_ACCEPT_SHIFT), ""]
        for install, mobs, outliers in auto:
            body.append("- `%s` (%d mobs): %s." % (install, mobs, "; ".join(map(describe_shift, outliers))))
    if held:
        body += ["", "Held back for review, and left out until accepted. To accept one, add its install ID to "
                 "`data/approved-installs.txt` and run the workflow again:", ""]
        for install, mobs, warnings in held:
            body.append("- `%s` (%d mobs): %s" % (install, mobs, "; ".join(warnings[:3])))
    if rejected:
        body += ["", "%d upload(s) failed validation and were skipped." % rejected]
    with open("pr_body.md", "a", encoding="utf-8") as handle:
        handle.write("\n".join(body) + "\n")
    set_output("uploads", len(stored))
    set_output("held", len(held))
    set_output("accepted_unreviewed", len(auto))
    set_output("rejected", rejected)


def main_file(path, ref="origin/main"):
    """A file's text on main (fetched), or None if main doesn't have it."""
    try:
        return subprocess.run(["git", "show", "%s:%s" % (ref, path.relative_to(ROOT).as_posix())], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def merged(issues_path, read=main_file):
    """Prints the open share-form issues whose data main already has: the same player's file for that install,
    at the same or a newer export. The data merge closes them: GitHub ignores "Closes #N" in a pull request
    merged with the workflow's own token, so they'd otherwise stay open."""
    found = []
    for line in Path(issues_path).read_text(encoding="utf-8").splitlines():
        issue = json.loads(line)
        user_id = (issue.get("user") or {}).get("id")
        export, _ = extract(issue.get("body"))
        result = submission.parse(export) if export else None
        if not isinstance(user_id, int) or not result or not result.ok:
            continue
        stored = read(SUBMISSIONS / ("%d-%s.txt" % (user_id, result.install_id)))
        stored = submission.parse(stored) if stored else None
        if stored and stored.ok and stored.seq >= result.seq:
            found.append(issue["number"])
    for number in sorted(found):
        print(number)


def main():
    commands = {"check": check, "collect": collect, "collect-uploads": collect_uploads, "merged": merged}
    if len(sys.argv) != 3 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]](sys.argv[2])


if __name__ == "__main__":
    main()
