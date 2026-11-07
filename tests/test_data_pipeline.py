"""Tests for the drop data pipeline: validator, submission bot and merge tool.

Run from the repository root:  python -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import data_bot  # noqa: E402
import merge_data  # noqa: E402
import submission  # noqa: E402

# A real export: two Zoram Strand crawlers.
GOOD = """GoldScout-export 2^abcdefghijkl^3
3812^11^0^19^20^1440^0.1179^0.2989^11^Clattering Crawler^4874:2:2,3010:7:7,2675:5:5,5523:4:4,2674:4:4^
3814^7^0^20^21^1440^0.1215^0.3092^7^Spined Crawler^5569:4:4,2674:4:4,2675:3:3,17057:2:2,5523:2:2,3010:1:1^
"""
CLATTERING = GOOD.splitlines()[1]


def errors(text):
    return submission.parse(text).errors


def form_body(export, ticked=True):
    box = "- [X] " if ticked else "- [ ] "
    return ("%s\n\n```text\n%s\n```\n\n%s\n\n%s%s\n%s%s\n" % (
        data_bot.EXPORT_HEADING, export.strip(), data_bot.TERMS_HEADING,
        box, data_bot.REQUIRED_CONSENT[0], box, data_bot.REQUIRED_CONSENT[1]))


class ValidatorTests(unittest.TestCase):
    def test_real_export_is_valid(self):
        result = submission.parse(GOOD)
        self.assertEqual(result.errors, [])
        self.assertEqual([mob.npc for mob in result.mobs], [3812, 3814])

    def test_windows_line_endings(self):
        self.assertEqual(errors(GOOD.replace("\n", "\r\n")), [])

    def test_round_trip(self):
        result = submission.parse(GOOD)
        self.assertEqual((result.install_id, result.seq), ("abcdefghijkl", 3))
        rebuilt = submission.parse(result.text())
        self.assertEqual(rebuilt.text(), result.text())
        self.assertEqual([m.to_line() for m in rebuilt.mobs], [m.to_line() for m in result.mobs])

    def test_old_exports_get_a_clear_message(self):
        message = errors(GOOD.replace("export 2^abcdefghijkl^3", "export 1"))[0]
        self.assertIn("older GoldScout", message)

    def test_rejects_bad_structure(self):
        cases = {
            "no header": GOOD.replace("GoldScout-export 2^abcdefghijkl^3\n", ""),
            "old version 1 header": GOOD.replace("export 2^abcdefghijkl^3", "export 1"),
            "short install ID": GOOD.replace("abcdefghijkl", "abc"),
            "uppercase install ID": GOOD.replace("abcdefghijkl", "ABCDEFGHIJKL"),
            "snapshot zero": GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl^0"),
            "no snapshot": GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl"),
            "header only": "GoldScout-export 2^abcdefghijkl^3\n",
            "garbage": "hello world",
            "missing field": GOOD.replace("^Spined Crawler", ""),
            "duplicate mob": GOOD + CLATTERING,
            "too large": "GoldScout-export 2^abcdefghijkl^3\n" + "x" * 70000,
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(errors(text))

    def test_rejects_bad_numbers(self):
        cases = {
            "negative kills": GOOD.replace("^11^0^", "^-11^0^"),
            "fractional kills": GOOD.replace("^11^0^", "^11.5^0^"),
            "huge kills": GOOD.replace("^11^0^", "^999999^0^"),
            "leading zero": GOOD.replace("^11^0^", "^011^0^"),
            "level 99": GOOD.replace("^19^20^", "^19^99^"),
            "levels reversed": GOOD.replace("^19^20^", "^20^19^"),
            "position off map": GOOD.replace("0.1179", "1.5000"),
            "position without map": GOOD.replace("^1440^0.1179", "^0^0.1179", 1),
            "more positions than kills": GOOD.replace("^0.2989^11^", "^0.2989^12^"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(errors(text))

    def test_rejects_impossible_loot(self):
        many = ",".join("%d:11:11" % (100 + i) for i in range(10))
        cases = {
            "more drops than kills": GOOD.replace("3010:7:7", "3010:12:12"),
            "impossible stack": GOOD.replace("4874:2:2", "4874:2:900"),
            "less quantity than drops": GOOD.replace("4874:2:2", "4874:2:1"),
            "too many drops per kill": GOOD.replace("Clattering Crawler^", "Clattering Crawler^" + many + ","),
            "item listed twice": GOOD.replace("4874:2:2", "4874:2:2,4874:1:1"),
            "pickpocket items without picks": GOOD.rstrip("\n").rstrip("^") + "^9:1:1\n",
            "bad item entry": GOOD.replace("4874:2:2", "4874:2"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(errors(text))

    def test_rejects_unsafe_names(self):
        for name in ('Spined" Crawler', "|cffff0000Spined", "Spined\\Crawler", "x" * 70):
            with self.subTest(name):
                self.assertTrue(errors(GOOD.replace("Spined Crawler", name)))

    def test_allows_normal_names(self):
        for name in ("Gath'Ilzogg", "Ol' Sooty", "Dun Garok Mountaineer", "Death's Head Acolyte", ""):
            with self.subTest(name):
                self.assertEqual(errors(GOOD.replace("Spined Crawler", name)), [])


class OutlierTests(unittest.TestCase):
    OTHERS = submission.parse(
        "GoldScout-export 2^abcdefghijkl^3\n"
        "3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^2674:20:20,3010:1200:1200^\n").mobs

    def test_sharply_different_rates_are_flagged(self):
        big = (CLATTERING.replace("3812^11^0", "3812^100^0").replace("^11^Clattering", "^100^Clattering")
               .replace("2674:4:4", "2674:90:90"))
        result = submission.compare(submission.parse("GoldScout-export 2^abcdefghijkl^3\n" + big), [self.OTHERS])
        self.assertTrue(result.warnings)

    def test_small_samples_are_not_flagged(self):
        result = submission.compare(submission.parse(GOOD), [self.OTHERS])
        self.assertEqual(result.warnings, [])


class BotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.old_submissions = data_bot.SUBMISSIONS
        data_bot.SUBMISSIONS = Path(self.tmp.name) / "submissions"
        data_bot.SUBMISSIONS.mkdir()

    def tearDown(self):
        data_bot.SUBMISSIONS = self.old_submissions
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def test_review(self):
        self.assertEqual(data_bot.review(form_body(GOOD), 1)[0], "valid")
        self.assertEqual(data_bot.review(form_body(GOOD).replace("\n", "\r\n"), 1)[0], "valid")
        self.assertEqual(data_bot.review(form_body(GOOD, ticked=False), 1)[0], "invalid")
        self.assertEqual(data_bot.review("random issue text", 1)[0], "invalid")
        self.assertEqual(data_bot.review(form_body("GoldScout-export 2^abcdefghijkl^3\nbad"), 1)[0], "invalid")

    def run_check(self, issue):
        event = Path("event.json")
        event.write_text(json.dumps({"action": "opened", "issue": issue}), encoding="utf-8")
        data_bot.check(str(event))
        return Path("comment.md").read_text(encoding="utf-8") if Path("comment.md").exists() else ""

    def test_check_comment_never_quotes_the_issue(self):
        evil = GOOD.replace("Spined Crawler", "@everyone `rm -rf` <script>")
        comment = self.run_check({"number": 1, "body": form_body(evil),
                                  "user": {"id": 5, "login": "x", "type": "User"}})
        self.assertIn("can't be accepted", comment)
        for fragment in ("@everyone", "rm -rf", "<script>"):
            self.assertNotIn(fragment, comment)

    def test_check_points_blank_issues_to_the_form(self):
        comment = self.run_check({"number": 1, "body": GOOD,
                                  "user": {"id": 5, "login": "x", "type": "User"}})
        self.assertIn("regular issue", comment)
        self.assertIn(data_bot.FORM_URL, comment)

    def test_check_skips_bots(self):
        Path("comment.md").unlink(missing_ok=True)
        self.assertEqual(self.run_check({"number": 1, "body": form_body(GOOD),
                                         "user": {"id": 5, "login": "b", "type": "Bot"}}), "")

    def test_collect_keeps_latest_valid_export_per_player(self):
        def issue(number, body, user_id, kind="User", labels=("data-valid",)):
            return {"number": number, "body": body, "labels": list(labels),
                    "user": {"id": user_id, "login": "p%d" % user_id, "type": kind}}
        issues = [
            issue(5, form_body(GOOD), 1),
            issue(9, form_body(GOOD.replace("3010:7:7", "3010:8:8")), 1),
            issue(7, form_body("GoldScout-export 2^abcdefghijkl^3\nbad"), 2),
            issue(10, form_body(GOOD), 4, kind="Bot"),
        ]
        Path("issues.jsonl").write_text("\n".join(json.dumps(i) for i in issues), encoding="utf-8")
        data_bot.collect("issues.jsonl")
        self.assertEqual(sorted(p.name for p in data_bot.SUBMISSIONS.glob("*.txt")), ["1-abcdefghijkl.txt"])
        self.assertIn("3010:8:8", (data_bot.SUBMISSIONS / "1-abcdefghijkl.txt").read_text(encoding="utf-8"))
        body = Path("pr_body.md").read_text(encoding="utf-8")
        self.assertIn("Closes #5", body)
        self.assertIn("Closes #9", body)
        self.assertNotIn("Closes #7", body)
        self.assertNotIn("Closes #10", body)

    def test_collect_keeps_newest_snapshot_per_install(self):
        def issue(number, export):
            return {"number": number, "body": form_body(export), "labels": ["data-valid"],
                    "user": {"id": 1, "login": "p1", "type": "User"}}
        newer = GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl^7").replace("3010:7:7", "3010:8:8")
        other_install = GOOD.replace("abcdefghijkl", "zzzzzzzzzzzz")
        (data_bot.SUBMISSIONS / "1.txt").write_text("GoldScout-export 1\nold format\n", encoding="utf-8")
        issues = [issue(20, newer), issue(21, GOOD), issue(22, other_install)]
        Path("issues.jsonl").write_text("\n".join(json.dumps(i) for i in issues), encoding="utf-8")
        data_bot.collect("issues.jsonl")
        names = sorted(p.name for p in data_bot.SUBMISSIONS.glob("*.txt"))
        self.assertEqual(names, ["1-abcdefghijkl.txt", "1-zzzzzzzzzzzz.txt"])  # old format removed
        kept = submission.parse((data_bot.SUBMISSIONS / "1-abcdefghijkl.txt").read_text(encoding="utf-8"))
        self.assertEqual(kept.seq, 7)  # snapshot 7 wins over 3, though its issue is older
        body = Path("pr_body.md").read_text(encoding="utf-8")
        for number in (20, 21, 22):
            self.assertIn("Closes #%d" % number, body)

    def test_collect_uploads(self):
        newer = GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl^5")
        listing = {"uploads": [
            {"install_id": "abcdefghijkl", "seq": 5, "body": newer, "terms": "2026-11-07"},
            {"install_id": "zzzzzzzzzzzz", "seq": 3, "body": GOOD, "terms": "2026-11-07"},  # ID mismatch
            {"install_id": "badtermsxxxx", "seq": 3, "body": GOOD.replace("abcdefghijkl", "badtermsxxxx"),
             "terms": "1999-01-01"},
        ]}
        Path("uploads.json").write_text(json.dumps(listing), encoding="utf-8")
        Path("pr_body.md").write_text("", encoding="utf-8")
        data_bot.collect_uploads("uploads.json")
        names = sorted(p.name for p in data_bot.SUBMISSIONS.glob("*.txt"))
        self.assertEqual(names, ["c-abcdefghijkl.txt"])
        self.assertEqual(submission.parse((data_bot.SUBMISSIONS / names[0]).read_text(encoding="utf-8")).seq, 5)
        body = Path("pr_body.md").read_text(encoding="utf-8")
        self.assertIn("`abcdefghijkl` | 5 |", body)
        self.assertIn("2 upload(s) failed validation", body)

    def test_review_label_needs_approval(self):
        (data_bot.SUBMISSIONS / "999.txt").write_text(
            "GoldScout-export 2^abcdefghijkl^3\n3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^"
            "2674:20:20,3010:1200:1200^\n", encoding="utf-8")
        big = (CLATTERING.replace("3812^11^0", "3812^100^0").replace("^11^Clattering", "^100^Clattering")
               .replace("2674:4:4", "2674:90:90"))
        body = form_body("GoldScout-export 2^abcdefghijkl^3\n" + big)
        for labels, stored in ((["data-valid"], False), (["data-approved"], True)):
            with self.subTest(labels=labels):
                (data_bot.SUBMISSIONS / "3-abcdefghijkl.txt").unlink(missing_ok=True)
                issue = {"number": 8, "body": body, "labels": labels,
                         "user": {"id": 3, "login": "c", "type": "User"}}
                Path("issues.jsonl").write_text(json.dumps(issue), encoding="utf-8")
                data_bot.collect("issues.jsonl")
                self.assertEqual((data_bot.SUBMISSIONS / "3-abcdefghijkl.txt").exists(), stored)


class MergeTests(unittest.TestCase):
    def test_one_file_per_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "7-abcdefghijkl.txt").write_text(GOOD.replace("^3\n", "^9\n", 1), encoding="utf-8")
            (folder / "c-abcdefghijkl.txt").write_text(GOOD.replace("3010:7:7", "3010:6:6"), encoding="utf-8")
            (folder / "8-zzzzzzzzzzzz.txt").write_text(GOOD.replace("abcdefghijkl", "zzzzzzzzzzzz"), encoding="utf-8")
            loaded = {r.install_id: r for r in merge_data.load(folder)}
            self.assertEqual(sorted(loaded), ["abcdefghijkl", "zzzzzzzzzzzz"])
            # The companion upload wins over a higher-numbered issue submission.
            self.assertEqual(loaded["abcdefghijkl"].seq, 3)
            self.assertIn("3010:6:6", loaded["abcdefghijkl"].text())

    def test_one_player_is_capped(self):
        heavy = submission.parse(
            "GoldScout-export 2^abcdefghijkl^3\n3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^3010:1200:1200^\n").mobs
        merged = merge_data.merge([heavy, submission.parse(GOOD).mobs], max_per_player=1000)
        self.assertEqual(merged[3812]["k"], 1011)
        self.assertEqual(merged[3812]["i"][3010][0], 600 + 7)

    def test_generated_lua_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Data_Community.lua"
            names = GOOD.replace("Spined Crawler", "Gath'Ilzogg")
            results = [submission.parse(names)]
            kept = merge_data.write_lua(merge_data.merge([r.mobs for r in results], 1000), 5, target, 1,
                                        merge_data.sources_of(results), 1000)
            self.assertEqual(kept, 2)
            text = target.read_text(encoding="utf-8")
            self.assertIn("GoldScout Data License", text)
            self.assertIn('["abcdefghijkl"] = 3', text)
            self.assertIn("ns.COMMUNITY_CAP = 1000", text)
            check = subprocess.run([sys.executable, str(ROOT / "tools" / "luacheck_lite.py"), str(target)],
                                   capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
