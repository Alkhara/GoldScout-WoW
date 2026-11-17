"""tools/fetch_uploads.py: the hourly merge downloads only new and changed exports."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fetch_uploads  # noqa: E402


class FetchUploadsTests(unittest.TestCase):
    def test_stored_snapshots_come_from_each_files_first_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "c-aaaaaaaaaaaa.txt").write_text("GoldScout-export 5^aaaaaaaaaaaa^7\n1^...\n", encoding="utf-8")
            (folder / "12-bbbbbbbbbbbb.txt").write_text("GoldScout-export 5^bbbbbbbbbbbb^3\n", encoding="utf-8")
            (folder / "c-cccccccccccc.txt").write_text("not an export\n", encoding="utf-8")
            self.assertEqual(fetch_uploads.stored_snapshots(folder), {"aaaaaaaaaaaa": 7})   # companion files only

    def test_only_new_and_changed_exports_are_downloaded(self):
        listing = [{"install_id": "a" * 12, "seq": 7}, {"install_id": "b" * 12, "seq": 8},
                   {"install_id": "c" * 12, "seq": 1}, {"install_id": "d" * 12, "seq": 2, "body": "old server"}]
        stored = {"a" * 12: 7, "b" * 12: 5}
        self.assertEqual(fetch_uploads.needed(listing, stored), ["b" * 12, "c" * 12])   # changed, and new

        asked = []

        def get(url, admin):
            asked.append(url)
            if "bodies=0" in url:
                return {"uploads": [dict(u) for u in listing]}
            ids = url.split("ids=")[1].split(",")
            return {"uploads": [{"install_id": i, "body": "export of " + i} for i in ids]}
        uploads, downloaded = fetch_uploads.fetch("https://api", "token", stored, get=get)
        self.assertEqual(downloaded, 2)
        self.assertEqual(asked, ["https://api/v1/uploads?bodies=0", "https://api/v1/uploads?ids=%s,%s" % ("b" * 12, "c" * 12)])
        bodies = {u["install_id"]: u.get("body") for u in uploads}
        self.assertEqual(bodies, {"a" * 12: None, "b" * 12: "export of " + "b" * 12, "c" * 12: "export of " + "c" * 12,
                                  "d" * 12: "old server"})

    def test_downloads_go_in_batches_the_server_takes(self):
        listing = [{"install_id": "%012d" % i, "seq": 1} for i in range(120)]
        batches = []

        def get(url, admin):
            if "bodies=0" in url:
                return {"uploads": [dict(u) for u in listing]}
            ids = url.split("ids=")[1].split(",")
            batches.append(len(ids))
            return {"uploads": [{"install_id": i, "body": "x"} for i in ids]}
        fetch_uploads.fetch("https://api", "token", {}, get=get)
        self.assertEqual(batches, [50, 50, 20])


if __name__ == "__main__":
    unittest.main()
