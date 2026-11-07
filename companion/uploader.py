"""Sends GoldScout exports to the GoldScout upload service.

The first upload from an install registers it and returns an upload token.
Every later upload for that install must carry the token, so nobody else can
replace that install's data.
"""
import json
import os
import urllib.error
import urllib.request

# The GoldScout upload service (server/). GOLDSCOUT_UPLOAD_URL overrides it,
# for testing against a local server.
UPLOAD_URL = "https://goldscout-api.cawley22.workers.dev"
TERMS_VERSION = "2026-11-07"


class UploadError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def upload_url():
    return os.environ.get("GOLDSCOUT_UPLOAD_URL", UPLOAD_URL).rstrip("/")


def upload(export, token=None, version="dev", timeout=20):
    """Uploads one export. Returns the server's JSON reply, which includes a
    new token the first time an install uploads."""
    base = upload_url()
    if not base:
        raise UploadError("Automatic sharing isn't available yet.")
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "X-GoldScout-Terms": TERMS_VERSION,
        "User-Agent": "GoldScoutCompanion/%s" % version,
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base + "/v1/uploads", data=export.encode("utf-8"),
                                     headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        try:
            message = json.loads(error.read().decode("utf-8")).get("error") or error.reason
        except ValueError:
            message = error.reason
        raise UploadError(str(message), error.code)
    except (urllib.error.URLError, OSError) as error:
        raise UploadError("Couldn't reach the GoldScout server (%s)." % getattr(error, "reason", error))
