"""The companion's macOS pieces: settings folder, login item, one copy at a
time, the update notification, finding WoW, and updates of the .app. Most run
on any system with macOS switched on in the module; the lock-file test needs
a Unix system."""
import hashlib
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "tools"))

import savedvars  # noqa: E402
import system  # noqa: E402
import updater  # noqa: E402

TEAM = "ABCDE12345"
BUNDLE = Path("/Applications/GoldScout Companion.app")


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class SystemTests(unittest.TestCase):
    def test_settings_folder(self):
        with mock.patch.object(system, "MAC", True):
            self.assertEqual(system.config_dir(),
                             Path.home() / "Library" / "Application Support" / "GoldScout Companion")

    def test_installed_path_is_the_app_bundle(self):
        program = BUNDLE / "Contents" / "MacOS" / "GoldScout Companion"
        with mock.patch.object(system, "MAC", True):
            self.assertEqual(system.installed_path(program), BUNDLE)
            self.assertEqual(system.installed_path("/usr/bin/python3"), Path("/usr/bin/python3"))
        with mock.patch.object(system, "MAC", False):
            self.assertEqual(system.installed_path(program), program)

    def test_launch_agent(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertFalse(system.mac_agent_enabled(BUNDLE, home))
            system.set_mac_agent(True, BUNDLE, home)
            path = system.agent_path(home)
            self.assertEqual(path.parent, Path(home) / "Library" / "LaunchAgents")
            with open(path, "rb") as handle:
                agent = plistlib.load(handle)
            self.assertEqual(agent["Label"], system.AGENT_LABEL)
            self.assertEqual(agent["ProgramArguments"],
                             ["/usr/bin/open", "-g", "-a", str(BUNDLE), "--args", "--tray"])
            self.assertTrue(agent["RunAtLoad"])
            self.assertTrue(system.mac_agent_enabled(BUNDLE, home))
            # The app moved: the old login item no longer counts as on.
            self.assertFalse(system.mac_agent_enabled(Path("/Users/me/Applications/GoldScout Companion.app"), home))
            system.set_mac_agent(False, BUNDLE, home)
            self.assertFalse(path.exists())
            system.set_mac_agent(False, BUNDLE, home)   # already off: no error

    def test_notification_quotes_its_text(self):
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return completed()
        with mock.patch.object(system, "MAC", True):
            self.assertTrue(system.notify('Say "hi"', "back\\slash", run=run))
        self.assertEqual(calls, [["osascript", "-e", 'display notification "back\\\\slash" with title "Say \\"hi\\""']])
        with mock.patch.object(system, "MAC", False):
            self.assertFalse(system.notify("t", "m", run=run))
        self.assertEqual(len(calls), 1)

    def test_finds_wow_in_applications(self):
        roots = savedvars.mac_roots("/Users/me")
        self.assertIn(Path("/Applications/World of Warcraft"), roots)
        self.assertIn(Path("/Users/me/Applications/World of Warcraft"), roots)


@unittest.skipIf(sys.platform == "win32", "uses a Unix file lock")
class LockFileTests(unittest.TestCase):
    def test_one_copy_at_a_time(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(system, "MAC", True), \
                mock.patch.object(system, "WINDOWS", False):
            signal = Path(tmp) / "show.request"
            first, second = system.SingleInstance(signal), system.SingleInstance(signal)
            self.assertTrue(first.claim())
            self.assertTrue(second.other_running())   # the first copy holds the lock
            self.assertFalse(second.claim())
            self.assertTrue(signal.exists())                     # it asked the first copy to show itself
            self.assertTrue(first.show_requested())
            first.close()
            self.assertFalse(second.other_running())
            self.assertTrue(second.claim(signal=False))
            self.assertTrue(first.other_running())
            second.close()


class MacUpdateTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def signed(self, team=TEAM, authority=None, verify=0, gatekeeper=0):
        authority = authority or "Developer ID Application: Chris Cawley (%s)" % team
        details = ("Executable=/x\nIdentifier=com.wowgoldscout.companion\nAuthority=%s\n"
                   "Authority=Developer ID Certification Authority\nAuthority=Apple Root CA\n"
                   "TeamIdentifier=%s\n" % (authority, team))

        def run(command, **kwargs):
            if command[0].endswith("codesign") and "--verify" in command:
                return completed(verify)
            if command[0].endswith("codesign"):
                return completed(0, "", details)   # codesign -dv prints to stderr
            if command[0].endswith("spctl"):
                return completed(gatekeeper)
            raise AssertionError(command)
        return run

    def test_picks_the_mac_asset(self):
        body = b"zip bytes"
        release = {"tag_name": "v0.8.0", "html_url": "https://example/release", "assets": [
            {"name": updater.WINDOWS_ASSET, "size": 1, "browser_download_url": "https://example/exe",
             "digest": "sha256:" + "0" * 64},
            {"name": updater.MAC_ASSET, "size": len(body), "browser_download_url": "https://example/zip",
             "digest": "sha256:" + hashlib.sha256(body).hexdigest()}]}
        update = updater.check("0.7.0", fetch=lambda url, version: release, asset_name=updater.MAC_ASSET)
        self.assertEqual(update.url, "https://example/zip")
        release["assets"].pop()
        self.assertIsNone(updater.check("0.7.0", fetch=lambda url, version: release, asset_name=updater.MAC_ASSET))

    def test_accepts_goldscouts_notarized_app(self):
        updater.verify_mac(self.folder, run=self.signed(), team=TEAM)

    def test_refuses_anything_else(self):
        bad = {
            "no team configured": dict(team_setting=""),
            "broken signature": dict(verify=1),
            "another team": dict(team="ZZZZZ99999"),
            "not a Developer ID": dict(authority="Apple Development: Someone (%s)" % TEAM),
            "Developer ID of someone else": dict(authority="Developer ID Application: Evil (ZZZZZ99999)"),
            "not notarized": dict(gatekeeper=3),
        }
        for name, case in bad.items():
            with self.subTest(name):
                team_setting = case.pop("team_setting", TEAM)
                with self.assertRaises(updater.UpdateError):
                    updater.verify_mac(self.folder, run=self.signed(**case), team=team_setting)

    def test_no_team_means_no_installs(self):
        with mock.patch.object(updater, "MAC", True):
            self.assertFalse(updater.can_install(""))
            self.assertTrue(updater.can_install(TEAM))
        with mock.patch.object(updater, "MAC", False):
            self.assertTrue(updater.can_install(""))

    def test_unpacks_only_the_companion_app(self):
        archive = self.folder / "download.zip"

        def ditto(contents):
            def run(command, **kwargs):
                archive_arg, stage = command[-2], Path(command[-1])
                self.assertEqual(archive_arg, str(archive))
                for name in contents:
                    (stage / name / "Contents").mkdir(parents=True)
                return completed()
            return run

        archive.write_bytes(b"zip")
        app = updater.unpack_mac(archive, self.folder, run=ditto([updater.APP_BUNDLE, "__MACOSX"]))
        self.assertEqual(app, self.folder / updater.STAGE_NAME / updater.APP_BUNDLE)
        self.assertFalse(archive.exists())
        for contents in ([], ["Other.app"], [updater.APP_BUNDLE, "Extra.app"]):
            with self.subTest(contents):
                archive.write_bytes(b"zip")
                with self.assertRaises(updater.UpdateError):
                    updater.unpack_mac(archive, self.folder, run=ditto(contents))
                self.assertFalse((self.folder / updater.STAGE_NAME).exists())
                self.assertFalse(archive.exists())

    def test_swaps_and_rolls_back_app_folders(self):
        current = self.folder / updater.APP_BUNDLE
        (current / "Contents").mkdir(parents=True)
        (current / "Contents" / "v").write_text("old")
        new = self.folder / updater.STAGE_NAME / updater.APP_BUNDLE
        (new / "Contents").mkdir(parents=True)
        (new / "Contents" / "v").write_text("new")
        with mock.patch.object(updater, "OLD_NAME", "GoldScout Companion.old.app"), \
                mock.patch.object(updater, "FAILED_NAME", "GoldScout Companion.failed.app"):
            updater.swap(current, new)
            self.assertEqual((current / "Contents" / "v").read_text(), "new")
            self.assertTrue(updater.rollback(current))
            self.assertEqual((current / "Contents" / "v").read_text(), "old")
            self.assertTrue(updater.clean_up(self.folder))
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [updater.APP_BUNDLE])

    def test_launches_a_new_copy_of_the_app(self):
        with mock.patch.object(updater.subprocess, "Popen") as popen:
            updater.launch(BUNDLE, ["--after-update", "--tray"])
        command = popen.call_args[0][0]
        self.assertEqual(command, ["/usr/bin/open", "-n", "-a", str(BUNDLE), "--args", "--after-update", "--tray"])


if __name__ == "__main__":
    unittest.main()
