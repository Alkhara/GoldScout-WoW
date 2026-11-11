"""Optional error reports: GoldScout's own Lua errors, sent to the GoldScout
server only when the player turns "Send error reports" on (off by default).

GoldScout keeps its errors in its saved data (GoldScoutDB.errors: message,
stack, count, time, addon version). Before anything is sent, each one is
cleaned on this PC: folder paths are removed, and the stack keeps only lines
from GoldScout's own files. A report carries a random reporter ID this
companion makes (not the install ID used for sharing), so the server can count
how many players hit an error without knowing who they are.
"""
import json
import re
import secrets
import urllib.error
import urllib.request

import uploader

MAX_ERRORS = 25
MAX_STACK_LINES = 12
SEND_EVERY = 30 * 60              # the server takes a report at most every 30 minutes
VERSION_RE = re.compile(r"^[0-9A-Za-z.@+-]{1,24}$")
ADDON_PATH = re.compile(r"(?:[A-Za-z]:/|/)[^\n\"']*?Interface/AddOns/")
DRIVE_PATH = re.compile(r"[A-Za-z]:/(?:[^/:\n]+/)*")
HOME_PATH = re.compile(r"/(?:Users|home)/[^/\n]+/")
FRAME = re.compile(r"AddOns/(GoldScout[^\"'\]:\n]*)[\"'\]]*:(\d+):?\s*(.*)")
ADDON_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")
# Before v0.11.1 every saved stack started with GoldScout's own error handler
# (Core.lua), so other addons' errors were saved as if they were GoldScout's.
HANDLER_FIXED = (0, 11, 1)


class ReportError(Exception):
    pass


def new_reporter_id():
    return secrets.token_hex(8)


def clean_message(text):
    text = str(text or "").replace("\\", "/")
    text = ADDON_PATH.sub("", text)          # "C:/.../Interface/AddOns/GoldScout/x.lua" -> "GoldScout/x.lua"
    text = re.sub(r"(?:Interface/)?AddOns/", "", text)
    text = DRIVE_PATH.sub("", text)          # any other folder path
    text = HOME_PATH.sub("~/", text)
    return " ".join(text.split())[:300]


def clean_stack(text):
    """GoldScout's own stack lines only, as "GoldScout/File.lua:123: in function 'X'"."""
    lines = []
    for line in str(text or "").replace("\\", "/").splitlines():
        match = FRAME.search(line)
        if match:
            rest = clean_message(match.group(3))[:150]
            lines.append(("%s:%s: %s" % (match.group(1), match.group(2), rest)).strip())
        if len(lines) >= MAX_STACK_LINES:
            break
    return "\n".join(lines)


def handler_first(version):
    """True if an addon of this version saved its error handler as each stack's first line."""
    match = ADDON_VERSION.match(version)
    return bool(match) and tuple(int(part) for part in match.groups()) < HANDLER_FIXED


def clean(entry):
    """One saved error as it's sent: {"m", "s", "n", "v"}, or None if there's nothing to send."""
    if not isinstance(entry, dict):
        return None
    message = clean_message(entry.get("m"))
    if not message:
        return None
    count = entry.get("n") if isinstance(entry.get("n"), int) and entry.get("n") > 0 else 1
    stack = clean_stack(entry.get("s"))
    version = str(entry.get("v") or "")
    if handler_first(version) and stack.startswith("GoldScout/Core.lua:"):
        stack = stack.partition("\n")[2]
        if not stack and "GoldScout/" not in message:
            return None                      # another addon's error, caught by GoldScout's handler
    report = {"m": message, "s": stack, "n": min(count, 1000000)}
    if VERSION_RE.match(version):
        report["v"] = version
    return report


def new_errors(accounts, since):
    """(cleaned errors newer than since, newest time among them) across WoW accounts."""
    found, newest = [], since
    for account in accounts:
        for entry in getattr(account, "errors", None) or []:
            when = entry.get("t") if isinstance(entry, dict) else None
            if not isinstance(when, (int, float)) or when <= since:
                continue
            report = clean(entry)
            if report:
                found.append((when, report))
                newest = max(newest, when)
    found.sort(key=lambda pair: -pair[0])
    return [report for _, report in found[:MAX_ERRORS]], newest


def send(reporter, errors, version, timeout=20):
    """Sends one report; returns the server's reply."""
    body = json.dumps({"reporter": reporter, "errors": errors}).encode("utf-8")
    request = urllib.request.Request(uploader.upload_url() + "/v1/errors", data=body, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": uploader.user_agent(version)})
    try:
        with uploader.open_url(request, timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        raise ReportError("The GoldScout server answered HTTP %d." % error.code)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ReportError("Couldn't reach the GoldScout server (%s)." % getattr(error, "reason", error))
