"""Tests for the drop data pipeline: validator, submission bot and merge tool.

Run from the repository root:  python -m unittest discover -s tests
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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
            "too large": "GoldScout-export 2^abcdefghijkl^3\n" + "x" * 260000,
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(errors(text))

    def test_long_time_players_exports_fit(self):
        # Past the share form's 60 KB (GitHub issues), within what the companion uploads.
        names = "".join("@i^%d^Some Long Item Name Number %d\n" % (item, item) for item in range(10000, 12500))
        big = GOOD.replace("export 2^", "export 3^") + names
        self.assertGreater(len(big.encode()), submission.FORM_MAX_BYTES)
        self.assertEqual(errors(big), [])
        # The share form still can't carry it, and says where to go instead.
        status, result, _, _ = data_bot.review(form_body(big), 1)
        self.assertEqual(status, "invalid")
        self.assertIn("GoldScout Companion can share it", result.errors[0])
        self.assertEqual(data_bot.review(form_body(GOOD), 1)[0], "valid")

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

    def test_a_boss_dropping_a_full_stack_of_ammo_is_fine(self):
        # Lord Roccor drops Rockshard Pellets 200 at a time: 3 kills, 3 drops, 600 pellets.
        self.assertEqual(errors(GOOD.replace("4874:2:2", "4874:2:400")), [])

    def test_unsafe_name_characters_are_removed_not_the_export(self):
        # Quotes, backslashes and the game's | codes become spaces: harmless, and the rest of the export counts.
        for name, kept in (('Spined" Crawler', "Spined Crawler"), ("|cffff0000Spined", "cffff0000Spined"),
                           ("Spined\\Crawler", "Spined Crawler")):
            with self.subTest(name):
                result = submission.parse(GOOD.replace("Spined Crawler", name))
                self.assertEqual(result.errors, [])
                self.assertIn(kept, [mob.n for mob in result.mobs])
        self.assertTrue(errors(GOOD.replace("Spined Crawler", "x" * 70)))

    def test_other_languages_typography_is_kept_plain(self):
        # French: a no-break space before ":", curly apostrophes, guillemets; Chinese: full-width punctuation.
        text = (V3.replace("Spined Crawler", "Ours d\u2019Orneval\u2026")
                .replace("@i^4874^Pattern: Hillman's Cloak, Belt", "@i^4874^Patron\u00a0: Cape \u00ab\u00a0Rouge\u00a0\u00bb")
                .replace("@m^1440^Ashenvale", "@m^1440^\u517b\u6b96\u573a\uff1a\u6d4b\u8bd5\uff08\u4e00\uff09"))
        result = submission.parse(text)
        self.assertEqual(result.errors, [])
        self.assertIn("Ours d'Orneval...", [mob.n for mob in result.mobs])
        self.assertEqual(result.item_names[4874], "Patron : Cape ' Rouge '")
        self.assertEqual(result.map_names[1440], "\u517b\u6b96\u573a:\u6d4b\u8bd5(\u4e00)")
        self.assertIn("^Ours d'Orneval...^", result.text())          # kept as cleaned
        self.assertTrue(errors(V3.replace("@m^1440^Ashenvale", "@m^1440^\u2605\u2605")))   # nothing left of it

    def test_allows_normal_names(self):
        for name in ("Gath'Ilzogg", "Ol' Sooty", "Dun Garok Mountaineer", "Death's Head Acolyte", ""):
            with self.subTest(name):
                self.assertEqual(errors(GOOD.replace("Spined Crawler", name)), [])


V3 = (GOOD.replace("export 2^", "export 3^")
      + "@i^3010^Crawler Meat\n@i^4874^Pattern: Hillman's Cloak, Belt\n@m^1440^Ashenvale\n@c^2996^\n@c^4231^\n")


class VersionThreeTests(unittest.TestCase):
    def test_names_and_crafted_round_trip(self):
        result = submission.parse(V3)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.version, 3)
        self.assertEqual(result.item_names[3010], "Crawler Meat")
        self.assertEqual(result.item_names[4874], "Pattern: Hillman's Cloak, Belt")
        self.assertEqual(result.map_names, {1440: "Ashenvale"})
        self.assertEqual(result.crafted, {2996, 4231})
        self.assertEqual(len(result.mobs), 2)
        self.assertEqual(submission.parse(result.text()).text(), result.text())

    def test_version_two_still_accepted_and_kept(self):
        result = submission.parse(GOOD)
        self.assertEqual((result.errors, result.version), ([], 2))
        self.assertTrue(result.text().startswith("GoldScout-export 2^"))

    def test_rejects_bad_extra_lines(self):
        cases = {
            "names in a v2 export": GOOD + "@i^3010^Crawler Meat\n",
            "unknown kind": V3 + "@x^1^thing\n",
            "empty name": V3.replace("Crawler Meat", ""),
            "too long": V3.replace("Crawler Meat", "x" * 70),
            "crafted with a name": V3.replace("@c^2996^", "@c^2996^Bolt"),
            "bad id": V3.replace("@m^1440^", "@m^-4^"),
            "extra field": V3.replace("@m^1440^Ashenvale", "@m^1440^Ash^envale"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(errors(text))

    def test_merge_writes_community_crafted(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Data_Community.lua"
            results = [submission.parse(V3)]
            merge_data.write_lua(merge_data.merge([r.mobs for r in results], 1000), 5, target, 1,
                                 merge_data.sources_of(results), 1000, results[0].crafted)
            text = target.read_text(encoding="utf-8")
            self.assertIn("ns.COMMUNITY_CRAFTED = {", text)
            self.assertIn("[2996] = true, [4231] = true,", text)


class OutlierTests(unittest.TestCase):
    OTHERS = submission.parse(
        "GoldScout-export 2^abcdefghijkl^3\n"
        "3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^2674:20:20,3010:1200:1200^\n").mobs

    def test_sharply_different_rates_are_flagged(self):
        big = (CLATTERING.replace("3812^11^0", "3812^100^0").replace("^11^Clattering", "^100^Clattering")
               .replace("2674:4:4", "2674:90:90"))
        result = submission.compare(submission.parse("GoldScout-export 2^abcdefghijkl^3\n" + big), [self.OTHERS])
        self.assertTrue(result.warnings)

    def test_one_lucky_drop_is_not_flagged(self):
        # Held uploads: one green world drop from a mob nobody else saw it from, in 30-40 kills.
        def export(drops):
            mob = (CLATTERING.replace("3812^11^0", "3812^40^0").replace("^11^Clattering", "^40^Clattering")
                   .replace("2674:4:4", "2674:4:4,9999:%d:%d" % (drops, drops)))
            return submission.parse("GoldScout-export 2^abcdefghijkl^3\n" + mob)
        self.assertFalse(any("item 9999" in w for w in submission.compare(export(1), [self.OTHERS]).warnings))
        self.assertTrue(any("item 9999" in w for w in submission.compare(export(3), [self.OTHERS]).warnings))

    def test_small_samples_are_not_flagged(self):
        result = submission.compare(submission.parse(GOOD), [self.OTHERS])
        self.assertEqual(result.warnings, [])

    def test_quest_items_are_not_compared(self):
        # Two players held for 0% of a quest item others saw 40% of: it drops only while you're on the quest.
        big = (CLATTERING.replace("3812^11^0", "3812^100^0").replace("^11^Clattering", "^100^Clattering")
               .replace("2674:4:4", "2674:90:90"))
        export = "GoldScout-export 2^abcdefghijkl^3\n" + big
        flagged = submission.compare(submission.parse(export), [self.OTHERS]).warnings
        self.assertTrue(any("item 2674" in w for w in flagged))
        # Known as a quest item from other players' exports...
        result = submission.compare(submission.parse(export), [self.OTHERS], quest_items={2674})
        self.assertFalse(any("item 2674" in w for w in result.warnings))
        # ...or from this export's own item details.
        own = submission.parse(export)
        own.item_meta[2674] = (1, submission.QUEST_ITEM_CLASS, False)
        self.assertFalse(any("item 2674" in w for w in submission.compare(own, [self.OTHERS]).warnings))


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
        # A hostile line that fails the checks, and a hostile name that's only cleaned: neither is quoted back.
        for evil, verdict in ((GOOD + "@everyone `rm -rf` <script>\n", "can't be accepted"),
                              (GOOD.replace("Spined Crawler", "@everyone `rm -rf` <script>"), "passed every check")):
            comment = self.run_check({"number": 1, "body": form_body(evil),
                                      "user": {"id": 5, "login": "x", "type": "User"}})
            self.assertIn(verdict, comment)
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

    def test_merged_lists_issues_main_already_has(self):
        # Main holds player 1's export at snapshot 3 for this install. #5 (snapshot 3) and #4 (an older
        # snapshot 2) are in the data; #6 (snapshot 7, newer) isn't yet; #8 is another player with nothing on main.
        def issue(number, export, user_id=1):
            return {"number": number, "body": form_body(export), "labels": ["data-valid"],
                    "user": {"id": user_id, "login": "p%d" % user_id, "type": "User"}}
        issues = [issue(5, GOOD), issue(4, GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl^2")),
                  issue(6, GOOD.replace("^abcdefghijkl^3", "^abcdefghijkl^7")), issue(8, GOOD, 2),
                  {"number": 9, "body": "no export here", "labels": [], "user": {"id": 1, "type": "User"}}]
        Path("issues.jsonl").write_text("\n".join(json.dumps(i) for i in issues), encoding="utf-8")
        on_main = {"1-abcdefghijkl.txt": GOOD}
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            data_bot.merged("issues.jsonl", read=lambda path: on_main.get(path.name))
        self.assertEqual(printed.getvalue().split(), ["4", "5"])

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

    def test_an_upload_already_stored_is_skipped_without_its_export(self):
        # The hourly merge downloads only new and changed exports (tools/fetch_uploads.py).
        self.upload(seq=5)
        stored = (data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").read_text(encoding="utf-8")
        listing = {"uploads": [{"install_id": "abcdefghijkl", "seq": 5, "terms": "2026-11-07",
                                "created_at": 1_800_000_000}]}                  # no body
        Path("uploads.json").write_text(json.dumps(listing), encoding="utf-8")
        Path("pr_body.md").write_text("", encoding="utf-8")
        data_bot.collect_uploads("uploads.json")
        self.assertEqual((data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").read_text(encoding="utf-8"), stored)
        body = Path("pr_body.md").read_text(encoding="utf-8")
        self.assertIn("No new companion uploads.", body)
        self.assertNotIn("failed validation", body)

    def test_checks_against_everyone_else_once_added_up(self):
        # submission.tally of every file, minus the player's own, gives what others() used to: the player's own
        # earlier file never counts against them.
        (data_bot.SUBMISSIONS / "9-zzzzzzzzzzzz.txt").write_text(
            "GoldScout-export 2^zzzzzzzzzzzz^3\n3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^"
            "2674:20:20,3010:1200:1200^\n", encoding="utf-8")
        big = (CLATTERING.replace("3812^11^0", "3812^100^0").replace("^11^Clattering", "^100^Clattering")
               .replace("2674:4:4", "2674:90:90"))
        export = "GoldScout-export 2^abcdefghijkl^%d\n" + big + "\n"
        (data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").write_text(export % 3, encoding="utf-8")
        files = {p.name: submission.parse(p.read_text(encoding="utf-8")) for p in data_bot.SUBMISSIONS.glob("*.txt")}
        totals = submission.tally(f.mobs for f in files.values())
        own = submission.tally([files["c-abcdefghijkl.txt"].mobs])
        fresh = submission.parse(export % 4)
        expected = submission.compare(submission.parse(export % 4), data_bot.others(exclude_install="abcdefghijkl"))
        self.assertTrue(expected.warnings)
        self.assertEqual(submission.compare(fresh, None, totals=totals, minus=own).warnings, expected.warnings)

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

    def upload(self, install="abcdefghijkl", seq=5, created=None):
        entry = {"install_id": install, "seq": seq, "terms": "2026-11-07",
                 "body": GOOD.replace("abcdefghijkl", install).replace("^3\n", "^%d\n" % seq, 1)}
        if created is not None:
            entry["created_at"] = created
        Path("uploads.json").write_text(json.dumps({"uploads": [entry]}), encoding="utf-8")
        Path("pr_body.md").write_text("", encoding="utf-8")
        data_bot.collect_uploads("uploads.json")
        return Path("pr_body.md").read_text(encoding="utf-8")

    def test_a_companion_upload_for_an_install_from_the_form_waits_for_review(self):
        # Form submissions make install IDs public, so someone else could register one on the upload service.
        (data_bot.SUBMISSIONS / "7-abcdefghijkl.txt").write_text(GOOD, encoding="utf-8")
        body = self.upload()
        self.assertFalse((data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").exists())
        self.assertIn("first shared through the GitHub form", body)
        self.assertIn("Held back for review", body)
        with mock.patch.object(data_bot, "approved_installs", return_value={"abcdefghijkl"}):
            self.upload()
        self.assertTrue((data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").exists())
        self.upload(seq=6)   # once its companion file exists, later uploads go straight in
        self.assertEqual(submission.parse((data_bot.SUBMISSIONS / "c-abcdefghijkl.txt").read_text(
            encoding="utf-8")).seq, 6)

    def test_upload_dates_are_recorded_once(self):
        dates = data_bot.SUBMISSIONS.parent / "install-dates.json"
        self.upload(created=1_800_000_000)
        self.assertEqual(json.loads(dates.read_text(encoding="utf-8")), {"abcdefghijkl": 1_800_000_000})
        self.upload(seq=6, created=1_900_000_000)
        self.upload(install="zzzzzzzzzzzz", created=1_800_000_500)
        self.assertEqual(json.loads(dates.read_text(encoding="utf-8")),
                         {"abcdefghijkl": 1_800_000_000, "zzzzzzzzzzzz": 1_800_000_500})

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

    def test_new_installs_wait_to_add_mobs_nobody_else_has(self):
        now = 1_800_000_000
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "submissions"
            folder.mkdir()
            # An established player has only the Clattering Crawler; a day-old install has both crawlers.
            (folder / "8-zzzzzzzzzzzz.txt").write_text("GoldScout-export 2^zzzzzzzzzzzz^3\n" + CLATTERING + "\n",
                                                        encoding="utf-8")
            (folder / "c-abcdefghijkl.txt").write_text(GOOD, encoding="utf-8")
            (Path(tmp) / "install-dates.json").write_text(json.dumps({"abcdefghijkl": now - 86400}), encoding="utf-8")
            loaded = {r.install_id: r for r in merge_data.load(folder, now=now)}
            self.assertEqual([m.npc for m in loaded["abcdefghijkl"].mobs], [3812])   # 3814 waits
            self.assertEqual([m.npc for m in loaded["zzzzzzzzzzzz"].mobs], [3812])
            loaded = {r.install_id: r for r in merge_data.load(folder, now=now + 3 * 86400)}
            self.assertEqual(sorted(m.npc for m in loaded["abcdefghijkl"].mobs), [3812, 3814])   # three days on

    def test_installs_from_before_probation_started_are_established(self):
        # The first run that dated every install held back 196 mobs already shipped; those players weren't new.
        start = merge_data.PROBATION_FROM
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "submissions"
            folder.mkdir()
            (folder / "8-zzzzzzzzzzzz.txt").write_text("GoldScout-export 2^zzzzzzzzzzzz^3\n" + CLATTERING + "\n",
                                                        encoding="utf-8")
            (folder / "c-abcdefghijkl.txt").write_text(GOOD, encoding="utf-8")
            dates = Path(tmp) / "install-dates.json"
            dates.write_text(json.dumps({"abcdefghijkl": start - 3600}), encoding="utf-8")   # an hour before
            loaded = {r.install_id: r for r in merge_data.load(folder, now=start + 3600)}
            self.assertEqual(len(loaded["abcdefghijkl"].mobs), 2)
            dates.write_text(json.dumps({"abcdefghijkl": start + 60}), encoding="utf-8")       # just after
            loaded = {r.install_id: r for r in merge_data.load(folder, now=start + 3600)}
            self.assertEqual(len(loaded["abcdefghijkl"].mobs), 1)

    def test_installs_without_a_date_are_established(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "submissions"
            folder.mkdir()
            (folder / "c-abcdefghijkl.txt").write_text(GOOD, encoding="utf-8")
            self.assertEqual(len(merge_data.load(folder)[0].mobs), 2)
            (Path(tmp) / "install-dates.json").write_text("not json", encoding="utf-8")
            self.assertEqual(len(merge_data.load(folder)[0].mobs), 2)

    def test_one_player_is_capped(self):
        heavy = submission.parse(
            "GoldScout-export 2^abcdefghijkl^3\n3812^2000^0^19^20^1440^0.1179^0.2989^500^Clattering Crawler^3010:1200:1200^\n").mobs
        merged = merge_data.merge([heavy, submission.parse(GOOD).mobs], max_per_player=1000)
        self.assertEqual(merged[3812]["k"], 1011)
        self.assertEqual(merged[3812]["i"][3010][0], 600 + 7)

    def test_dungeon_zones_without_a_position(self):
        # Inside a dungeon the game gives no position, only the zone: version 6 can say that, older versions can't.
        dungeon = "3812^40^0^19^20^291^0.0000^0.0000^0^Defias Miner^3010:7:7^"
        self.assertEqual(submission.parse("GoldScout-export 6^abcdefghijkl^3\n" + dungeon + "\n").errors, [])
        self.assertTrue(submission.parse("GoldScout-export 5^abcdefghijkl^3\n" + dungeon + "\n").errors)
        # A zone with a stray position count, or a position, still has to be whole.
        self.assertTrue(submission.parse("GoldScout-export 6^abcdefghijkl^3\n"
                                         + dungeon.replace("^0.0000^0.0000^0^", "^0.5000^0.5000^0^") + "\n").errors)
        # The merge keeps the zone players reported most, without a spot; a real position still wins.
        zoned = submission.parse("GoldScout-export 6^abcdefghijkl^3\n" + dungeon + "\n")
        other = submission.parse("GoldScout-export 6^zzzzzzzzzzzz^3\n" + dungeon.replace("^291^", "^292^")
                                 .replace("3812^40^", "3812^10^") + "\n")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Data_Community.lua"
            merge_data.write_lua(merge_data.merge([zoned.mobs, other.mobs], 1000), 5, target, 2,
                                 merge_data.sources_of([zoned, other]), 1000)
            line = next(l for l in target.read_text(encoding="utf-8").splitlines() if l.startswith("  [3812] ="))
        self.assertIn("m = 291", line)
        self.assertNotIn(", x = ", line)                               # no spot (not lmax)
        merged = merge_data.merge([zoned.mobs, submission.parse(GOOD).mobs], 1000)
        self.assertEqual(dict(merged[3812]["zones"]), {291: 40})
        self.assertIn(1440, merged[3812]["maps"])                      # the outdoor player's spot

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
