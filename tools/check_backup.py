#!/usr/bin/env python3
"""Proves a database backup restores into D1, and makes the file that does it.
Run by .github/workflows/backup.yml before a backup is kept.

  python tools/check_backup.py backup.sql [--restore-file restore.sql]

A D1 export can't be loaded back into D1 as it is: D1 refuses any statement
over 100 KB, and one row (an auction house's prices, a player's export) can
be bigger. So the export is loaded into plain SQLite, which has no such
limit, and written out again as restore SQL whose long values are inserted in
pieces (INSERT, then UPDATE ... || for the rest). That file is loaded into a
throwaway local D1 database, and every table in server/schema.sql must come
back with the same number of rows. --restore-file keeps it, for a real
restore (server/README.md).

Prints each table's row count (counts only, never rows: the backup holds
install IDs and hashed addresses, and CI logs are public). Exits 1 if
anything doesn't match.
"""
import argparse
import json
import os
import re
import sqlite3
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
# Characters of a long value per statement: at most 4 bytes each, doubled
# quotes 2, so a piece stays well under D1's 100 KB statement limit.
PIECE = 20000


def run(command):
    """Runs a wrangler command in server/: (succeeded, stdout)."""
    # shutil.which finds npx.cmd on Windows, where subprocess alone wouldn't.
    command = [shutil.which(command[0]) or command[0], *command[1:]]
    result = subprocess.run(command, cwd=SERVER, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        # wrangler's errors, not data: an import that fails names the statement number, not its values.
        print(result.stderr[-2000:], file=sys.stderr)
    return result.returncode == 0, result.stdout


def schema_tables(schema=None):
    text = schema if schema is not None else (SERVER / "schema.sql").read_text(encoding="utf-8")
    return sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", text)))


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return "X'%s'" % value.hex()
    if isinstance(value, (int, float)):
        return repr(value)
    return "'%s'" % str(value).replace("'", "''")


def load_dump(text):
    """The export loaded into an in-memory SQLite database."""
    db = sqlite3.connect(":memory:")
    db.executescript(text)
    return db


def user_tables(db):
    return [name for (name,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' ORDER BY name")]


def restore_statements(db, piece=PIECE):
    """D1-sized SQL that recreates every table, index and row in `db`."""
    yield "PRAGMA defer_foreign_keys = TRUE;"
    tables = user_tables(db)
    for name in tables:
        (sql,) = db.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
        yield sql + ";"
    for (sql,) in db.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL "
                             "AND tbl_name NOT LIKE '\\_cf\\_%' ESCAPE '\\' ORDER BY name"):
        yield sql + ";"
    for name in tables:
        info = db.execute('PRAGMA table_info("%s")' % name).fetchall()
        columns = [column[1] for column in info]
        keys = [column[1] for column in sorted(info, key=lambda c: c[5]) if column[5] > 0]
        by_rowid = not keys
        select = ("SELECT rowid, * FROM \"%s\"" if by_rowid else "SELECT NULL, * FROM \"%s\"") % name
        for row in db.execute(select):
            rowid, values = row[0], list(row[1:])
            rest = {}
            for i, value in enumerate(values):
                if isinstance(value, str) and len(value) > piece:
                    rest[columns[i]] = value[piece:]
                    values[i] = value[:piece]
            names = (["rowid"] if by_rowid else []) + columns
            first = ([rowid] if by_rowid else []) + values
            yield 'INSERT INTO "%s" (%s) VALUES (%s);' % (
                name, ", ".join('"%s"' % c for c in names), ", ".join(literal(v) for v in first))
            if by_rowid:
                where = "rowid = %d" % rowid
            else:
                where = " AND ".join('"%s" = %s' % (k, literal(row[1 + columns.index(k)])) for k in keys)
            for column, remaining in rest.items():
                for start in range(0, len(remaining), piece):
                    yield 'UPDATE "%s" SET "%s" = "%s" || %s WHERE %s;' % (
                        name, column, column, literal(remaining[start:start + piece]), where)


def fingerprint_sql(db, name):
    """One query giving a table's row count and each column's total length:
    a value that lost or gained a piece changes its column's total."""
    columns = [column[1] for column in db.execute('PRAGMA table_info("%s")' % name)]
    parts = ['COUNT(*) AS "n"'] + ['COALESCE(SUM(LENGTH("%s")), 0) AS "%s"' % (c, c) for c in columns]
    return 'SELECT %s FROM "%s"' % (", ".join(parts), name)


def fingerprint(db, name):
    cursor = db.execute(fingerprint_sql(db, name))
    return dict(zip([d[0] for d in cursor.description], cursor.fetchone()))


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


def check(dump, restore_path, persist, runner=run, schema=None):
    """None if the backup restores into D1 with every table and row, else the
    problem; also the row counts. Writes the restore SQL to `restore_path`."""
    try:
        db = load_dump(dump)
    except sqlite3.Error as error:
        return "the backup isn't valid SQL (%s)" % error, {}
    tables = schema_tables(schema)
    missing = [name for name in tables if name not in user_tables(db)]
    if missing:
        return "tables missing from the backup: " + ", ".join(missing), {}
    expected = {name: fingerprint(db, name) for name in tables}
    with open(restore_path, "w", encoding="utf-8", newline="\n") as handle:
        for statement in restore_statements(db):
            handle.write(statement + "\n")
    ok, _ = runner(local(persist, "--yes", "--file", str(restore_path)))
    if not ok:
        return "the restore SQL didn't load into an empty D1 database", {}
    for name in tables:
        result = query(runner, persist, fingerprint_sql(db, name))
        if result is None:
            return "couldn't read back the rows restored in " + name, {}
        got, want = result[0], expected[name]
        if got.get("n") != want["n"]:
            return "%s: %d rows in the backup but %s restored" % (name, want["n"], got.get("n")), {}
        changed = [column for column in want if column != "n" and got.get(column) != want[column]]
        if changed:
            return "%s: values in %s didn't come back whole" % (name, ", ".join(changed)), {}
    return None, {name: want["n"] for name, want in expected.items()}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("backup")
    parser.add_argument("--restore-file", help="keep the D1 restore SQL here")
    args = parser.parse_args(argv[1:])
    path = Path(args.backup).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        print("FAIL: %s is missing or empty" % path)
        return 1
    dump = path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as work:   # never the local dev database
        restore = Path(args.restore_file).resolve() if args.restore_file else Path(work) / "restore.sql"
        problem, counts = check(dump, restore, Path(work) / "d1")
    if problem:
        print("FAIL: " + problem)
        return 1
    lines = ["| Table | Rows |", "|---|---|"] + ["| %s | %d |" % item for item in sorted(counts.items())]
    report = "Backup restores into D1: %d tables, %d rows, %.1f MB.\n\n%s" % (
        len(counts), sum(counts.values()), path.stat().st_size / 1e6, "\n".join(lines))
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
