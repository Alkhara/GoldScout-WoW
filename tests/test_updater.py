"""The companion's in-place updater: release checks, download checks, the
signature rule, and swapping/rolling back files (on temporary files, never a
running exe)."""
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))

import updater  # noqa: E402

EXE = b"MZ new companion bytes" * 1000
GOOD_SIGNATURE = {"status": "Valid",
                  "subject": "CN=Chris Cawley, O=Chris Cawley, L=Sandown, S=nh, C=US",
                  "issuer": "CN=Microsoft ID Verified CS AOC CA 03, O=Microsoft Corporation, C=US"}


def release(tag="v0.6.2", digest=None, name=updater.ASSET, **extra):
    asset = {"name": name, "size": len(EXE), "browser_download_url": "https://example/exe",
             "digest": digest if digest is not None else "sha256:" + hashlib.sha256(EXE).hexdigest()}
    return dict({"tag_name": tag, "html_url": "https://example/release", "assets": [asset]}, **extra)


def fake_opener(body):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    return lambda request, timeout: Response(body)


class CheckTests(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(updater.is_newer("0.6.2", "0.6.1"))
        self.assertTrue(updater.is_newer("v0.10.0", "0.9.9"))     # numeric, not text order
        self.assertFalse(updater.is_newer("0.6.1", "0.6.1"))
        self.assertFalse(updater.is_newer("0.6.0", "0.6.1"))
        self.assertFalse(updater.is_newer("garbage", "0.6.1"))

    def test_offers_a_newer_release_with_a_hash(self):
        update = updater.check("0.6.1", fetch=lambda url, version: release())
        self.assertEqual((update.version, update.size), ("0.6.2", len(EXE)))
        self.assertEqual(update.sha256, hashlib.sha256(EXE).hexdigest())
        self.assertEqual(update.page, "https://example/release")

    def test_nothing_to_offer(self):
        cases = {
            "same version": release("v0.6.1"),
            "older": release("v0.6.0"),
            "prerelease": release(prerelease=True),
            "no companion": release(name="GoldScout-v0.6.2-forever.zip"),
            "no hash": release(digest=""),
        }
        for name, data in cases.items():
            with self.subTest(name):
                self.assertIsNone(updater.check("0.6.1", fetch=lambda url, version, data=data: data))

    def test_offline_is_an_update_error(self):
        def offline(url, version):
            raise OSError("no network")
        with self.assertRaises(updater.UpdateError):
            updater.check("0.6.1", fetch=offline)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.update = updater.check("0.6.1", fetch=lambda url, version: release())

    def test_good_download(self):
        seen = []
        path = updater.download(self.update, self.folder, "0.6.1", opener=fake_opener(EXE),
                                progress=lambda done, total: seen.append(done))
        self.assertEqual(path.read_bytes(), EXE)
        self.assertEqual(path.name, updater.NEW_NAME)
        self.assertEqual(seen[-1], len(EXE))

    def test_tampered_or_short_downloads_are_deleted(self):
        for name, body in {"tampered": EXE[:-1] + b"X", "short": EXE[:100], "long": EXE + b"extra"}.items():
            with self.subTest(name):
                with self.assertRaises(updater.UpdateError):
                    updater.download(self.update, self.folder, "0.6.1", opener=fake_opener(body))
                self.assertFalse((self.folder / updater.NEW_NAME).exists())


class SignatureTests(unittest.TestCase):
    def test_only_our_valid_signature_passes(self):
        updater.verify_signature("x", reader=lambda path: GOOD_SIGNATURE)
        bad = {
            "unsigned": dict(GOOD_SIGNATURE, status="NotSigned", subject="", issuer=""),
            "hash mismatch": dict(GOOD_SIGNATURE, status="HashMismatch"),
            "someone else": dict(GOOD_SIGNATURE, subject="CN=Evil Corp, O=Evil Corp, C=US"),
            "name inside another": dict(GOOD_SIGNATURE, subject="CN=Not Chris Cawley, O=Chris Cawley Fan, C=US"),
            "other issuer": dict(GOOD_SIGNATURE, issuer="CN=Some Other CA, O=Someone, C=US"),
        }
        for name, info in bad.items():
            with self.subTest(name):
                with self.assertRaises(updater.UpdateError):
                    updater.verify_signature("x", reader=lambda path, info=info: info)


class SwapTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.current = self.folder / "GoldScoutCompanion.exe"
        self.current.write_bytes(b"old")
        self.new = self.folder / updater.NEW_NAME
        self.new.write_bytes(b"new")

    def test_swap_then_clean_up(self):
        updater.swap(self.current, self.new)
        self.assertEqual(self.current.read_bytes(), b"new")
        self.assertEqual((self.folder / updater.OLD_NAME).read_bytes(), b"old")
        self.assertTrue(updater.clean_up(self.folder))
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["GoldScoutCompanion.exe"])

    def test_rollback_restores_the_old_version(self):
        updater.swap(self.current, self.new)
        self.assertTrue(updater.rollback(self.current))
        self.assertEqual(self.current.read_bytes(), b"old")
        self.assertFalse((self.folder / updater.OLD_NAME).exists())

    def test_failed_swap_leaves_the_current_exe(self):
        self.new.unlink()   # nothing to move in
        with self.assertRaises(updater.UpdateError):
            updater.swap(self.current, self.new)
        self.assertEqual(self.current.read_bytes(), b"old")

    def test_child_starts_fresh(self):
        env = updater.child_environment()
        self.assertEqual(env["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertFalse([key for key in env if key.startswith("_PYI") or key in ("TCL_LIBRARY", "TK_LIBRARY")])


if __name__ == "__main__":
    unittest.main()
