"""Integration tests for the upload service in server/.

They run against a live server and are skipped unless GOLDSCOUT_TEST_SERVER is
set. Locally (from server/):
  npx wrangler d1 execute goldscout --local --file schema.sql
  npx wrangler dev --local --port 8787     (.dev.vars sets ADMIN_TOKEN etc.)
then:  GOLDSCOUT_TEST_SERVER=http://127.0.0.1:8787 python -m unittest tests.test_server

The cron test also needs the server started with --test-scheduled, .dev.vars
lines GITHUB_DISPATCH_TOKEN=local-dispatch-token and
GITHUB_API=http://127.0.0.1:8798, and GOLDSCOUT_TEST_GITHUB=8798 (the port the
test's stand-in for GitHub listens on).
"""
import http.server
import json
import os
import queue
import threading
import random
import string
import sys
import time
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
GITHUB_PORT = os.environ.get("GOLDSCOUT_TEST_GITHUB", "")
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

    # -- auction prices -------------------------------------------------------------
    def put_prices(self, house, snapshot, prices='{"2589":[15,20699],"2770":[135,3780]}', admin=ADMIN, **extra):
        headers = {"Authorization": "Bearer " + admin, "X-Snapshot": str(snapshot), "X-Items": "2",
                   "X-House-Name": "Horde Auction House", "X-Faction": "Horde",
                   "X-Ruleset": "1", "X-Ruleset-Name": "PvP"}
        headers.update(extra)
        return raw("/v1/admin/prices/kr/%d" % house, prices, headers, "PUT")

    def test_prices_round_trip(self):
        house = random.randint(100000, 999999)  # region kr: never used by the real fetcher
        now = int(time.time())
        self.assertEqual(self.put_prices(house, now - 600), (200, {"status": "stored"}))
        self.assertEqual(self.put_prices(house, now - 600)[1]["status"], "unchanged")
        self.assertEqual(self.put_prices(house, now - 1200)[1]["status"], "older")

        status, prices = raw("/v1/prices/kr/%d" % house)
        self.assertEqual(status, 200)
        self.assertEqual(prices["prices"], {"2589": [15, 20699], "2770": [135, 3780]})
        self.assertEqual((prices["ruleset"], prices["rulesetName"], prices["faction"]), (1, "PvP", "Horde"))
        self.assertEqual(prices["snapshot"], now - 600)
        self.assertIn("Blizzard", prices["source"])

        status, listing = raw("/v1/prices")
        self.assertEqual(status, 200)
        self.assertIn("Blizzard", listing["source"])
        mine = [h for h in listing["houses"] if h["region"] == "kr" and h["house"] == house]
        self.assertEqual(len(mine), 1)
        self.assertNotIn("prices", mine[0])

        # An unmapped house: no ruleset headers.
        unmapped = house + 1 if house < 999999 else house - 1
        status, _ = self.put_prices(unmapped, now, **{"X-Ruleset": "", "X-Ruleset-Name": ""})
        self.assertEqual(status, 200)
        self.assertIsNone(raw("/v1/prices/kr/%d" % unmapped)[1]["ruleset"])
        self.assertEqual(raw("/v1/prices/kr/1")[0], 404)

    def test_prices_need_admin_and_valid_input(self):
        now = int(time.time())
        house = random.randint(100000, 999999)
        self.assertEqual(self.put_prices(house, now, admin="wrong")[0], 401)
        cases = {
            "malformed prices": dict(prices='{"2589":[15,20699],}'),
            "not json": dict(prices="hello"),
            "names in prices": dict(prices='{"x":[1,2]}'),
            "too old for the 30-day limit": dict(snapshot=now - 31 * 86400),
            "in the future": dict(snapshot=now + 3600),
            "bad faction": {"X-Faction": "Pirates"},
            "ruleset without name": {"X-Ruleset-Name": ""},
        }
        for name, case in cases.items():
            with self.subTest(name):
                case = dict(case)
                status, reply = self.put_prices(house, case.pop("snapshot", now), case.pop("prices", "{}"), **case)
                self.assertEqual(status, 400)
                self.assertIn("error", reply)
        self.assertEqual(raw("/v1/prices/kr/%d" % house)[0], 404)

    def test_realm_map_round_trip(self):
        def put(body, admin=ADMIN):
            return raw("/v1/admin/realms/kr", body, {"Authorization": "Bearer " + admin,
                                                     "Content-Type": "application/json"}, "PUT")
        self.assertEqual(put('{"A": 1}', admin="wrong")[0], 401)
        for bad in ('[1, 2]', '{"A": "PvP"}', '{"<script>": 1}', '{"A": 0}', "nope"):
            with self.subTest(bad):
                self.assertEqual(put(bad)[0], 400)
        self.assertEqual(put('{"TestRealm PvP": 1, "Other\'s Realm": 2}'), (200, {"status": "stored", "realms": 2}))
        self.assertEqual(raw("/v1/prices")[1]["realms"]["kr"], {"Other's Realm": 2, "TestRealm PvP": 1})
        self.assertEqual(put('{"TestRealm PvP": 3}')[0], 200)          # replaces the whole region
        self.assertEqual(raw("/v1/prices")[1]["realms"]["kr"], {"TestRealm PvP": 3})
        self.assertEqual(put("{}")[0], 200)
        self.assertNotIn("kr", raw("/v1/prices")[1]["realms"])


@unittest.skipUnless(SERVER and GITHUB_PORT, "set GOLDSCOUT_TEST_SERVER and GOLDSCOUT_TEST_GITHUB to test the crons")
class CronTests(unittest.TestCase):
    """The server's cron triggers start GitHub workflows (a local stand-in for
    GitHub's API records the requests)."""

    @classmethod
    def setUpClass(cls):
        cls.calls = queue.Queue()
        calls = cls.calls

        class GitHub(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                calls.put((self.path, self.headers.get("Authorization"), json.loads(body or b"{}")))
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args):
                pass

        cls.github = http.server.HTTPServer(("127.0.0.1", int(GITHUB_PORT)), GitHub)
        threading.Thread(target=cls.github.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.github.shutdown()
        cls.github.server_close()

    def run_cron(self, cron):
        url = SERVER + "/cdn-cgi/handler/scheduled?cron=" + cron.replace(" ", "+")   # wrangler 4
        with urllib.request.urlopen(url, timeout=10) as response:
            response.read()

    def started(self):
        calls = []
        while True:
            try:
                calls.append(self.calls.get(timeout=3))
            except queue.Empty:
                return calls

    def test_each_cron_starts_its_workflow(self):
        for cron, workflow in (("7,22,37,52 * * * *", "ah-prices.yml"), ("17 * * * *", "data-merge.yml")):
            with self.subTest(cron):
                self.run_cron(cron)
                self.assertEqual(self.started(), [(
                    "/repos/Alkhara/GoldScout-WoW/actions/workflows/%s/dispatches" % workflow,
                    "Bearer local-dispatch-token", {"ref": "main"})])

    def test_other_crons_start_nothing(self):
        self.run_cron("0 0 * * *")
        self.assertEqual(self.started(), [])


if __name__ == "__main__":
    unittest.main()
