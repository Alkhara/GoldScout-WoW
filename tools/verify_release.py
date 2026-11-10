#!/usr/bin/env python3
"""Checks a GoldScout release, or that the upload server is ready for one.

  python tools/verify_release.py assets DIR vX.Y.Z
      DIR holds the release's downloaded files. Checks the addon zip is there,
      its TOC version is the tag, every file the TOC lists is in the zip, it
      ships regional price estimates, and the companion exe is there (and
      signed, when checked on Windows), and the Mac app is in its zip when the
      release has one.

  python tools/verify_release.py server [URL]
      Checks the live upload server accepts the export version this addon
      writes (Learn.lua), so players' uploads won't be rejected. Sends a
      deliberately malformed export, so nothing is ever stored.

Exits 1 with a reason on the first problem.
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER = "https://goldscout-api.cawley22.workers.dev"
TERMS_VERSION = "2026-11-07"


def fail(message):
    print("FAIL: " + message)
    sys.exit(1)


def check_assets(folder, tag):
    folder = Path(folder)
    zips = sorted(folder.glob("GoldScout-%s*.zip" % tag))
    if not zips:
        fail("no GoldScout-%s*.zip in %s" % (tag, folder))
    with zipfile.ZipFile(zips[0]) as archive:
        names = set(archive.namelist())
        toc = archive.read("GoldScout/GoldScout.toc").decode("utf-8", "replace")
        bundled = archive.read("GoldScout/Data_Prices.lua").decode("utf-8", "replace") \
            if "GoldScout/Data_Prices.lua" in names else ""
    version = re.search(r"^## Version:\s*(\S+)", toc, re.M)
    if not version or version.group(1) != tag:
        fail("TOC version is %r, expected %s" % (version and version.group(1), tag))
    listed = [line.strip() for line in toc.splitlines() if line.strip().endswith(".lua")]
    missing = [name for name in listed if "GoldScout/" + name not in names]
    if missing:
        fail("files listed in the TOC are missing from the zip: %s" % ", ".join(missing))
    print("ok   %s: version %s, %d Lua files" % (zips[0].name, tag, len(listed)))
    regions = re.findall(r"^  (\w+) = \{ snapshot = \d+, houses = \d+, items = \"\d", bundled, re.M)
    if not regions:
        fail("Data_Prices.lua in the zip has no regional price estimates (the empty stub was packaged)")
    print("ok   regional price estimates for %s" % ", ".join(regions))

    exe = folder / "GoldScoutCompanion.exe"
    if not exe.is_file() or exe.stat().st_size < 1_000_000:
        fail("GoldScoutCompanion.exe is missing or too small")
    if sys.platform == "win32":
        status = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "(Get-AuthenticodeSignature '%s').Status" % exe],
            capture_output=True, text=True).stdout.strip()
        if status != "Valid":
            fail("companion signature is %r" % status)
        print("ok   GoldScoutCompanion.exe: signature Valid")
    else:
        print("ok   GoldScoutCompanion.exe present (%d MB); signature checked in the companion job"
              % (exe.stat().st_size // 1_000_000))

    # The Mac app is attached only once Apple signing is set up.
    mac = folder / "GoldScoutCompanion-macOS.zip"
    if mac.is_file():
        with zipfile.ZipFile(mac) as archive:
            names = archive.namelist()
        if "GoldScout Companion.app/Contents/MacOS/GoldScout Companion" not in names:
            fail("GoldScoutCompanion-macOS.zip doesn't contain GoldScout Companion.app")
        print("ok   GoldScoutCompanion-macOS.zip: the app is there; signing checked in the companion-mac job")


def export_version():
    source = (ROOT / "GoldScout" / "Learn.lua").read_text(encoding="utf-8")
    match = re.search(r"^local EXPORT_VERSION = (\d+)", source, re.M)
    if not match:
        fail("can't find EXPORT_VERSION in Learn.lua")
    return int(match.group(1))


def check_server(url=DEFAULT_SERVER):
    version = export_version()
    # A mob line with too few fields is malformed in every export version, so
    # the server rejects it before touching its database. (Never use an @ line
    # here: a later version may make it valid, and then the probe gets stored.)
    body = ("GoldScout-export %d^probeprobepr^1\nnot^a^mob^line\n" % version).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/v1/uploads", data=body, method="POST", headers={
        "Content-Type": "text/plain; charset=utf-8", "X-GoldScout-Terms": TERMS_VERSION,
        "User-Agent": "GoldScout-release-check"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            fail("the probe was accepted (HTTP %d); expected it to be rejected as malformed" % response.status)
    except urllib.error.HTTPError as error:
        message = json.loads(error.read() or b"{}").get("error", "")
    except (urllib.error.URLError, OSError) as error:
        fail("can't reach %s: %s" % (url, error))
    if "malformed" not in message.lower():
        fail("the server doesn't accept export version %d (it said: %s). Deploy the server first."
             % (version, message))
    print("ok   server at %s accepts export version %d" % (url, version))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "server":
        check_server(*sys.argv[2:3])
    elif len(sys.argv) == 4 and sys.argv[1] == "assets":
        check_assets(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
