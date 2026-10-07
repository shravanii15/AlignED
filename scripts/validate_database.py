"""
validate_database.py: integrity checks for the AlignED SQLite database.

validate_database(conn) returns a list of human-readable problems (an empty
list means the database passed). It is used by rebuild_all.py before a
rebuilt database is allowed to replace the current one, and by the tests.

Checks:
  - PRAGMA foreign_key_check is clean
  - no duplicate posting->cluster mappings, extraction rows, gap rows, or
    recommendation rows
  - every gap row has gap_value > 0 and q_value < 0.05
  - every recommendation references an existing gap row for the same
    program, skill and scope
  - priority tiers are consistent with priority scores within each
    program and scope (higher tier never has a lower score than a lower tier)
  - trend labels agree with q_value and slope

Run:  python scripts/validate_database.py [path/to/aligned.db]
"""

import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
SIGNIFICANCE = 0.05
TIER_RANK = {"high": 2, "medium": 1, "low": 0}


def validate_database(conn):
    problems = []

    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"foreign_key_check reported {len(fk)} violation(s), e.g. {fk[0]}")

    duplicate_checks = {
        "posting_cluster_map": "SELECT posting_id, COUNT(*) FROM posting_cluster_map GROUP BY posting_id HAVING COUNT(*) > 1",
        "extractions": "SELECT source_type, source_id, skill_id, method, COUNT(*) FROM extractions GROUP BY 1,2,3,4 HAVING COUNT(*) > 1",
        "gap_scores": "SELECT program_id, skill_id, IFNULL(cluster_id, -1), COUNT(*) FROM gap_scores GROUP BY 1,2,3 HAVING COUNT(*) > 1",
        "recommendations": "SELECT program_id, skill_id, IFNULL(cluster_id, -1), COUNT(*) FROM recommendations GROUP BY 1,2,3 HAVING COUNT(*) > 1",
    }
    for table, sql in duplicate_checks.items():
        dupes = conn.execute(sql).fetchall()
        if dupes:
            problems.append(f"{table}: {len(dupes)} duplicate group(s), e.g. {dupes[0]}")

    bad_gap = conn.execute(
        "SELECT COUNT(*) FROM gap_scores WHERE gap_value IS NULL OR gap_value <= 0 OR q_value IS NULL OR q_value >= ?",
        (SIGNIFICANCE,),
    ).fetchone()[0]
    if bad_gap:
        problems.append(f"gap_scores: {bad_gap} row(s) with gap_value <= 0 or q_value >= {SIGNIFICANCE}")

    orphan_recs = conn.execute(
        """
        SELECT COUNT(*) FROM recommendations r
        WHERE NOT EXISTS (
            SELECT 1 FROM gap_scores g
            WHERE g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        )
        """
    ).fetchone()[0]
    if orphan_recs:
        problems.append(f"recommendations: {orphan_recs} row(s) with no matching gap_scores row")

    rows = conn.execute(
        "SELECT program_id, IFNULL(cluster_id, -1), priority_tier, priority_score FROM recommendations"
    ).fetchall()
    scores_by_scope = {}
    for program_id, cluster, tier, score in rows:
        if tier not in TIER_RANK:
            problems.append(f"recommendations: unknown tier {tier!r}")
            continue
        scores_by_scope.setdefault((program_id, cluster), []).append((TIER_RANK[tier], score))
    for scope, entries in scores_by_scope.items():
        for rank_a, score_a in entries:
            for rank_b, score_b in entries:
                if rank_a > rank_b and score_a < score_b:
                    problems.append(f"recommendations: tier/score inconsistency in scope {scope}")
                    break
            else:
                continue
            break

    bad_trends = conn.execute(
        """
        SELECT COUNT(*) FROM skill_trends
        WHERE (trend_label = 'rising'  AND (q_value >= ? OR slope <= 0))
           OR (trend_label = 'falling' AND (q_value >= ? OR slope >= 0))
           OR (trend_label = 'no clear trend' AND q_value < ? AND slope != 0)
        """,
        (SIGNIFICANCE, SIGNIFICANCE, SIGNIFICANCE),
    ).fetchone()[0]
    if bad_trends:
        problems.append(f"skill_trends: {bad_trends} row(s) whose label disagrees with q_value/slope")

    # Ingestion: loaded postings must be unique by content, and every run
    # must be closed out with a status.
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "ingest_runs" in tables:
        dup_content = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT 1 FROM postings WHERE source = 'adzuna' AND content_hash IS NOT NULL
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if dup_content:
            problems.append(f"postings: {dup_content} duplicated adzuna content hash(es) (reposts that should have been skipped)")
        open_runs = conn.execute("SELECT COUNT(*) FROM ingest_runs WHERE status IS NULL OR finished_at IS NULL").fetchone()[0]
        if open_runs:
            problems.append(f"ingest_runs: {open_runs} run(s) never finished")
        bad_arith = conn.execute(
            """
            SELECT COUNT(*) FROM ingest_runs
            WHERE fetched != rejected + duplicate_ids + duplicate_content + inserted
            """
        ).fetchone()[0]
        if bad_arith:
            problems.append(f"ingest_runs: {bad_arith} run(s) whose counts do not add up to the number fetched")

    return problems


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    problems = validate_database(conn)
    conn.close()
    if problems:
        print(f"{path}: {len(problems)} problem(s)")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"{path}: all integrity checks passed")


if __name__ == "__main__":
    main()
