#!/usr/bin/env python3
"""Deploys the upload server, and puts the previous version back if the new one
fails its checks. Run by .github/workflows/server-deploy.yml after the schema
step, with CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID set.

  python tools/server_deploy.py

1. Notes which version is live now (wrangler deployments status).
2. Runs wrangler deploy.
3. Checks every address answers /health (a few tries, while the new version
   spreads) and that the server accepts this build's export version.
4. If the deploy or a check failed and a different version is now live, rolls
   back to the noted one and checks again.

Exits 1 whenever the new version didn't stay live, so the workflow fails and
says so. Rolling back is safe after the schema step: schema.sql only adds.

With DEPLOY_DRILL=true (the workflow's "Rehearse a rollback" option) it
deploys, then rolls back as if the checks had failed, and exits 0 if the
rollback worked. Run by hand, the version before is the same code, so
nothing changes for players.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(ROOT / "tools"))
import verify_release  # noqa: E402

# The custom domain, and workers.dev for companions from v0.12.0 and earlier.
ADDRESSES = ["https://api.wowgoldscout.com", "https://goldscout-api.cawley22.workers.dev"]
TRIES, WAIT = 6, 10
# Cloudflare answers Python's default User-Agent with 403 (error 1010).
USER_AGENT = "GoldScout-deploy-check (+https://github.com/Alkhara/GoldScout-WoW)"


def run(command, show=True):
    """Runs a wrangler command in server/: (succeeded, stdout)."""
    # shutil.which finds npx.cmd on Windows, where subprocess alone wouldn't.
    command = [shutil.which(command[0]) or command[0], *command[1:]]
    result = subprocess.run(command, cwd=SERVER, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if show:
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode == 0, result.stdout


def live_version(runner=run):
    """The version serving all traffic now, or None if that can't be read."""
    # Not printed: the status names who deployed (an email address), and CI logs are public.
    ok, out = runner(["npx", "wrangler", "deployments", "status", "--json"], False)
    if not ok:
        return None
    try:
        versions = json.loads(out[out.index("{"):]).get("versions") or []
    except ValueError:
        return None
    full = [v.get("version_id") for v in versions if v.get("percentage") == 100]
    return full[0] if len(full) == 1 else None


def health(url, opener=urllib.request.urlopen):
    try:
        request = urllib.request.Request(url.rstrip("/") + "/health", headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=20) as response:
            return response.status == 200 and json.loads(response.read().decode("utf-8")).get("ok") is True
    except Exception:
        return False


def check(sleep=time.sleep, healthy=health, accepts=None):
    """None when every address is healthy and the export check passes, else the problem."""
    for url in ADDRESSES:
        for attempt in range(TRIES):
            if healthy(url):
                print("ok   %s/health" % url)
                break
            if attempt < TRIES - 1:
                sleep(WAIT)
        else:
            return "%s/health didn't answer ok after %d tries" % (url, TRIES)
    try:
        (accepts or verify_release.check_server)(ADDRESSES[0])
    except (SystemExit, Exception):   # check_server exits with its reason printed
        return "the live server doesn't accept this build's export version"
    return None


def summary(text):
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(runner=run, checker=check, drill=False):
    before = live_version(runner)
    print("Live before deploying: %s" % (before or "unknown"))
    deployed, _ = runner(["npx", "wrangler", "deploy"])
    problem = checker() if deployed else "wrangler deploy failed"
    if drill and not problem:
        problem = "rollback drill, so treated as failed"
    if not problem:
        summary("Deployed and checked the live server.")
        return 0
    summary("**Deploy failed:** %s." % problem)
    after = live_version(runner)
    if after and after == before:
        summary("The previous version is still live, so nothing was rolled back.")
        return 1
    if not before:
        summary("**Not rolled back:** the version live before the deploy couldn't be read. "
                "Roll back in the Cloudflare dashboard (goldscout-api > Deployments).")
        return 1
    message = "Automatic rollback: %s failed its checks" % os.environ.get("GITHUB_SHA", "the deploy")[:12]
    rolled, _ = runner(["npx", "wrangler", "rollback", before, "--message", message, "--yes"])
    if not rolled:
        summary("**Rollback failed.** Roll back to %s in the Cloudflare dashboard "
                "(goldscout-api > Deployments)." % before)
        return 1
    problem = checker()
    if problem:
        summary("**Rolled back to %s, but it fails too:** %s." % (before, problem))
        return 1
    summary("Rolled back to %s, which is healthy." % before)
    return 0 if drill and after != before else 1


if __name__ == "__main__":
    sys.exit(main(drill=os.environ.get("DEPLOY_DRILL") == "true"))
