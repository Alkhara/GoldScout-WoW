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
ACCESS_PORT = os.environ.get("GOLDSCOUT_TEST_ACCESS", "")
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

    def test_companion_version_is_recorded(self):
        def client_of(install):
            status, listing = raw("/v1/uploads?since=%d" % (time.time() - 3600),
                                  headers={"Authorization": "Bearer " + ADMIN})
            self.assertEqual(status, 200)
            return next(u["client"] for u in listing["uploads"] if u["install_id"] == install)

        install = new_install()
        status, first = register(install)          # Python's own User-Agent: not the companion
        self.assertEqual(status, 201)
        self.assertEqual(client_of(install), "other")
        self.assertEqual(uploader.upload(export(install, 1), first["token"], "9.8.7")["status"], "unchanged")
        self.assertEqual(client_of(install), "9.8.7")
        self.assertEqual(uploader.upload(export(install, 2), first["token"], "9.8.8")["status"], "stored")
        self.assertEqual(client_of(install), "9.8.8")

    def test_companion_system_is_recorded(self):
        def listed(install):
            status, listing = raw("/v1/uploads?since=%d" % (time.time() - 3600),
                                  headers={"Authorization": "Bearer " + ADMIN})
            self.assertEqual(status, 200)
            return next(u for u in listing["uploads"] if u["install_id"] == install)

        def send(install, seq, token, agent):
            return raw("/v1/uploads", export(install, seq), {
                "Content-Type": "text/plain; charset=utf-8", "X-GoldScout-Terms": uploader.TERMS_VERSION,
                "Authorization": "Bearer " + token, "User-Agent": agent}, "POST")

        install = new_install()
        status, first = register(install)
        self.assertEqual(status, 201)
        self.assertIsNone(listed(install)["os"])            # no companion system sent yet
        token = first["token"]
        self.assertEqual(send(install, 1, token, "GoldScoutCompanion/0.7.0")[0], 200)
        self.assertIsNone(listed(install)["os"])            # companions before 0.8.0 send none
        self.assertEqual(send(install, 1, token, "GoldScoutCompanion/0.8.0 (macOS)")[0], 200)
        self.assertEqual((listed(install)["client"], listed(install)["os"]), ("0.8.0", "macOS"))
        self.assertEqual(send(install, 1, token, "GoldScoutCompanion/0.8.0 (Linux)")[0], 200)
        self.assertEqual((listed(install)["client"], listed(install)["os"]), ("0.8.0", "macOS"))  # unknown: kept
        self.assertEqual(send(install, 2, token, "GoldScoutCompanion/0.8.1 (Windows)")[0], 200)
        self.assertEqual((listed(install)["client"], listed(install)["os"]), ("0.8.1", "Windows"))

        status, _, text = fetch("/admin/api/summary", {"Authorization": "Bearer " + ADMIN})
        self.assertEqual(status, 200)
        systems = {row["os"]: row for row in json.loads(text)["live"]["systems"]}
        self.assertGreaterEqual(systems["Windows"]["n"], 1)
        self.assertGreaterEqual(systems["Windows"]["d7"], 1)

    def test_version_five_exports_with_a_language_are_accepted(self):
        install = new_install()
        text = "GoldScout-export 5^%s^1\n%s\n@a^3812^205:3,206:1\n@l^0^deDE\n" % (install, LINE)
        status, reply = raw("/v1/uploads", text, {"X-GoldScout-Terms": uploader.TERMS_VERSION,
                                                  "CF-Connecting-IP": fake_ip()}, "POST")
        self.assertEqual((status, reply.get("status")), (201, "registered"))

    def test_fishing_only_exports_are_accepted(self):
        def upload(lines):
            text = "GoldScout-export 5^%s^1\n%s\n" % (new_install(), "\n".join(lines))
            return raw("/v1/uploads", text, {"X-GoldScout-Terms": uploader.TERMS_VERSION,
                                             "CF-Connecting-IP": fake_ip()}, "POST")

        status, reply = upload(["@f^1413^0^20^75^6303:12:12,6291:5:5^335:10", "@f^1413^180683^6^0^6358:6:9^",
                                "@l^0^enUS"])
        self.assertEqual((status, reply.get("status")), (201, "registered"))
        for bad in ("@f^1413^0^20^75^6303:12:12", "@f^1413^0^20^75^Raw Fish^", "@f^x^0^20^75^^"):
            with self.subTest(bad):
                self.assertEqual(upload([bad])[0], 400)

    def test_error_reports_are_grouped_and_rate_limited(self):
        def report(reporter, errors):
            body = json.dumps({"reporter": reporter, "errors": errors})
            return raw("/v1/errors", body, {"Content-Type": "application/json",
                                            "User-Agent": "GoldScoutCompanion/0.11.0 (Windows)"}, "POST")

        message = "GoldScout/UI.lua:%d: attempt to index a nil value" % random.randint(1, 10 ** 9)
        error = {"m": message, "s": "GoldScout/UI.lua:1: in function 'Refresh'", "n": 3, "v": "v0.10.1"}
        first, second = new_install() + "abcd", new_install() + "ef01"
        first, second = "".join("0123456789abcdef"[ord(c) % 16] for c in first[:16]), \
            "".join("0123456789abcdef"[ord(c) % 16] for c in second[:16])
        self.assertEqual(report(first, [error])[0], 200)
        self.assertEqual(report(first, [error])[0], 429)                 # at most every 30 minutes
        self.assertEqual(report(second, [dict(error, n=2)])[0], 200)
        status, _, text = fetch("/admin/api/summary", {"Authorization": "Bearer " + ADMIN})
        self.assertEqual(status, 200)
        live = json.loads(text)["live"]
        row = next(e for e in live["errors"] if e["message"] == message)
        self.assertEqual((row["players"], row["occurrences"], row["reports"]), (2, 5, 2))
        self.assertGreaterEqual(live["errors24"]["players"], 2)
        # Dismissed on the dashboard: gone, and later reports of it are ignored.
        def dismiss(body, headers=None):
            headers = dict({"Authorization": "Bearer " + ADMIN, "Content-Type": "application/json"}, **(headers or {}))
            request = urllib.request.Request(SERVER + "/admin/api/errors/dismiss", data=body.encode(),
                                             headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                return error.code

        fingerprint = row["fingerprint"]
        self.assertEqual(dismiss(json.dumps({"fingerprint": fingerprint}), {"Authorization": "Bearer wrong"}), 403)
        self.assertEqual(dismiss(json.dumps({"fingerprint": fingerprint}), {"Origin": "https://evil.example"}), 403)
        self.assertEqual(dismiss(json.dumps({"fingerprint": fingerprint}), {"Content-Type": "text/plain"}), 403)
        self.assertEqual(dismiss(json.dumps({"fingerprint": "nope"})), 400)
        self.assertEqual(dismiss(json.dumps({"fingerprint": fingerprint})), 200)
        third = "".join("0123456789abcdef"[ord(c) % 16] for c in (new_install() + "9999")[:16])
        self.assertEqual(report(third, [error])[0], 200)
        status, _, text = fetch("/admin/api/summary", {"Authorization": "Bearer " + ADMIN})
        self.assertFalse(any(e["message"] == message for e in json.loads(text)["live"]["errors"]))
        for bad in ({"reporter": "nope", "errors": [error]}, {"reporter": first, "errors": []},
                    {"reporter": first, "errors": [dict(error, n=0)]}, {"reporter": first, "errors": [{"m": 5}]}):
            with self.subTest(bad):
                self.assertEqual(raw("/v1/errors", json.dumps(bad), {"Content-Type": "application/json"}, "POST")[0],
                                 400)

    def test_region_is_recorded(self):
        def region_of(install):
            status, listing = raw("/v1/uploads?since=%d" % (time.time() - 3600),
                                  headers={"Authorization": "Bearer " + ADMIN})
            return next(u["region"] for u in listing["uploads"] if u["install_id"] == install)

        install = new_install()
        status, first = register(install)
        self.assertEqual(status, 201)
        self.assertIsNone(region_of(install))
        self.assertEqual(uploader.upload(export(install, 1), first["token"], "0.9.0", region="eu")["status"],
                         "unchanged")
        self.assertEqual(region_of(install), "eu")
        status, _ = raw("/v1/uploads", export(install, 1), {
            "Content-Type": "text/plain; charset=utf-8", "X-GoldScout-Terms": uploader.TERMS_VERSION,
            "Authorization": "Bearer " + first["token"], "X-GoldScout-Region": "atlantis"}, "POST")
        self.assertEqual(status, 200)
        self.assertEqual(region_of(install), "eu")      # not a region: ignored, the last one kept
        status, _, text = fetch("/admin/api/summary", {"Authorization": "Bearer " + ADMIN})
        regions = {row["region"]: row["n"] for row in json.loads(text)["live"]["regions"]}
        self.assertGreaterEqual(regions["eu"], 1)

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
    GitHub's API records the requests), and the hourly one sends alerts
    (.dev.vars ALERT_WEBHOOK_URL=http://127.0.0.1:<GOLDSCOUT_TEST_GITHUB>/alert,
    the same stand-in)."""

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

    alerts = []   # every alert posted while these tests ran

    def started(self):
        """The workflows started since the last look; alerts are set aside."""
        calls = []
        while True:
            try:
                call = self.calls.get(timeout=3)
            except queue.Empty:
                return calls
            if call[0] == "/alert":
                CronTests.alerts.append(call[2])
            else:
                calls.append(call)

    def test_alerts_go_out_once_and_never_mention_anyone(self):
        self.run_cron("17 * * * *")
        self.started()
        before = len(self.alerts)
        self.run_cron("17 * * * *")
        self.started()
        self.assertEqual(len(self.alerts), before)          # nothing new: nothing repeats within the day
        if os.environ.get("GOLDSCOUT_TEST_FRESH_DB"):        # CI: the first run ever says alerts are on
            self.assertTrue(any("alerts are on" in a["content"] for a in self.alerts))
        for alert in self.alerts:
            self.assertEqual(alert["allowed_mentions"], {"parse": []})
            self.assertTrue(alert["content"])

    def test_each_cron_starts_its_workflow(self):
        for cron, workflow in (("7,22,37,52 * * * *", "ah-prices.yml"), ("17 * * * *", "data-merge.yml"),
                               ("0 15 * * *", "data-release.yml")):
            with self.subTest(cron):
                self.run_cron(cron)
                self.assertEqual(self.started(), [(
                    "/repos/Alkhara/GoldScout-WoW/actions/workflows/%s/dispatches" % workflow,
                    "Bearer local-dispatch-token", {"ref": "main"})])

    def test_other_crons_start_nothing(self):
        self.run_cron("0 0 * * *")
        self.assertEqual(self.started(), [])


def fetch(path, headers=None, method="GET", body=None):
    """(status, headers, text) for any response."""
    request = urllib.request.Request(SERVER + path, headers=headers or {}, method=method,
                                     data=body.encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read().decode()


@unittest.skipUnless(SERVER and ACCESS_PORT, "set GOLDSCOUT_TEST_SERVER and GOLDSCOUT_TEST_ACCESS to test the admin page")
class AdminTests(unittest.TestCase):
    """The admin dashboard opens only with a valid Cloudflare Access token (or
    the admin token for its API). Needs .dev.vars ACCESS_TEAM_DOMAIN=
    test.cloudflareaccess.com, ACCESS_AUD=test-audience and ACCESS_CERTS_URL=
    http://127.0.0.1:<GOLDSCOUT_TEST_ACCESS>/certs; a stand-in serves the keys."""

    @classmethod
    def setUpClass(cls):
        import subprocess
        made = subprocess.run(["node", str(ROOT / "tests" / "access_jwt.mjs")], capture_output=True, text=True,
                              check=True)
        data = json.loads(made.stdout)
        cls.tokens = data["tokens"]
        keys = json.dumps(data["jwks"]).encode()

        class Certs(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(keys)

            def log_message(self, *args):
                pass

        cls.certs = http.server.HTTPServer(("127.0.0.1", int(ACCESS_PORT)), Certs)
        threading.Thread(target=cls.certs.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.certs.shutdown()
        cls.certs.server_close()

    def as_user(self, token):
        return {"Cf-Access-Jwt-Assertion": token}

    def test_closed_without_a_valid_access_token(self):
        self.assertEqual(fetch("/admin")[0], 403)
        self.assertEqual(fetch("/admin/api/summary")[0], 403)
        for name in ("wrongAudience", "expired", "wrongIssuer", "wrongKey", "unknownKey", "tampered", "unsigned"):
            with self.subTest(name):
                status, _, text = fetch("/admin/api/summary", self.as_user(self.tokens[name]))
                self.assertEqual(status, 403)
                self.assertNotIn("live", text)
        self.assertEqual(fetch("/admin", {"Authorization": "Bearer " + ADMIN})[0], 403)   # the page needs Access

    def test_open_with_access(self):
        status, headers, page = fetch("/admin", self.as_user(self.tokens["good"]))
        self.assertEqual(status, 200)
        self.assertIn("GoldScout admin", page)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, headers, script = fetch("/admin/app.js", self.as_user(self.tokens["good"]))
        self.assertEqual((status, headers["Content-Type"].split(";")[0]), (200, "text/javascript"))
        self.assertNotIn("innerHTML", script)
        status, _, text = fetch("/admin/api/summary", self.as_user(self.tokens["good"]))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["live"]["who"], "admin@example.com")

    def test_stats_snapshot_round_trip(self):
        def put(body, admin=ADMIN):
            return fetch("/v1/admin/stats", {"Authorization": "Bearer " + admin,
                                             "Content-Type": "application/json"}, "PUT", body)
        self.assertEqual(put('{"generated": 1}', admin="wrong")[0], 401)
        for bad in ("nope", "[1]", '{"no": "generated"}'):
            with self.subTest(bad):
                self.assertEqual(put(bad)[0], 400)
        generated = int(time.time())
        self.assertEqual(put(json.dumps({"generated": generated, "players": [{"tag": "abcde"}]}))[0], 200)
        status, _, text = fetch("/admin/api/summary", {"Authorization": "Bearer " + ADMIN})
        self.assertEqual(status, 200)
        summary = json.loads(text)
        self.assertEqual(summary["snapshot"]["generated"], generated)
        self.assertEqual(summary["live"]["who"], "admin token")
        self.assertIn("installs", summary["live"])


if __name__ == "__main__":
    unittest.main()
