"""tools/check_backup.py: a backup is only kept once it restores into D1, and
rows bigger than D1's 100 KB statement limit are restored in pieces."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_backup  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS installs (install_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS installs_body ON installs (body);
CREATE TABLE IF NOT EXISTS ah_houses (region TEXT NOT NULL, house INTEGER NOT NULL, prices TEXT NOT NULL,
  PRIMARY KEY (region, house));
CREATE TABLE IF NOT EXISTS notes (text TEXT);
"""
# What a D1 export looks like: plain CREATEs, then INSERTs (and D1's own table).
EXPORT = """PRAGMA defer_foreign_keys=TRUE;
CREATE TABLE installs (install_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE ah_houses (region TEXT NOT NULL, house INTEGER NOT NULL, prices TEXT NOT NULL,
  PRIMARY KEY (region, house));
CREATE TABLE notes (text TEXT);
CREATE TABLE _cf_KV (key TEXT PRIMARY KEY, value BLOB);
INSERT INTO "installs" VALUES('abc','{"it''s": "small"}');
INSERT INTO "ah_houses" VALUES('us',1,'%s');
INSERT INTO "notes" VALUES(NULL);
INSERT INTO "notes" VALUES('two''s');
CREATE INDEX installs_body ON installs (body);
"""
BIG = "é'" + "x" * 150000 + "'end"     # 150 KB: over D1's statement limit on its own


def export(big=BIG):
    return EXPORT % big.replace("'", "''")


class FakeD1:
    """A local D1: SQLite that, like D1, refuses statements over 100 KB."""

    LIMIT = 100000

    def __init__(self, corrupt=None):
        self.db, self.commands, self.corrupt = sqlite3.connect(":memory:"), [], corrupt

    def __call__(self, command):
        self.commands.append(command)
        assert command[:6] == ["npx", "wrangler", "d1", "execute", "goldscout", "--local"]
        if "--file" in command:
            text = Path(command[command.index("--file") + 1]).read_text(encoding="utf-8")
            statement = ""
            for line in text.splitlines(keepends=True):
                statement += line
                if not sqlite3.complete_statement(statement):
                    continue                           # a CREATE TABLE spanning lines
                if len(statement.encode("utf-8")) > self.LIMIT:
                    return False, ""                   # statement too long: SQLITE_TOOBIG
                self.db.execute(statement)
                statement = ""
            if self.corrupt:
                self.db.execute(self.corrupt)
            return True, ""
        cursor = self.db.execute(command[-1])
        names = [d[0] for d in cursor.description]
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        return True, "Some banner\n" + json.dumps([{"results": rows, "success": True}])


class CheckBackupTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.restore = Path(folder.name) / "restore.sql"

    def check(self, dump, d1):
        return check_backup.check(dump, self.restore, "/tmp/throwaway", d1, SCHEMA)

    def test_schema_tables_are_read_from_the_create_statements(self):
        self.assertEqual(check_backup.schema_tables(SCHEMA), ["ah_houses", "installs", "notes"])
        self.assertIn("installs", check_backup.schema_tables())          # the real schema

    def test_a_row_over_the_statement_limit_restores_whole(self):
        d1 = FakeD1()
        self.assertEqual(self.check(export(), d1), (None, {"ah_houses": 1, "installs": 1, "notes": 2}))
        (prices,) = d1.db.execute("SELECT prices FROM ah_houses").fetchone()
        self.assertEqual(prices, BIG)
        self.assertEqual(d1.db.execute("SELECT body FROM installs").fetchone()[0], '{"it\'s": "small"}')
        statements = self.restore.read_text(encoding="utf-8").splitlines()
        self.assertTrue(all(len(s.encode("utf-8")) < 90000 for s in statements))
        self.assertTrue(any(s.startswith('UPDATE "ah_houses"') for s in statements))

    def test_the_d1_export_as_is_would_not_load(self):
        # Why the restore SQL exists: the export's own INSERT is too long for D1.
        self.assertTrue(any(len(line.encode("utf-8")) > FakeD1.LIMIT for line in export().splitlines()))

    def test_d1s_own_tables_and_indexes_are_recreated_but_not_its_internal_ones(self):
        self.check(export(), FakeD1())
        restore = self.restore.read_text(encoding="utf-8")
        self.assertIn("CREATE INDEX installs_body", restore)
        self.assertNotIn("_cf_KV", restore)

    def test_tables_without_a_primary_key_restore_by_rowid(self):
        d1 = FakeD1()
        self.check(export(), d1)
        self.assertEqual(d1.db.execute("SELECT text FROM notes ORDER BY rowid").fetchall(), [(None,), ("two's",)])

    def test_every_command_uses_the_throwaway_database(self):
        d1 = FakeD1()
        self.check(export(), d1)
        for command in d1.commands:
            self.assertEqual(command[command.index("--persist-to") + 1], "/tmp/throwaway")

    def test_a_value_that_comes_back_short_fails(self):
        problem, _ = self.check(export(), FakeD1(corrupt="UPDATE ah_houses SET prices = substr(prices, 1, 20000)"))
        self.assertIn("prices", problem)

    def test_a_lost_row_fails(self):
        problem, _ = self.check(export(), FakeD1(corrupt="DELETE FROM notes WHERE text IS NULL"))
        self.assertIn("notes", problem)

    def test_a_missing_table_fails(self):
        problem, _ = self.check(export().replace("CREATE TABLE notes (text TEXT);", "")
                                .replace('INSERT INTO "notes" VALUES(NULL);', "")
                                .replace('INSERT INTO "notes" VALUES(\'two\'\'s\');', ""), FakeD1())
        self.assertIn("notes", problem)

    def test_a_broken_export_fails(self):
        problem, _ = self.check("CREATE TABLE installs (", FakeD1())
        self.assertIn("isn't valid SQL", problem)

    def test_an_empty_file_is_never_kept(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ):
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            empty = Path(folder) / "backup.sql"
            empty.write_text("")
            self.assertEqual(check_backup.main(["check_backup.py", str(empty)]), 1)
            self.assertEqual(check_backup.main(["check_backup.py", str(Path(folder) / "none.sql")]), 1)


if __name__ == "__main__":
    unittest.main()
