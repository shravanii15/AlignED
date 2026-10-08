"""Tests for the weekly market-pulse refresh (scripts/market_pulse.py).

They matter because this feature must never change the published statistics and must compare
like with like (Adzuna descriptions are truncated; the historical sample is full text)."""

import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone

import pytest

import market_pulse
from orchestration import flows

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_DB = os.path.join(BASE, "database", "aligned.db")
NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _job(i, text):
    return {"id": str(i), "title": f"Data Scientist {i}", "description": text + f" Unique posting number {i}. " * 5,
            "created": "2026-10-07T01:00:00Z", "company": {"display_name": f"Co {i}"}, "location": {"display_name": "NY"}}


@pytest.fixture
def snapshots(tmp_path):
    d = tmp_path / "snaps"
    d.mkdir()
    jobs = [_job(i, "We use Python and SQL every day." if i % 2 == 0 else "We use Excel and reporting tools.") for i in range(150)]
    (d / "2026-10-07.json").write_text(json.dumps(jobs), encoding="utf-8")
    (d / "2026-10-08.json").write_text(json.dumps(jobs[:50] + [_job(1000 + i, "Python and Tableau dashboards.") for i in range(20)]), encoding="utf-8")
    return str(d)


def test_postings_are_deduplicated_across_snapshots(snapshots):
    postings, names = market_pulse.load_recent_postings(snapshots, now=NOW)
    assert names == ["2026-10-07.json", "2026-10-08.json"]
    assert len(postings) == 170  # 150 + 20 new; the 50 repeats are not double counted


def test_too_few_postings_publishes_nothing(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "x.json").write_text(json.dumps([_job(1, "Python")]), encoding="utf-8")
    assert market_pulse.compute_market_pulse(REAL_DB, str(d), now=NOW) is None


def test_pulse_structure_and_values(snapshots):
    pulse = market_pulse.compute_market_pulse(REAL_DB, snapshots, now=NOW)
    assert pulse["recent_postings"] == 170
    assert pulse["refreshed_at"].startswith("2026-10-08")
    assert pulse["posted_to"] == "2026-10-07"
    assert pulse["historical_postings"] == 1660
    assert pulse["text_window_chars"] == 500
    python = next(r for r in pulse["skills"] if r["skill"] == "Python")
    assert python["recent_count"] == 75 + 20  # even ids 0..148 = 75, plus 20 Tableau postings mentioning Python
    assert 0 <= python["q_value"] <= 1 and python["q_value"] >= python["p_value"]
    assert all(r["recent_count"] >= market_pulse.MIN_RECENT_MENTIONS for r in pulse["skills"])


def test_ambiguous_generic_terms_are_excluded(snapshots):
    names = {r["skill"].lower() for r in market_pulse.compute_market_pulse(REAL_DB, snapshots, now=NOW)["skills"]}
    assert not names & market_pulse.AMBIGUOUS_GENERIC_TERMS


def test_historical_side_is_measured_on_the_same_text_window(tmp_path):
    """A skill mentioned only after character 500 must not count for the historical sample."""
    db = str(tmp_path / "t.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE postings (posting_id TEXT, source TEXT, title TEXT, description TEXT)")
    conn.execute("INSERT INTO postings VALUES ('a', 'kaggle_sample', 'T', ?)", ("x " * 400 + "Python",))
    conn.execute("INSERT INTO postings VALUES ('b', 'kaggle_sample', 'T', 'Python early')")
    vocab = market_pulse.load_vocabulary()
    lookup = {}
    for e in vocab:
        lookup.setdefault(market_pulse.normalize_term(e["term"]), e)
    pattern = market_pulse.build_combined_pattern([e["term"] for e in lookup.values()])
    total, counts = market_pulse.historical_baseline(conn, lookup, pattern)
    assert total == 2 and counts["python"] == 1


def test_running_the_refresh_does_not_modify_the_database(snapshots, tmp_path):
    db_copy = str(tmp_path / "copy.db")
    shutil.copyfile(REAL_DB, db_copy)
    before = open(db_copy, "rb").read()
    market_pulse.compute_market_pulse(db_copy, snapshots, now=NOW)
    assert open(db_copy, "rb").read() == before


def test_write_is_atomic_and_valid_json(snapshots, tmp_path):
    pulse = market_pulse.compute_market_pulse(REAL_DB, snapshots, now=NOW)
    out = str(tmp_path / "out" / "latest.json")
    market_pulse.write_market_pulse(pulse, out)
    assert json.load(open(out, encoding="utf-8"))["recent_postings"] == 170
    assert not os.path.exists(out + ".tmp")


def test_cli_returns_1_and_keeps_previous_file_when_data_is_thin(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    out = tmp_path / "latest.json"
    out.write_text('{"keep": true}', encoding="utf-8")
    assert market_pulse.main(["--db", REAL_DB, "--snapshots", str(d), "--out", str(out)]) == 1
    assert json.loads(out.read_text()) == {"keep": True}


def test_committed_pulse_file_is_loadable_by_the_dashboard():
    import sys
    sys.path.insert(0, os.path.join(BASE, "dashboard", "services"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("pulse_loader", os.path.join(BASE, "dashboard", "services", "market_pulse.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pulse = mod.load_market_pulse()
    assert pulse and pulse["recent_postings"] >= market_pulse.MIN_POSTINGS_TO_PUBLISH
    assert len(mod.refreshed_date(pulse)) == 10
    assert mod.load_market_pulse("/nonexistent/file.json") is None


def test_flow_task_writes_file(snapshots, tmp_path):
    out = str(tmp_path / "latest.json")
    pulse = flows.market_pulse_task.fn(REAL_DB, snapshots, out)
    assert os.path.exists(out) and pulse["recent_postings"] == 170
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError):
        flows.market_pulse_task.fn(REAL_DB, str(empty), out)
