"""The database itself must reject bad rows, not only the pipeline code. Also checks the migration is safe and the
committed database is at schema version 2."""

import os
import sqlite3
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

import migrate_schema  # noqa: E402

SCHEMA = os.path.join(BASE, "database", "schema.sql")
COMMITTED_DB = os.path.join(BASE, "database", "aligned.db")


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute("INSERT INTO programs (university, program_name) VALUES ('U', 'P')")
    conn.execute("INSERT INTO skills (canonical_name) VALUES ('Python')")
    yield conn
    conn.close()


def _gap(conn, **over):
    row = {"program_id": 1, "skill_id": 1, "cluster_id": None, "program_coverage_rate": 0.1, "market_demand_rate": 0.4,
           "p_value": 0.01, "q_value": 0.02, "test_method": "z_test"}
    row.update(over)
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO gap_scores ({cols}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))


def test_rates_must_be_proportions(db):
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, market_demand_rate=1.4)
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, program_coverage_rate=-0.1)


def test_p_and_q_values_must_be_probabilities(db):
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, q_value=2)


def test_unknown_test_method_is_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, test_method="t_test")


def test_overall_market_gap_cannot_be_duplicated(db):
    """cluster_id NULL means overall market; a plain UNIQUE would let duplicates through because NULLs differ."""
    _gap(db)
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db)


def test_same_skill_in_different_scopes_is_allowed(db):
    db.execute("INSERT INTO role_clusters (role_label) VALUES ('Data')")
    _gap(db)
    _gap(db, cluster_id=1)


def test_gap_needs_real_program_and_skill(db):
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, program_id=99)
    with pytest.raises(sqlite3.IntegrityError):
        _gap(db, skill_id=99)


def test_extraction_enums_and_uniqueness(db):
    ins = "INSERT INTO extractions (source_type, source_id, skill_id, confidence, method) VALUES (?, ?, ?, ?, ?)"
    db.execute(ins, ("course", "1", 1, 1.0, "baseline_keyword"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("course", "1", 1, 1.0, "baseline_keyword"))  # duplicate
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("video", "1", 1, 1.0, "baseline_keyword"))  # unknown source type
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("course", "2", 1, 1.0, "magic"))  # unknown method
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("course", "3", 1, 7.0, "llm"))  # confidence out of range
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("course", "4", None, 1.0, "llm"))  # skill is required


def test_recommendation_tier_and_uniqueness(db):
    ins = "INSERT INTO recommendations (program_id, skill_id, cluster_id, priority_tier) VALUES (1, 1, NULL, ?)"
    db.execute(ins, ("high",))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("high",))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO recommendations (program_id, skill_id, cluster_id, priority_tier) VALUES (1, 1, NULL, 'urgent')")


def test_posting_rules(db):
    ins = "INSERT INTO postings (posting_id, source, salary_min) VALUES (?, ?, ?)"
    db.execute(ins, ("a", "adzuna", 50000))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("b", "somewhere_else", None))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(ins, ("c", "adzuna", -5))


def test_posting_cluster_map_has_a_primary_key(db):
    db.execute("INSERT INTO postings (posting_id, source) VALUES ('p', 'adzuna')")
    db.execute("INSERT INTO role_clusters (role_label) VALUES ('Data')")
    db.execute("INSERT INTO posting_cluster_map VALUES ('p', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO posting_cluster_map VALUES ('p', 1)")


def test_program_and_course_rules(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO programs (university, program_name) VALUES ('U', 'P')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO courses (program_id, course_name, is_elective) VALUES (1, 'X', 5)")


def test_main_extraction_query_uses_the_index(db):
    plan = db.execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(DISTINCT source_id) FROM extractions "
        "WHERE source_type = 'posting' AND method = 'baseline_keyword' AND skill_id = 1"
    ).fetchall()
    assert "idx_extractions_lookup" in " ".join(str(r) for r in plan)


def test_committed_database_is_version_2_and_clean():
    conn = sqlite3.connect(COMMITTED_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # extractions.source_id is polymorphic, so no foreign key can protect it; check every id resolves here instead
    orphans = conn.execute(
        """
        SELECT COUNT(*) FROM extractions e
        WHERE (e.source_type = 'posting' AND e.source_id NOT IN (SELECT posting_id FROM postings))
           OR (e.source_type = 'course' AND CAST(e.source_id AS INTEGER) NOT IN (SELECT course_id FROM courses))
        """
    ).fetchone()[0]
    assert orphans == 0
    conn.close()


def _legacy_db(path):
    """A version-1 style database: same tables, no constraints, no version stamp."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE programs (program_id INTEGER PRIMARY KEY AUTOINCREMENT, university TEXT NOT NULL, program_name TEXT NOT NULL, tier TEXT, url TEXT);
        CREATE TABLE skills (skill_id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_name TEXT NOT NULL UNIQUE, taxonomy_source TEXT, category TEXT);
        INSERT INTO programs (university, program_name) VALUES ('U', 'P');
        INSERT INTO skills (canonical_name) VALUES ('Python');
        """
    )
    return conn


def test_migration_copies_rows_stamps_version_and_is_idempotent(tmp_path):
    path = str(tmp_path / "old.db")
    _legacy_db(path).close()
    assert migrate_schema.migrate(path) == "migrated"
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 1
    conn.close()
    assert migrate_schema.migrate(path) == "already current"


def test_migration_leaves_original_untouched_when_data_breaks_a_rule(tmp_path):
    path = str(tmp_path / "bad.db")
    conn = _legacy_db(path)
    conn.execute("INSERT INTO programs (university, program_name) VALUES ('U', 'P')")  # duplicate natural key
    conn.commit()
    conn.close()
    with pytest.raises(migrate_schema.MigrationError):
        migrate_schema.migrate(path)
    assert migrate_schema.schema_version(path) == 0
    assert not os.path.exists(path + ".migrating")
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 2
    conn.close()
