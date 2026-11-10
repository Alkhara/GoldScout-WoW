"""Updates the companion in place, from the latest GitHub release.

  check()     asks GitHub for the latest release; returns an Update when it's
              newer than this copy and has a companion exe with a published
              SHA-256 hash.
  download()  saves the new exe next to the running one and checks its size
              and hash.
  verify_signature()  refuses any exe Windows doesn't call Valid, or that
              isn't signed by the GoldScout publisher. Our Azure Artifact
              Signing certificates last 3 days, so the publisher name is pinned,
              not a single certificate.
  verify_mac()  the macOS equivalent, after prepare() unpacks the zip: the app
              must pass codesign's strict check, be signed with a Developer ID
              from GoldScout's Apple team, and be accepted by Gatekeeper
              (which also means Apple notarized it).
  swap()      renames the running exe to GoldScoutCompanion.old.exe (Windows
              allows renaming a running exe, not overwriting it), or on macOS
              the app to GoldScout Companion.old.app, and moves the new one
              into its place; rollback() undoes that if the new copy
              doesn't start.

Nothing here runs a file that failed a check. The app (app.py) does the
handover: it starts the new copy and waits for it to take over.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

LATEST_URL = "https://api.github.com/repos/Alkhara/GoldScout-WoW/releases/latest"
RELEASES_PAGE = "https://github.com/Alkhara/GoldScout-WoW/releases/latest"
MAC = sys.platform == "darwin"
WINDOWS_ASSET = "GoldScoutCompanion.exe"
MAC_ASSET = "GoldScoutCompanion-macOS.zip"   # the signed, notarized app, zipped with ditto
APP_BUNDLE = "GoldScout Companion.app"
if MAC:
    ASSET = MAC_ASSET
    NEW_NAME = "GoldScout Companion.new.zip"
    OLD_NAME = "GoldScout Companion.old.app"
    FAILED_NAME = "GoldScout Companion.failed.app"
else:
    ASSET = WINDOWS_ASSET
    NEW_NAME = "GoldScoutCompanion.new.exe"
    OLD_NAME = "GoldScoutCompanion.old.exe"
    FAILED_NAME = "GoldScoutCompanion.failed.exe"
STAGE_NAME = "GoldScout Companion.new"   # macOS: where the downloaded zip is unpacked

# Who signs GoldScout releases (see notes on code signing). Both must match.
PUBLISHER_SUBJECT = ("CN=Chris Cawley", "O=Chris Cawley")
PUBLISHER_ISSUER = "Microsoft ID Verified CS"
# The Apple Developer Team ID that signs macOS releases. Until it's set, a Mac
# copy never installs an update (it opens the download page instead).
MAC_TEAM_ID = ""

MAX_SIZE = 200_000_000
CREATE_NO_WINDOW = 0x08000000


class UpdateError(Exception):
    pass


@dataclass
class Update:
    version: str        # "0.6.2"
    url: str            # the exe's download link
    size: int
    sha256: str
    page: str           # the release's page, for "What's new"


def parse_version(text):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def is_newer(candidate, current):
    new, old = parse_version(candidate), parse_version(current)
    return bool(new and old and new > old)


def fetch_json(url, version, timeout=20):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "GoldScoutCompanion/%s" % version})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check(current, fetch=fetch_json, asset_name=ASSET):
    """The newer release's companion, or None. Raises UpdateError when GitHub can't be asked."""
    try:
        release = fetch(LATEST_URL, current)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise UpdateError("Couldn't check for updates (%s)." % getattr(error, "reason", error))
    if release.get("draft") or release.get("prerelease"):
        return None
    version = (release.get("tag_name") or "").lstrip("v")
    if not is_newer(version, current):
        return None
    for asset in release.get("assets") or []:
        digest = asset.get("digest") or ""
        if asset.get("name") == asset_name and digest.startswith("sha256:") and asset.get("size"):
            return Update(version, asset["browser_download_url"], int(asset["size"]),
                          digest.split(":", 1)[1].lower(), release.get("html_url") or RELEASES_PAGE)
    return None   # no companion in that release (or no hash to check it against)


def download(update, folder, current_version, opener=urllib.request.urlopen, progress=None):
    """Saves the update as folder/GoldScoutCompanion.new.exe; checks size and hash."""
    if update.size > MAX_SIZE:
        raise UpdateError("The update is unexpectedly large.")
    target = Path(folder) / NEW_NAME
    digest = hashlib.sha256()
    received = 0
    request = urllib.request.Request(update.url, headers={"User-Agent": "GoldScoutCompanion/%s" % current_version})
    try:
        with opener(request, timeout=60) as response, open(target, "wb") as out:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > update.size:
                    raise UpdateError("The download is larger than the release says.")
                digest.update(chunk)
                out.write(chunk)
                if progress:
                    progress(received, update.size)
    except (urllib.error.URLError, OSError) as error:
        remove(target)
        raise UpdateError("The download failed (%s)." % getattr(error, "reason", error))
    except UpdateError:
        remove(target)
        raise
    if received != update.size or digest.hexdigest() != update.sha256:
        remove(target)
        raise UpdateError("The download didn't match the release, so it wasn't used.")
    return target


def read_signature(path):
    """Windows' verdict on a file's signature: {"status", "subject", "issuer"}."""
    script = ("$s = Get-AuthenticodeSignature -LiteralPath $env:GS_UPDATE_FILE; "
              "[pscustomobject]@{status = [string]$s.Status; "
              "subject = [string]$s.SignerCertificate.Subject; "
              "issuer = [string]$s.SignerCertificate.Issuer} | ConvertTo-Json -Compress")
    env = dict(os.environ, GS_UPDATE_FILE=str(path))
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, timeout=60, env=env,
                                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return json.loads(result.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise UpdateError("Couldn't check the update's signature (%s)." % error)


def verify_signature(path, reader=read_signature):
    info = reader(path)
    subject = [part.strip() for part in (info.get("subject") or "").split(",")]
    if info.get("status") != "Valid":
        raise UpdateError("The update isn't validly signed (%s), so it wasn't used." % (info.get("status") or "unknown"))
    if not all(part in subject for part in PUBLISHER_SUBJECT) or PUBLISHER_ISSUER not in (info.get("issuer") or ""):
        raise UpdateError("The update isn't signed by GoldScout's publisher, so it wasn't used.")


def can_install(team=None):
    """False on a Mac copy built before GoldScout had an Apple team to check against."""
    return not MAC or bool(MAC_TEAM_ID if team is None else team)


def prepare(downloaded, folder, run=subprocess.run):
    """What to verify and install: the exe itself on Windows; on macOS the app
    unpacked from the zip (the zip is deleted)."""
    if not MAC:
        return Path(downloaded)
    return unpack_mac(downloaded, folder, run)


def unpack_mac(archive, folder, run=subprocess.run):
    stage = Path(folder) / STAGE_NAME
    remove(stage)
    try:
        result = run(["/usr/bin/ditto", "-x", "-k", str(archive), str(stage)], capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as error:
        remove(stage)
        raise UpdateError("Couldn't unpack the update (%s)." % error)
    finally:
        remove(archive)
    app = stage / APP_BUNDLE
    found = sorted(p.name for p in stage.iterdir() if p.name != "__MACOSX") if stage.is_dir() else []
    if result.returncode != 0 or found != [APP_BUNDLE] or not app.is_dir():
        remove(stage)
        raise UpdateError("The update didn't contain the companion app, so it wasn't used.")
    return app


def _output(result):
    return (result.stdout or "") + (result.stderr or "")


def verify_mac(app, run=subprocess.run, team=None):
    """Refuses an app that isn't intact, signed by GoldScout's Apple team with a
    Developer ID, and accepted by Gatekeeper (signed and notarized)."""
    team = MAC_TEAM_ID if team is None else team
    if not team:
        raise UpdateError("This copy can't check macOS updates, so it wasn't used.")

    def ask(command):
        try:
            return run(command, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as error:
            raise UpdateError("Couldn't check the update's signature (%s)." % error)

    if ask(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)]).returncode != 0:
        raise UpdateError("The update isn't validly signed, so it wasn't used.")
    details = _output(ask(["/usr/bin/codesign", "-dv", "--verbose=2", str(app)])).splitlines()
    teams = [line.split("=", 1)[1].strip() for line in details if line.startswith("TeamIdentifier=")]
    authorities = [line.split("=", 1)[1].strip() for line in details if line.startswith("Authority=")]
    if teams != [team] or not authorities or not authorities[0].startswith("Developer ID Application:")             or not authorities[0].endswith("(%s)" % team):
        raise UpdateError("The update isn't signed by GoldScout's publisher, so it wasn't used.")
    if ask(["/usr/sbin/spctl", "--assess", "--type", "execute", str(app)]).returncode != 0:
        raise UpdateError("macOS didn't accept the update (it isn't notarized), so it wasn't used.")


def verify(path):
    """The signature check for this system."""
    if MAC:
        verify_mac(path)
    else:
        verify_signature(path)


def remove(path):
    path = Path(path)
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def can_write(folder):
    probe = Path(folder) / ".goldscout-write-test"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def swap(current, new):
    """Puts new where current is; current becomes OLD_NAME. Undoes itself on failure."""
    current, new = Path(current), Path(new)
    old = current.with_name(OLD_NAME)
    if old.exists() and not remove(old):
        raise UpdateError("An earlier update is still being cleaned up; try again in a minute.")
    try:
        current.rename(old)
    except OSError as error:
        raise UpdateError("Couldn't replace the companion (%s)." % error)
    try:
        new.rename(current)
    except OSError as error:
        old.rename(current)
        raise UpdateError("Couldn't replace the companion (%s)." % error)


def rollback(current):
    """Puts the previous version back after a new copy failed to start."""
    current = Path(current)
    old = current.with_name(OLD_NAME)
    if not old.exists():
        return False
    failed = current.with_name(FAILED_NAME)
    remove(failed)
    try:
        if current.exists():
            current.rename(failed)
        old.rename(current)
    except OSError:
        return False
    remove(failed)   # may still be running; cleaned up at a later start otherwise
    return True


def clean_up(folder):
    """Deletes what earlier updates left. Returns True when nothing is left."""
    return all([remove(Path(folder) / name) for name in (OLD_NAME, NEW_NAME, FAILED_NAME, STAGE_NAME)])


def child_environment():
    """Environment for starting the new exe as a fresh program: without this a
    PyInstaller one-file exe started by another reuses the parent's unpacked
    files, which vanish when the parent quits."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("_PYI", "_MEIPASS")) and key not in ("TCL_LIBRARY", "TK_LIBRARY")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def launch(exe, args):
    exe = Path(exe)
    if exe.suffix == ".app":   # macOS: a new copy of the app, through Launch Services
        return subprocess.Popen(["/usr/bin/open", "-n", "-a", str(exe), "--args"] + list(args),
                                env=child_environment(), close_fds=True)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([str(exe)] + list(args), env=child_environment(), close_fds=True,
                            creationflags=flags, cwd=str(Path(exe).parent))
