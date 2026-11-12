"""Sends GoldScout exports to the GoldScout upload service.

The first upload from an install registers it and returns an upload token.
Every later upload for that install must carry the token, so nobody else can
replace that install's data.
"""
import functools
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

# The GoldScout upload service (server/). GOLDSCOUT_UPLOAD_URL overrides it,
# for testing against a local server. Copies from v0.12.0 and earlier use the Worker's
# workers.dev address, which stays on for them (server/wrangler.toml).
UPLOAD_URL = "https://api.wowgoldscout.com"
TERMS_VERSION = "2026-11-07"


@functools.lru_cache(maxsize=None)
def https_context():
    """The certificates HTTPS requests are checked against. On Windows, the
    system's own. python.org's Python on macOS (and so the app built from it)
    has none of its own until its Install Certificates script runs, so there
    it's certifi's list, bundled with the app."""
    if sys.platform == "darwin":
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            pass
    return ssl.create_default_context()


def open_url(request, timeout):
    """urllib.request.urlopen with https_context(); every request the companion makes."""
    return urllib.request.urlopen(request, timeout=timeout, context=https_context())


class UploadError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


# The system named in uploads' User-Agent, so the GoldScout server can count
# installs per OS (and nothing else about the computer).
OS_NAME = {"win32": "Windows", "darwin": "macOS"}.get(sys.platform)


def user_agent(version):
    """'GoldScoutCompanion/0.8.0 (macOS)': the companion's version and system."""
    return "GoldScoutCompanion/%s" % version + (" (%s)" % OS_NAME if OS_NAME else "")


def upload_url():
    return os.environ.get("GOLDSCOUT_UPLOAD_URL", UPLOAD_URL).rstrip("/")


def upload(export, token=None, version="dev", timeout=20, region=None):
    """Uploads one export. Returns the server's JSON reply, which includes a
    new token the first time an install uploads. region ("us", "eu", ...)
    lets the server count installs per region."""
    base = upload_url()
    if not base:
        raise UploadError("Automatic sharing isn't available yet.")
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "X-GoldScout-Terms": TERMS_VERSION,
        "User-Agent": user_agent(version),
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if region:
        headers["X-GoldScout-Region"] = region
    request = urllib.request.Request(base + "/v1/uploads", data=export.encode("utf-8"),
                                     headers=headers, method="POST")
    try:
        with open_url(request, timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            message = json.loads(error.read().decode("utf-8")).get("error") or error.reason
        except ValueError:
            message = error.reason
        raise UploadError(str(message), error.code)
    except (urllib.error.URLError, OSError) as error:
        raise UploadError("Couldn't reach the GoldScout server (%s)." % getattr(error, "reason", error))
