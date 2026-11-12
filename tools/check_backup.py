#!/usr/bin/env python3
"""Proves a database backup restores, by loading it into a throwaway local D1
database and checking every table in server/schema.sql came back. Run by
.github/workflows/backup.yml before a backup is kept.

  python tools/check_backup.py backup.sql

Prints each table's row count (counts only, never rows: the backup holds
install IDs and hashed addresses, and CI logs are public). Exits 1 if the
restore fails or a table is missing.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"


def run(command):
    """Runs a wrangler command in server/: (succeeded, stdout)."""
    result = subprocess.run(command, cwd=SERVER, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        # wrangler's errors, not data: an import that fails names the statement number, not its values.
        print(result.stderr[-2000:], file=sys.stderr)
    return result.returncode == 0, result.stdout


def schema_tables(schema=None):
    text = schema if schema is not None else (SERVER / "schema.sql").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", text)))


def local(persist, *args):
    """A wrangler d1 execute against the throwaway database in `persist`."""
    return ["npx", "wrangler", "d1", "execute", "goldscout", "--local", "--persist-to", str(persist), *args]


def query(runner, persist, sql):
    ok, out = runner(local(persist, "--json", "--command", sql))
    if not ok:
        return None
    try:
        return json.loads(out[out.index("["):])[0]["results"]
    except (ValueError, KeyError, IndexError):
        return None


def check(path, persist, runner=run, schema=None):
    """None if the backup restores with every table, else the problem. Also returns row counts."""
    ok, _ = runner(local(persist, "--yes", "--file", str(path)))
    if not ok:
        return "the backup didn't load into an empty database", {}
    rows = query(runner, persist, "SELECT name FROM sqlite_master WHERE type = 'table'")
    if rows is None:
        return "couldn't list the restored tables", {}
    restored = {row["name"] for row in rows}
    missing = [name for name in schema_tables(schema) if name not in restored]
    if missing:
        return "tables missing from the backup: " + ", ".join(missing), {}
    counts = {}
    for name in schema_tables(schema):
        result = query(runner, persist, "SELECT COUNT(*) AS n FROM %s" % name)
        if result is None:
            return "couldn't count the rows in " + name, {}
        counts[name] = result[0]["n"]
    return None, counts


def main(argv):
    path = Path(argv[1]).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        print("FAIL: %s is missing or empty" % path)
        return 1
    with tempfile.TemporaryDirectory() as persist:   # never the local dev database
        problem, counts = check(path, persist)
    lines = ["| Table | Rows |", "|---|---|"] + ["| %s | %d |" % item for item in sorted(counts.items())]
    if problem:
        print("FAIL: " + problem)
        return 1
    report = "Backup restores: %d tables, %d rows, %.1f MB.\n\n%s" % (
        len(counts), sum(counts.values()), path.stat().st_size / 1e6, "\n".join(lines))
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
