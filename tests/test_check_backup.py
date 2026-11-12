"""tools/check_backup.py: a backup is only kept once it restores with every table."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_backup  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS installs (install_id TEXT PRIMARY KEY);
CREATE INDEX IF NOT EXISTS installs_updated ON installs (install_id);
CREATE TABLE IF NOT EXISTS admin_stats (name TEXT PRIMARY KEY);
"""


class FakeD1:
    """Answers the local wrangler d1 commands check_backup sends."""

    def __init__(self, tables=("installs", "admin_stats"), counts=None, load_ok=True):
        self.tables, self.counts, self.load_ok = tables, counts or {}, load_ok
        self.commands = []

    def __call__(self, command):
        self.commands.append(command)
        assert command[:6] == ["npx", "wrangler", "d1", "execute", "goldscout", "--local"]
        if "--file" in command:
            return self.load_ok, ""
        sql = command[-1]
        if "sqlite_master" in sql:
            rows = [{"name": name} for name in self.tables] + [{"name": "_cf_KV"}]
        else:
            rows = [{"n": self.counts.get(sql.split()[-1], 0)}]
        return True, "Some banner\n" + json.dumps([{"results": rows, "success": True}])


class CheckBackupTests(unittest.TestCase):
    def test_schema_tables_are_read_from_the_create_statements(self):
        self.assertEqual(check_backup.schema_tables(SCHEMA), ["admin_stats", "installs"])
        self.assertIn("installs", check_backup.schema_tables())          # the real schema

    def test_a_complete_backup_passes_with_row_counts(self):
        d1 = FakeD1(counts={"installs": 12, "admin_stats": 1})
        self.assertEqual(check_backup.check("b.sql", "/tmp/x", d1, SCHEMA), (None, {"admin_stats": 1, "installs": 12}))

    def test_every_command_uses_the_throwaway_database(self):
        d1 = FakeD1()
        check_backup.check("b.sql", "/tmp/throwaway", d1, SCHEMA)
        for command in d1.commands:
            self.assertEqual(command[command.index("--persist-to") + 1], "/tmp/throwaway")

    def test_a_backup_that_does_not_load_fails(self):
        problem, _ = check_backup.check("b.sql", "/tmp/x", FakeD1(load_ok=False), SCHEMA)
        self.assertIn("didn't load", problem)

    def test_a_missing_table_fails(self):
        problem, _ = check_backup.check("b.sql", "/tmp/x", FakeD1(tables=("installs",)), SCHEMA)
        self.assertIn("admin_stats", problem)

    def test_an_empty_file_is_never_kept(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ):
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            empty = Path(folder) / "backup.sql"
            empty.write_text("")
            self.assertEqual(check_backup.main(["check_backup.py", str(empty)]), 1)
            self.assertEqual(check_backup.main(["check_backup.py", str(Path(folder) / "none.sql")]), 1)


if __name__ == "__main__":
    unittest.main()
