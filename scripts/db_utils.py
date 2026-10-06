"""
db_utils.py: shared helpers for scripts that rebuild parts of the database.

Why this exists: several pipeline scripts reload a table from scratch
(programs and courses, skills, role clusters). With SQLite foreign keys
switched on, a plain DELETE of a parent table fails while child tables
(gap_scores, recommendations, extractions, ...) still reference it, so the
documented rebuild could not be re-run against a populated database. The
fix is not to switch foreign keys off, it is to clear the tables that
depend on the one being reloaded first, in dependency order. That order is
read from the schema itself (PRAGMA foreign_key_list) instead of being
hand-maintained, so adding a table can't silently reintroduce the bug.
"""

import os
import sqlite3


def foreign_key_children(conn, table):
    """Tables that declare a foreign key pointing at `table`."""
    children = []
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        for row in conn.execute(f'PRAGMA foreign_key_list("{name}")'):
            if row[2] == table:  # row[2] is the referenced (parent) table
                children.append(name)
                break
    return children


def dependents_in_delete_order(conn, table):
    """Every table that (transitively) depends on `table` through foreign
    keys, ordered so children come before their parents. Does not include
    `table` itself."""
    order = []

    def visit(parent):
        for child in foreign_key_children(conn, parent):
            if child == parent or child in order:
                continue
            visit(child)
            if child not in order:
                order.append(child)

    visit(table)
    return order


def clear_table_and_dependents(conn, table, extra_deletes=()):
    """Delete all rows of `table`, after first deleting everything that
    depends on it, children first. `extra_deletes` is a sequence of
    (sql, params) for tables linked by value rather than by a declared
    foreign key (extractions.source_id points at courses/postings by id
    text, with no FK), which must also be cleared to stay consistent."""
    for child in dependents_in_delete_order(conn, table):
        conn.execute(f'DELETE FROM "{child}"')
    for sql, params in extra_deletes:
        conn.execute(sql, params)
    conn.execute(f'DELETE FROM "{table}"')


def foreign_key_violations(conn):
    """Rows reported by PRAGMA foreign_key_check (empty list when clean)."""
    return conn.execute("PRAGMA foreign_key_check").fetchall()


def atomic_replace(new_path, final_path):
    """Replace final_path with new_path in one step (os.replace is atomic
    on the same filesystem), so a failed rebuild never leaves a half-built
    database where the working one used to be."""
    os.replace(new_path, final_path)


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
