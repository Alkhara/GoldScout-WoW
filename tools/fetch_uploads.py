#!/usr/bin/env python3
"""Fetches the upload service's listing for the hourly data merge, downloading only the exports it needs.

Every install is listed without its export (GET /v1/uploads?bodies=0, a few hundred bytes each); an
export is downloaded (GET /v1/uploads?ids=..., up to 50 at a time) only when its snapshot is newer than
the one already in data/submissions/c-<install>.txt, or there is none yet (new, held or rejected
uploads). tools/data_bot.py collect-uploads skips the rest without needing their exports, so the merge
stays quick however many players there are.

  python tools/fetch_uploads.py uploads.json

Needs GOLDSCOUT_API_ADMIN; GOLDSCOUT_API_URL picks the server. A server that ignores ?bodies=0 (before
it was added) sends every export, which works too.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS = ROOT / "data" / "submissions"
BATCH = 50          # the server's MAX_LIST_IDS
TRIES = 3
USER_AGENT = "GoldScout-merge/1.0 (+https://github.com/Alkhara/GoldScout-WoW)"


def get_json(url, admin, opener=urllib.request.urlopen, sleep=time.sleep):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + admin, "User-Agent": USER_AGENT})
    for attempt in range(1, TRIES + 1):
        try:
            with opener(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429 or attempt == TRIES:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == TRIES:
                raise
        sleep(10 * attempt)


def stored_snapshots(folder=SUBMISSIONS):
    """{install: snapshot} of the companion uploads already stored, from each file's first line."""
    stored = {}
    for path in folder.glob("c-*.txt"):
        with open(path, encoding="utf-8") as handle:
            parts = handle.readline().strip().split("^")
        if len(parts) == 3 and parts[2].isdigit():
            stored[path.stem[2:]] = int(parts[2])
    return stored


def needed(uploads, stored):
    """The installs whose exports this merge has to see: no export in the listing, and a snapshot newer
    than the stored one (or none stored)."""
    return [u["install_id"] for u in uploads if "body" not in u
            and not (isinstance(u.get("seq"), int) and stored.get(u.get("install_id"), -1) >= u["seq"])]


def fetch(api, admin, stored, get=get_json):
    uploads = get(api + "/v1/uploads?bodies=0", admin).get("uploads", [])
    wanted = needed(uploads, stored)
    bodies = {}
    for start in range(0, len(wanted), BATCH):
        batch = wanted[start:start + BATCH]
        for row in get(api + "/v1/uploads?ids=" + ",".join(batch), admin).get("uploads", []):
            bodies[row["install_id"]] = row.get("body")
    for upload in uploads:
        if upload["install_id"] in bodies:
            upload["body"] = bodies[upload["install_id"]]
    return uploads, len(bodies)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    admin = os.environ.get("GOLDSCOUT_API_ADMIN", "")
    api = os.environ.get("GOLDSCOUT_API_URL", "https://api.wowgoldscout.com").rstrip("/")
    if not admin:
        sys.exit("GOLDSCOUT_API_ADMIN isn't set.")
    uploads, downloaded = fetch(api, admin, stored_snapshots())
    Path(sys.argv[1]).write_text(json.dumps({"uploads": uploads}), encoding="utf-8")
    print("Upload service: %d install(s) found; %d new or changed export(s) downloaded." % (len(uploads), downloaded))


if __name__ == "__main__":
    main()
