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

Issue text is untrusted: it is only ever parsed here, never run or put into a
shell command, and messages never quote it back.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
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


def others(exclude_user_id):
    """Accepted exports from everyone except this contributor."""
    mobs = []
    for path in sorted(SUBMISSIONS.glob("*.txt")):
        if path.stem.split("-")[0] == str(exclude_user_id):
            continue
        result = submission.parse(path.read_text(encoding="utf-8"))
        if result.ok:
            mobs.append(result.mobs)
    return mobs


def review(body, user_id):
    """Validates an issue body. Returns (status, result, consent, found_export)."""
    export, consent = extract(body)
    if export is None:
        return "invalid", None, consent, False
    result = submission.parse(export)
    if result.ok:
        submission.compare(result, others(user_id))
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
    body.append("| Issue | Player | Mobs | Rate warnings |")
    body.append("|---|---|---|---|")
    for number, login, mobs, warnings in included:
        body.append("| #%d | `%s` | %d | %d |" % (number, login, mobs, warnings))
    body.append("")
    # Every accepted issue is either included or replaced by a newer export
    # from the same player and install, so merging closes them all.
    for number in sorted(accepted):
        body.append("Closes #%d" % number)
    Path("pr_body.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    set_output("count", len(included))


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "collect"):
        sys.exit(__doc__)
    if sys.argv[1] == "check":
        check(sys.argv[2])
    else:
        collect(sys.argv[2])


if __name__ == "__main__":
    main()
