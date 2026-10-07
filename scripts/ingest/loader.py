"""scripts/ingest/loader.py: load validated postings into SQLite.

Idempotent by construction: running the same snapshot twice inserts
nothing the second time. Every run is recorded in `ingest_runs`, and every
rejected posting in `rejected_postings` with its reason, so data quality is
visible over time instead of only in console output.
"""

import json
import sqlite3
from datetime import datetime, timezone

from ingest.quality import content_hash, normalize_adzuna, validate_posting

DEGRADED_REJECT_RATE = 0.30  # more than this share rejected marks the run degraded

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"

INGEST_DDL = """
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    snapshot_path TEXT,
    fetched INTEGER,
    rejected INTEGER,
    duplicate_ids INTEGER,
    duplicate_content INTEGER,
    inserted INTEGER,
    warnings INTEGER,
    status TEXT
);
CREATE TABLE IF NOT EXISTS rejected_postings (
    rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    posting_id TEXT,
    title TEXT,
    reason TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES ingest_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_postings_source_hash ON postings(source, content_hash);
"""


def ensure_ingest_schema(conn):
    """Additive migration: safe on a database that predates ingestion."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(postings)")}
    for column in ("content_hash", "ingested_at"):
        if column not in existing:
            conn.execute(f"ALTER TABLE postings ADD COLUMN {column} TEXT")
    conn.executescript(INGEST_DDL)
    conn.commit()


def backfill_content_hashes(conn):
    """Fingerprint postings loaded before ingestion existed."""
    rows = conn.execute(
        "SELECT posting_id, title, company, description FROM postings WHERE content_hash IS NULL"
    ).fetchall()
    for posting_id, title, company, description in rows:
        h = content_hash({"title": title, "company": company, "description": description})
        conn.execute("UPDATE postings SET content_hash = ? WHERE posting_id = ?", (h, posting_id))
    conn.commit()
    return len(rows)


def remove_existing_duplicates(conn, source="adzuna"):
    """One-off cleanup for postings loaded before de-duplication existed:
    keep the earliest posting of each content hash, delete the reposts.
    Skips any posting that other tables already reference. Returns the
    number removed."""
    dup_groups = conn.execute(
        "SELECT content_hash FROM postings WHERE source = ? AND content_hash IS NOT NULL GROUP BY content_hash HAVING COUNT(*) > 1",
        (source,),
    ).fetchall()
    removed = 0
    for (h,) in dup_groups:
        ids = [r[0] for r in conn.execute(
            "SELECT posting_id FROM postings WHERE source = ? AND content_hash = ? ORDER BY posted_date, posting_id", (source, h))]
        for posting_id in ids[1:]:
            referenced = conn.execute(
                "SELECT (SELECT COUNT(*) FROM extractions WHERE source_type = 'posting' AND source_id = ?) + "
                "(SELECT COUNT(*) FROM posting_cluster_map WHERE posting_id = ?)", (posting_id, posting_id)).fetchone()[0]
            if not referenced:
                conn.execute("DELETE FROM postings WHERE posting_id = ?", (posting_id,))
                removed += 1
    conn.commit()
    return removed


def ingest_postings(conn, raw_jobs, source="adzuna", snapshot_path=None, now=None):
    """Validate, deduplicate and load raw Adzuna results. Returns a stats dict."""
    ensure_ingest_schema(conn)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = conn.execute(
        "INSERT INTO ingest_runs (source, started_at, snapshot_path, fetched) VALUES (?, ?, ?, ?)",
        (source, started, snapshot_path, len(raw_jobs)),
    ).lastrowid

    known_ids = {r[0] for r in conn.execute("SELECT posting_id FROM postings")}
    known_hashes = {r[0] for r in conn.execute("SELECT content_hash FROM postings WHERE source = ? AND content_hash IS NOT NULL", (source,))}
    stats = {"fetched": len(raw_jobs), "rejected": 0, "duplicate_ids": 0, "duplicate_content": 0, "inserted": 0, "warnings": 0}
    reasons = {}
    ingested_at = started

    for raw in raw_jobs:
        posting, reason, warns = validate_posting(normalize_adzuna(raw, source), now=now)
        stats["warnings"] += len(warns)
        if reason:
            stats["rejected"] += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            conn.execute(
                "INSERT INTO rejected_postings (run_id, posting_id, title, reason) VALUES (?, ?, ?, ?)",
                (run_id, posting.get("posting_id") or None, (posting.get("title") or "")[:200], reason),
            )
            continue
        if posting["posting_id"] in known_ids:
            stats["duplicate_ids"] += 1
            continue
        h = content_hash(posting)
        if h in known_hashes:
            stats["duplicate_content"] += 1
            continue
        conn.execute(
            "INSERT INTO postings (posting_id, source, title, company, location, description, salary_min, salary_max, posted_date, content_hash, ingested_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (posting["posting_id"], source, posting["title"], posting["company"], posting["location"], posting["description"],
             posting["salary_min"], posting["salary_max"], posting["posted_date"], h, ingested_at),
        )
        known_ids.add(posting["posting_id"])
        known_hashes.add(h)
        stats["inserted"] += 1

    reject_rate = stats["rejected"] / stats["fetched"] if stats["fetched"] else 0.0
    status = STATUS_DEGRADED if reject_rate > DEGRADED_REJECT_RATE else STATUS_OK
    conn.execute(
        "UPDATE ingest_runs SET finished_at = ?, rejected = ?, duplicate_ids = ?, duplicate_content = ?, inserted = ?, warnings = ?, status = ? WHERE run_id = ?",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), stats["rejected"], stats["duplicate_ids"],
         stats["duplicate_content"], stats["inserted"], stats["warnings"], status, run_id),
    )
    conn.commit()
    return {**stats, "run_id": run_id, "status": status, "reject_rate": reject_rate, "reject_reasons": reasons}


def load_snapshot_file(conn, path, source="adzuna"):
    """Replay a saved raw snapshot (a JSON list of Adzuna results)."""
    with open(path, encoding="utf-8") as f:
        jobs = json.load(f)
    return ingest_postings(conn, jobs, source=source, snapshot_path=str(path))
