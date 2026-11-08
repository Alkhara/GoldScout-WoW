#!/usr/bin/env python3
"""Checks a GoldScout release, or that the upload server is ready for one.

  python tools/verify_release.py assets DIR vX.Y.Z
      DIR holds the release's downloaded files. Checks the addon zip is there,
      its TOC version is the tag, every file the TOC lists is in the zip, and
      the companion exe is there (and signed, when checked on Windows).

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
    version = re.search(r"^## Version:\s*(\S+)", toc, re.M)
    if not version or version.group(1) != tag:
        fail("TOC version is %r, expected %s" % (version and version.group(1), tag))
    listed = [line.strip() for line in toc.splitlines() if line.strip().endswith(".lua")]
    missing = [name for name in listed if "GoldScout/" + name not in names]
    if missing:
        fail("files listed in the TOC are missing from the zip: %s" % ", ".join(missing))
    print("ok   %s: version %s, %d Lua files" % (zips[0].name, tag, len(listed)))

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


def export_version():
    source = (ROOT / "GoldScout" / "Learn.lua").read_text(encoding="utf-8")
    match = re.search(r"GoldScout%-export (\d+)|\"GoldScout-export (\d+)\^", source)
    if not match:
        fail("can't find the export version in Learn.lua")
    return int(match.group(1) or match.group(2))


def check_server(url=DEFAULT_SERVER):
    version = export_version()
    body = ("GoldScout-export %d^probeprobepr^1\n@q^1^x\n" % version).encode("utf-8")
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
