"""Integration tests for the upload service in server/.

They run against a live server and are skipped unless GOLDSCOUT_TEST_SERVER is
set. Locally (from server/):
  npx wrangler d1 execute goldscout --local --file schema.sql
  npx wrangler dev --local --port 8787     (.dev.vars sets ADMIN_TOKEN etc.)
then:  GOLDSCOUT_TEST_SERVER=http://127.0.0.1:8787 python -m unittest tests.test_server
"""
import json
import os
import random
import string
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))

import uploader  # noqa: E402

SERVER = os.environ.get("GOLDSCOUT_TEST_SERVER", "")
ADMIN = os.environ.get("GOLDSCOUT_TEST_ADMIN", "local-admin-token")
LINE = "3812^11^0^19^20^1440^0.1179^0.2989^11^Clattering Crawler^2674:4:4,3010:7:7^"


def export(install, seq):
    return "GoldScout-export 2^%s^%d\n%s\n" % (install, seq, LINE)


def new_install():
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))


def fake_ip():
    # Only works against a local server: on Cloudflare the real client address
    # always replaces this header.
    return "10.%d.%d.%d" % (random.randint(0, 255), random.randint(0, 255), random.randint(1, 254))


def register(install, ip=None):
    return raw("/v1/uploads", export(install, 1),
               {"X-GoldScout-Terms": uploader.TERMS_VERSION, "CF-Connecting-IP": ip or fake_ip()}, "POST")


def raw(path, body=None, headers=None, method=None):
    request = urllib.request.Request(SERVER + path, data=body.encode() if body is not None else None,
                                     headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


@unittest.skipUnless(SERVER, "set GOLDSCOUT_TEST_SERVER to run against a live upload service")
class ServerTests(unittest.TestCase):
    def setUp(self):
        os.environ["GOLDSCOUT_UPLOAD_URL"] = SERVER

    def test_register_update_and_protect(self):
        install = new_install()
        status, first = register(install)
        self.assertEqual((status, first["status"]), (201, "registered"))
        token = first["token"]
        self.assertEqual(len(token), 64)

        self.assertEqual(uploader.upload(export(install, 1), token)["status"], "unchanged")
        self.assertEqual(uploader.upload(export(install, 2), token)["status"], "stored")

        with self.assertRaises(uploader.UploadError) as stolen:
            uploader.upload(export(install, 3), "0" * 64)
        self.assertEqual(stolen.exception.status, 403)
        with self.assertRaises(uploader.UploadError) as missing:
            uploader.upload(export(install, 3))
        self.assertEqual(missing.exception.status, 403)

        status, listing = raw("/v1/uploads", headers={"Authorization": "Bearer " + ADMIN})
        self.assertEqual(status, 200)
        mine = [u for u in listing["uploads"] if u["install_id"] == install]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["seq"], 2)
        self.assertEqual(mine[0]["body"], export(install, 2))

    def test_rejects_bad_uploads(self):
        headers = {"X-GoldScout-Terms": uploader.TERMS_VERSION}
        cases = {
            "no terms": (export(new_install(), 1), {}),
            "old format": ("GoldScout-export 1\n" + LINE + "\n", headers),
            "garbage": ("hello", headers),
            "bad line": ("GoldScout-export 2^%s^1\n1^2^3\n" % new_install(), headers),
            "too large": (export(new_install(), 1) + "x" * 70000, headers),
        }
        for name, (body, extra) in cases.items():
            with self.subTest(name):
                status, reply = raw("/v1/uploads", body, extra, "POST")
                self.assertIn(status, (400, 413))
                self.assertIn("error", reply)

    def test_accepts_version_three(self):
        install = new_install()
        body = ("GoldScout-export 3^%s^1\n%s\n@i^3010^Crawler Meat\n@m^1440^Ashenvale\n@c^2996^\n"
                % (install, LINE))
        status, reply = raw("/v1/uploads", body, {"X-GoldScout-Terms": uploader.TERMS_VERSION,
                                                  "CF-Connecting-IP": fake_ip()}, "POST")
        self.assertEqual((status, reply.get("status")), (201, "registered"))
        bad = body.replace("@c^2996^", "@z^1^x")
        status, _ = raw("/v1/uploads", bad.replace(install, new_install()),
                        {"X-GoldScout-Terms": uploader.TERMS_VERSION, "CF-Connecting-IP": fake_ip()}, "POST")
        self.assertEqual(status, 400)

    def test_accepts_version_four(self):
        body = ("GoldScout-export 4^%s^1\n%s\n@i^3010^Crawler Meat\n@q^3010^1:7:1\n@m^1440^Ashenvale\n"
                % (new_install(), LINE))
        status, reply = raw("/v1/uploads", body, {"X-GoldScout-Terms": uploader.TERMS_VERSION,
                                                  "CF-Connecting-IP": fake_ip()}, "POST")
        self.assertEqual((status, reply.get("status")), (201, "registered"))

    def test_list_needs_admin_token(self):
        self.assertEqual(raw("/v1/uploads")[0], 401)
        self.assertEqual(raw("/v1/uploads", headers={"Authorization": "Bearer wrong"})[0], 401)

    def test_new_installs_are_rate_limited_per_network(self):
        ip = fake_ip()
        statuses = [register(new_install(), ip)[0] for _ in range(7)]
        self.assertEqual(statuses[:5], [201] * 5)
        self.assertEqual(statuses[5:], [429, 429])
        self.assertEqual(register(new_install())[0], 201)  # another network is unaffected


if __name__ == "__main__":
    unittest.main()
