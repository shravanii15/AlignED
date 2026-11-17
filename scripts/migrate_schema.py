"""
migrate_schema.py: upgrade an existing AlignED database to schema version 2 (constraints and indexes).

    python scripts/migrate_schema.py                    # migrates database/aligned.db in place
    python scripts/migrate_schema.py --db path/to.db

SQLite cannot add CHECK or UNIQUE constraints to an existing table, so the migration builds a new database file
from database/schema.sql, copies every row across by column name, verifies the result, and only then swaps it
into place. If any step fails the original file is untouched. It is safe to run twice: a database already at
version 2 is left alone.
"""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_utils import atomic_replace, foreign_key_violations  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "database", "aligned.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
TARGET_VERSION = 2

# Parents before children, so foreign keys hold while copying.
COPY_ORDER = ("programs", "courses", "postings", "skills", "extractions", "role_clusters", "posting_cluster_map",
              "skill_trends", "recommendations", "gap_scores", "ingest_runs", "rejected_postings")


class MigrationError(RuntimeError):
    pass


def schema_version(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _columns(conn, schema, table):
    return [r[1] for r in conn.execute(f'PRAGMA {schema}.table_info("{table}")')]


def migrate(db_path=DEFAULT_DB, schema_path=SCHEMA_PATH):
    """Returns 'migrated' or 'already current'. Raises MigrationError and leaves db_path untouched on any problem."""
    if schema_version(db_path) >= TARGET_VERSION:
        return "already current"
    new_path = db_path + ".migrating"
    if os.path.exists(new_path):
        os.remove(new_path)
    conn = sqlite3.connect(new_path)
    try:
        with open(schema_path, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("ATTACH DATABASE ? AS old", (db_path,))
        old_tables = {r[0] for r in conn.execute("SELECT name FROM old.sqlite_master WHERE type = 'table'")}
        counts = {}
        for table in COPY_ORDER:
            if table not in old_tables:
                continue
            cols = [c for c in _columns(conn, "main", table) if c in _columns(conn, "old", table)]
            col_list = ", ".join(f'"{c}"' for c in cols)
            try:
                conn.execute(f'INSERT INTO main."{table}" ({col_list}) SELECT {col_list} FROM old."{table}"')
            except sqlite3.IntegrityError as exc:
                raise MigrationError(f"Existing rows in '{table}' break a new rule: {exc}") from exc
            counts[table] = conn.execute(f'SELECT COUNT(*) FROM old."{table}"').fetchone()[0]
        conn.commit()
        for table, expected in counts.items():
            got = conn.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
            if got != expected:
                raise MigrationError(f"Row count mismatch in '{table}': {expected} before, {got} after")
        if foreign_key_violations(conn):
            raise MigrationError("PRAGMA foreign_key_check reported violations")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationError("PRAGMA integrity_check failed")
        conn.execute("DETACH DATABASE old")
        conn.execute("VACUUM")
        conn.close()
        atomic_replace(new_path, db_path)
        return "migrated"
    except Exception:
        conn.close()
        if os.path.exists(new_path):
            os.remove(new_path)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--db", default=DEFAULT_DB)
    args = parser.parse_args(argv)
    print(f"{args.db}: {migrate(args.db)}")


if __name__ == "__main__":
    main()
