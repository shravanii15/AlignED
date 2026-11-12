"""Tests added after an external code audit: each one pins a specific fix or a verified claim."""

import json
import os
import sqlite3

import pytest

import heldout
import rebuild_all
import verify_claims
from api.security import RateLimiter, key_id

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- the key identifier written to logs must not contain any of the secret ---

def test_key_id_does_not_leak_secret_characters():
    secret = "sk_live_abcdefghijklmnop"
    ident = key_id(secret)
    assert ident.startswith("key-") and len(ident) == 12
    assert secret[:4] not in ident and secret[4:8] not in ident


def test_key_id_is_stable_and_distinguishes_keys():
    assert key_id("aaaa1111") == key_id("aaaa1111")
    assert key_id("aaaa1111") != key_id("aaaa1112")


def test_rate_limiter_state_is_bounded_by_the_keys_it_is_asked_about():
    limiter = RateLimiter(limit=2)
    for _ in range(10):
        limiter.check("only-key")
    assert len(limiter._hits) == 1


# --- held-out set: no leakage from the development set, checked beyond the 200-character fingerprint ---

def test_shingle_overlap_catches_a_near_duplicate_with_a_different_opening():
    body = "build scalable data pipelines using python sql airflow and docker for analytics teams across the company " * 3
    assert heldout.shingle_overlap("Senior role. " + body, "Different intro here. " + body) > 0.8
    assert heldout.text_fingerprint("Senior role. " + body) != heldout.text_fingerprint("Different intro here. " + body)


def test_unrelated_texts_do_not_overlap():
    assert heldout.shingle_overlap("python statistics regression modelling course", "kubernetes docker deployment pipelines") == 0


def test_committed_held_out_items_have_no_overlap_with_the_development_set():
    with open(os.path.join(BASE, "data", "heldout", "heldout_items.json"), encoding="utf-8") as f:
        items = json.load(f)
    assert heldout.dev_overlaps(items, threshold=0.3) == []


# --- the full rebuild must not touch the live database unless everything succeeds ---

def _make_db(path, value):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE marker (v TEXT)")
    conn.execute("INSERT INTO marker VALUES (?)", (value,))
    conn.commit()
    conn.close()


def _value(path):
    conn = sqlite3.connect(path)
    v = conn.execute("SELECT v FROM marker").fetchone()[0]
    conn.close()
    return v


def test_full_rebuild_leaves_live_database_untouched_when_a_stage_fails(tmp_path, monkeypatch):
    live = str(tmp_path / "live.db")
    _make_db(live, "old")
    bad = tmp_path / "bad_stage.py"
    bad.write_text("import os, sqlite3\nc = sqlite3.connect(os.environ['ALIGNED_DB_PATH'])\n"
                   "c.execute('CREATE TABLE marker (v TEXT)'); c.execute(\"INSERT INTO marker VALUES ('half-built')\"); c.commit()\n"
                   "raise SystemExit(1)\n")
    monkeypatch.setattr(rebuild_all, "SCRIPTS_DIR", str(tmp_path))
    import subprocess
    with pytest.raises(subprocess.CalledProcessError):
        rebuild_all.rebuild_full(db_path=live, stages=[("bad", "bad_stage.py", [])])
    assert _value(live) == "old"


def test_full_rebuild_keeps_live_database_when_validation_fails(tmp_path, monkeypatch):
    live = str(tmp_path / "live.db")
    _make_db(live, "old")
    stage = tmp_path / "ok_stage.py"
    stage.write_text("import os, sqlite3\nc = sqlite3.connect(os.environ['ALIGNED_DB_PATH'])\n"
                     "c.execute('CREATE TABLE marker (v TEXT)'); c.execute(\"INSERT INTO marker VALUES ('new')\"); c.commit()\n")
    monkeypatch.setattr(rebuild_all, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(rebuild_all, "validate_database", lambda conn: ["broken invariant"])
    assert rebuild_all.rebuild_full(db_path=live, stages=[("ok", "ok_stage.py", [])]) == ["broken invariant"]
    assert _value(live) == "old"


def test_full_rebuild_replaces_live_database_after_success(tmp_path, monkeypatch):
    live = str(tmp_path / "live.db")
    _make_db(live, "old")
    good = tmp_path / "good_stage.py"
    good.write_text("import os, sqlite3\nc = sqlite3.connect(os.environ['ALIGNED_DB_PATH'])\n"
                    "c.execute('CREATE TABLE marker (v TEXT)'); c.execute(\"INSERT INTO marker VALUES ('new')\"); c.commit()\n")
    monkeypatch.setattr(rebuild_all, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(rebuild_all, "validate_database", lambda conn: [])  # the toy database has no real schema
    assert rebuild_all.rebuild_full(db_path=live, stages=[("good", "good_stage.py", [])]) == []
    assert _value(live) == "new"


# --- every number quoted in the docs regenerates from stored artifacts ---

def test_every_quoted_headline_number_matches_the_stored_artifacts():
    mismatches = [(c, q, v) for c, q, v, _ in verify_claims.collect() if q != v]
    assert mismatches == []
