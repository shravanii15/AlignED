"""Tests for the postings ingestion pipeline (scripts/ingest/)."""

import os
import sqlite3
from datetime import datetime, timezone

import pytest
import requests

from ingest import adzuna_client
from ingest.loader import (
    ensure_ingest_schema, ingest_postings, load_snapshot_file, remove_existing_duplicates, backfill_content_hashes,
)
from ingest.quality import (
    MIN_DESCRIPTION_CHARS, content_hash, normalize_adzuna, validate_posting,
)

NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
LONG = "We are hiring a data engineer to build pipelines in Python and SQL, deploy with Docker on AWS and use Git daily. " * 2


def raw(job_id="1", title="Data Engineer", company="Acme", description=LONG, created="2026-10-06T10:00:00Z", **extra):
    job = {"id": job_id, "title": title, "company": {"display_name": company}, "location": {"display_name": "Boston"},
           "description": description, "created": created, "salary_min": 90000, "salary_max": 120000}
    job.update(extra)
    return job


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    schema = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "schema.sql")
    c.executescript(open(schema, encoding="utf-8").read())
    return c


# ---------- validation rules ----------

def test_valid_posting_passes_and_is_normalised():
    p, reason, warns = validate_posting(normalize_adzuna(raw(title="  Data   Engineer ")), now=NOW)
    assert reason is None and warns == [] and p["title"] == "Data Engineer" and p["company"] == "Acme"


@pytest.mark.parametrize("job, expected", [
    (raw(job_id=""), "missing_id"),
    (raw(title="  "), "missing_title"),
    (raw(description="too short"), "description_too_short"),
    (raw(created="not a date"), "unreadable_or_future_date"),
    (raw(created="2027-01-01T00:00:00Z"), "unreadable_or_future_date"),
    (raw(created=None), "unreadable_or_future_date"),
])
def test_rejection_reasons(job, expected):
    _, reason, _ = validate_posting(normalize_adzuna(job), now=NOW)
    assert reason == expected


def test_impossible_salary_is_blanked_not_rejected():
    p, reason, warns = validate_posting(normalize_adzuna(raw(salary_min=200000, salary_max=100000)), now=NOW)
    assert reason is None and warns == ["salary_blanked"] and p["salary_min"] is None and p["salary_max"] is None


def test_description_length_boundary():
    ok = normalize_adzuna(raw(description="x" * MIN_DESCRIPTION_CHARS))
    short = normalize_adzuna(raw(description="x" * (MIN_DESCRIPTION_CHARS - 1)))
    assert validate_posting(ok, now=NOW)[1] is None
    assert validate_posting(short, now=NOW)[1] == "description_too_short"


def test_content_hash_ignores_id_case_and_whitespace_but_not_content():
    a = normalize_adzuna(raw(job_id="1"))
    b = normalize_adzuna(raw(job_id="2", title="DATA  engineer", description=LONG.upper()))
    c = normalize_adzuna(raw(job_id="3", title="Data Analyst"))
    assert content_hash(a) == content_hash(b)
    assert content_hash(a) != content_hash(c)


# ---------- loading ----------

def test_ingest_inserts_and_records_the_run(conn):
    stats = ingest_postings(conn, [raw("1"), raw("2", title="Data Analyst")], now=NOW)
    assert stats["inserted"] == 2 and stats["status"] == "ok"
    row = conn.execute("SELECT fetched, inserted, status, finished_at FROM ingest_runs").fetchone()
    assert row[0] == 2 and row[1] == 2 and row[2] == "ok" and row[3] is not None
    assert conn.execute("SELECT COUNT(*) FROM postings WHERE content_hash IS NOT NULL AND ingested_at IS NOT NULL").fetchone()[0] == 2


def test_ingest_is_idempotent(conn):
    batch = [raw("1"), raw("2", title="Data Analyst")]
    ingest_postings(conn, batch, now=NOW)
    again = ingest_postings(conn, batch, now=NOW)
    assert again["inserted"] == 0 and again["duplicate_ids"] == 2
    assert conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 2


def test_repost_under_new_id_is_skipped_as_duplicate_content(conn):
    stats = ingest_postings(conn, [raw("1"), raw("2")], now=NOW)  # same text, different id
    assert stats["inserted"] == 1 and stats["duplicate_content"] == 1


def test_rejections_are_stored_with_reasons(conn):
    stats = ingest_postings(conn, [raw("1"), raw("2", description="short")], now=NOW)
    assert stats["rejected"] == 1
    assert conn.execute("SELECT reason, posting_id FROM rejected_postings").fetchone() == ("description_too_short", "2")


def test_run_counts_always_add_up(conn):
    batch = [raw("1"), raw("1"), raw("2"), raw("3", description="short"), raw("4", title="Other role")]
    s = ingest_postings(conn, batch, now=NOW)
    assert s["fetched"] == s["rejected"] + s["duplicate_ids"] + s["duplicate_content"] + s["inserted"]


def test_high_reject_rate_marks_run_degraded(conn):
    batch = [raw("1")] + [raw(str(i), description="short") for i in range(2, 6)]
    s = ingest_postings(conn, batch, now=NOW)
    assert s["status"] == "degraded" and s["reject_rate"] == 0.8


def test_empty_fetch_is_not_degraded(conn):
    assert ingest_postings(conn, [], now=NOW)["status"] == "ok"


def test_migration_adds_columns_to_an_old_database():
    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE postings (posting_id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT, company TEXT, location TEXT, description TEXT, salary_min REAL, salary_max REAL, posted_date TEXT)")
    old.execute("INSERT INTO postings VALUES ('a', 'adzuna', 'T', 'C', 'L', 'desc', NULL, NULL, NULL)")
    ensure_ingest_schema(old)
    assert backfill_content_hashes(old) == 1
    ensure_ingest_schema(old)  # safe to run twice
    assert old.execute("SELECT content_hash FROM postings").fetchone()[0]


def test_remove_existing_duplicates_keeps_the_earliest(conn):
    for pid, date in (("a", "2026-01-02"), ("b", "2026-01-01"), ("c", "2026-01-03")):
        conn.execute("INSERT INTO postings (posting_id, source, title, company, description, posted_date, content_hash) VALUES (?, 'adzuna', 'T', 'C', 'd', ?, 'same')", (pid, date))
    assert remove_existing_duplicates(conn) == 2
    assert [r[0] for r in conn.execute("SELECT posting_id FROM postings")] == ["b"]


def test_snapshot_replay_matches_a_live_load(conn, tmp_path):
    import json
    path = tmp_path / "snap.json"
    path.write_text(json.dumps([raw("1"), raw("2", title="Data Analyst")]))
    first = load_snapshot_file(conn, str(path))
    second = load_snapshot_file(conn, str(path))
    assert first["inserted"] == 2 and second["inserted"] == 0


# ---------- API client retry logic (no network, no real sleeping) ----------

class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_client_retries_transient_failures_then_succeeds():
    session = FakeSession([requests.Timeout(), FakeResponse(503), FakeResponse(200, {"results": [raw("1")]})])
    sleeps = []
    jobs = adzuna_client.fetch_jobs("id", "key", queries=["q"], session=session, sleep=sleeps.append)
    assert len(jobs) == 1 and session.calls == 3
    assert sleeps[:2] == [1.0, 2.0]  # exponential backoff


def test_client_gives_up_with_a_clear_error():
    session = FakeSession([FakeResponse(503)] * adzuna_client.MAX_ATTEMPTS)
    with pytest.raises(adzuna_client.FetchError):
        adzuna_client.fetch_jobs("id", "key", queries=["q"], session=session, sleep=lambda s: None)
    assert session.calls == adzuna_client.MAX_ATTEMPTS


def test_client_does_not_retry_auth_errors():
    session = FakeSession([FakeResponse(401)])
    with pytest.raises(adzuna_client.FetchError):
        adzuna_client.fetch_jobs("id", "key", queries=["q"], session=session, sleep=lambda s: None)
    assert session.calls == 1


def test_client_dedupes_across_queries_and_pages():
    page = {"results": [raw("1"), raw("2")]}
    session = FakeSession([FakeResponse(200, page), FakeResponse(200, page)])
    jobs = adzuna_client.fetch_jobs("id", "key", queries=["a", "b"], session=session, sleep=lambda s: None)
    assert [j["id"] for j in jobs] == ["1", "2"]


# ---------- command line entry point ----------

def _db_copy(tmp_path):
    import shutil
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = tmp_path / "copy.db"
    shutil.copy(os.path.join(base, "database", "aligned.db"), target)
    return str(target)


def test_cli_replays_a_snapshot_and_exits_ok(tmp_path, capsys):
    import json
    import ingest_adzuna
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([raw("zz1", title="Unique Role One"), raw("zz2", title="Unique Role Two")]))
    db = _db_copy(tmp_path)
    assert ingest_adzuna.main(["--db", db, "--from-file", str(snap)]) == ingest_adzuna.EXIT_OK
    assert "inserted           2" in capsys.readouterr().out


def test_cli_exits_3_when_quality_is_degraded(tmp_path):
    import json
    import ingest_adzuna
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([raw(str(i), description="short") for i in range(5)]))
    assert ingest_adzuna.main(["--db", _db_copy(tmp_path), "--from-file", str(snap)]) == ingest_adzuna.EXIT_DEGRADED


def test_cli_exits_2_without_credentials(tmp_path, monkeypatch):
    import ingest_adzuna
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    assert ingest_adzuna.main(["--db", _db_copy(tmp_path)]) == ingest_adzuna.EXIT_FETCH_FAILED


def test_loading_postings_never_changes_the_published_statistics(tmp_path):
    """Adzuna postings must not leak into the dashboard numbers, which are
    computed from the kaggle_sample postings only."""
    import json
    import ingest_adzuna
    db = _db_copy(tmp_path)
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'").fetchone()[0]
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([raw("zz9", title="Another Unique Role")]))
    ingest_adzuna.main(["--db", db, "--from-file", str(snap)])
    after = sqlite3.connect(db).execute("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'").fetchone()[0]
    assert before == after == 1660
