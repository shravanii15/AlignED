"""Tests for the Prefect flows in scripts/orchestration/.

The task logic is tested by calling the undecorated functions (`.fn`), which is fast and
needs no Prefect server. Two end-to-end tests run the real flows against a throwaway
database inside Prefect's test harness.
"""

import os
import sqlite3

import pytest
from prefect.testing.utilities import prefect_test_harness

import ingest_adzuna
from orchestration import flows

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(BASE, "data", "raw", "adzuna", "2026-10-07.json")


@pytest.fixture(scope="module", autouse=True)
def prefect_server():
    with prefect_test_harness():
        yield


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.executescript(open(os.path.join(BASE, "database", "schema.sql"), encoding="utf-8").read())
    conn.commit()
    conn.close()
    return path


def _count(path):
    conn = sqlite3.connect(path)
    n = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    conn.close()
    return n


# ---------- retry policy ----------

def test_ingest_raises_fetch_failed_on_fetch_exit_code(monkeypatch):
    monkeypatch.setattr(ingest_adzuna, "main", lambda argv: ingest_adzuna.EXIT_FETCH_FAILED)
    with pytest.raises(flows.FetchFailed):
        flows.ingest_task.fn("x.db")


def test_ingest_raises_quality_error_on_degraded_exit_code(monkeypatch):
    monkeypatch.setattr(ingest_adzuna, "main", lambda argv: ingest_adzuna.EXIT_DEGRADED)
    with pytest.raises(flows.DataQualityDegraded):
        flows.ingest_task.fn("x.db")


class _State:
    def __init__(self, error):
        self._error = error

    def result(self):
        if self._error:
            raise self._error


def test_only_fetch_failures_are_retried():
    assert flows._retry_only_fetch_failures(None, None, _State(flows.FetchFailed("x"))) is True
    assert flows._retry_only_fetch_failures(None, None, _State(flows.DataQualityDegraded("x"))) is False
    assert flows._retry_only_fetch_failures(None, None, _State(None)) is False


def test_ingest_task_is_configured_to_retry():
    assert flows.ingest_task.retries == flows.FETCH_RETRIES >= 2
    assert flows.ingest_task.retry_delay_seconds


# ---------- alerts ----------

def test_failure_hook_posts_to_webhook_when_configured(monkeypatch):
    sent = {}
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.test/hook")
    monkeypatch.setattr(flows.requests, "post", lambda url, json, timeout: sent.update(url=url, body=json))

    class Run:
        name = "brave-otter"

    class St:
        name = "Failed"

    monkeypatch.setattr(flows, "get_run_logger", lambda: type("L", (), {"error": lambda *a: None, "warning": lambda *a: None})())
    flows.notify_failure(None, Run(), St())
    assert sent["url"] == "https://example.test/hook" and "brave-otter" in sent["body"]["text"]


def test_failure_hook_without_webhook_does_not_post(monkeypatch):
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(flows.requests, "post", lambda *a, **k: pytest.fail("should not post"))
    monkeypatch.setattr(flows, "get_run_logger", lambda: type("L", (), {"error": lambda *a: None})())

    class Run:
        name = "x"

    class St:
        name = "Failed"

    flows.notify_failure(None, Run(), St())


# ---------- end to end ----------

def test_daily_flow_loads_snapshot_and_skips_rebuild(db_path, monkeypatch):
    monkeypatch.setattr(flows.integrity_task, "fn", lambda p: 0)  # empty test database has no skills to validate against
    result = flows.daily_flow(db_path=db_path, from_file=SNAPSHOT, rebuild=False)
    assert result["after"] > result["before"] == 0
    assert _count(db_path) == result["after"]


def test_backfill_is_idempotent(db_path, tmp_path, monkeypatch):
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    (snaps / "2026-10-07.json").write_text(open(SNAPSHOT, encoding="utf-8").read(), encoding="utf-8")
    first = flows.backfill_flow(db_path=db_path, snapshot_dir=str(snaps))
    second = flows.backfill_flow(db_path=db_path, snapshot_dir=str(snaps))
    assert second["after"] == first["after"] > 0  # replaying adds nothing


def test_backfill_fails_clearly_without_snapshots(db_path, tmp_path):
    with pytest.raises(FileNotFoundError):
        flows.backfill_flow(db_path=db_path, snapshot_dir=str(tmp_path))
