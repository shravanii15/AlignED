"""Tests for the held-out evaluation tooling (sampling, label import, bootstrap scoring)."""

import json
import os
import sqlite3

import pytest
from openpyxl import Workbook

import build_heldout_set
import evaluate_heldout
import heldout
import import_heldout_labels
from extract_common import load_vocabulary

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG = "This text describes building data pipelines with Python and SQL and teaching statistics to students every week. "


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "h.db")
    c = sqlite3.connect(path)
    c.executescript(open(os.path.join(BASE, "database", "schema.sql"), encoding="utf-8").read())
    c.executemany("INSERT INTO programs VALUES (?, ?, ?, NULL, NULL)", [(1, "U1", "P1"), (2, "U2", "P2")])
    for i in range(20):
        c.execute("INSERT INTO courses (program_id, course_name, description) VALUES (?, ?, ?)", (1 + i % 2, f"C{i}", f"{LONG} variant {i}"))
    c.execute("INSERT INTO role_clusters VALUES (1, 'Role A', 'k', 0.1), (2, 'Role B', 'k', 0.1)")
    for i in range(10):
        c.execute("INSERT INTO postings (posting_id, source, title, company, description) VALUES (?, 'kaggle_sample', 't', 'co', ?)",
                  (f"p{i}", (LONG * 6) + f" posting {i}"))
        c.execute("INSERT INTO posting_cluster_map VALUES (?, ?)", (f"p{i}", 1 + i % 2))
    c.commit()
    c.close()
    return path


# ---------- sampling ----------

def test_sampling_is_deterministic_and_has_requested_mix(db):
    a = heldout.sample_items(db, 8, 4, seed=1, exclude=set())
    b = heldout.sample_items(db, 8, 4, seed=1, exclude=set())
    assert a == b
    assert sum(i["source_type"] == "course" for i in a) == 8 and sum(i["source_type"] == "posting" for i in a) == 4
    assert len({i["id"] for i in a}) == 12


def test_different_seed_gives_different_sample(db):
    assert heldout.sample_items(db, 8, 4, seed=1, exclude=set()) != heldout.sample_items(db, 8, 4, seed=2, exclude=set())


def test_sampling_spreads_across_programs_and_roles(db):
    items = heldout.sample_items(db, 6, 4, seed=3, exclude=set())
    assert {i["context"] for i in items if i["source_type"] == "course"} == {"U1: P1", "U2: P2"}
    assert {i["context"].split(" | ")[0] for i in items if i["source_type"] == "posting"} == {"Role A", "Role B"}


def test_dev_items_are_excluded(db):
    all_items = heldout.sample_items(db, 20, 10, seed=1, exclude=set())
    blocked = {heldout.text_fingerprint(i["text"]) for i in all_items[:10]}
    again = heldout.sample_items(db, 20, 10, seed=1, exclude=blocked)
    assert not {heldout.text_fingerprint(i["text"]) for i in again} & blocked


def test_real_sample_has_no_overlap_with_the_dev_set():
    path = os.path.join(BASE, "data", "heldout", "heldout_items.json")
    if not os.path.exists(path):
        pytest.skip("held-out items not built")
    items = json.load(open(path, encoding="utf-8"))
    assert len(items) >= 50
    assert not {heldout.text_fingerprint(i["text"]) for i in items} & heldout.dev_fingerprints()
    assert all(len(i["text"]) <= heldout.MAX_TEXT_CHARS for i in items)


# ---------- label parsing and import ----------

def test_parse_skill_cell():
    assert heldout.parse_skill_cell("Python; SQL\nGit ;") == ["Python", "SQL", "Git"]
    assert heldout.parse_skill_cell("none") == [] and heldout.parse_skill_cell(None) is None
    assert heldout.parse_skill_cell("  ") == []


def test_build_labels_grounds_names_and_reports_unknowns_and_blanks():
    vocab = load_vocabulary()
    items = [{"id": "X1", "source_type": "course", "title": "t"}, {"id": "X2", "source_type": "course", "title": "t"},
             {"id": "X3", "source_type": "posting", "title": "t"}]
    labeled, blank, unmatched = import_heldout_labels.build_labels(
        items, {"X1": "Python; python; Not A Real Skill 9000", "X2": "NONE", "X3": None}, vocab)
    assert blank == ["X3"] and unmatched == {"X1": ["Not A Real Skill 9000"]}
    x1 = next(i for i in labeled if i["id"] == "X1")
    names = [e.get("title") or e.get("name") for e in x1["essential_technologies"] + x1["essential_skills_or_knowledge"]]
    assert names == ["Python"]  # duplicate collapsed
    assert next(i for i in labeled if i["id"] == "X2")["essential_technologies"] == []


def test_sheet_roundtrip_and_empty_sheet_is_not_a_valid_key(tmp_path):
    items = [{"id": "HC001", "source_type": "course", "context": "c", "title": "t", "text": "x"}]
    path = str(tmp_path / "s.xlsx")
    build_heldout_set.write_sheet(items, load_vocabulary()[:5], path)
    cells = import_heldout_labels.read_cells(path)
    assert cells == {"HC001": None}
    _, blank, _ = import_heldout_labels.build_labels(items, cells, load_vocabulary())
    assert blank == ["HC001"]


def test_sheet_never_overwritten_without_force(tmp_path, monkeypatch):
    monkeypatch.setattr(build_heldout_set, "HELDOUT_DIR", str(tmp_path))
    Workbook().save(str(tmp_path / "labeling_sheet.xlsx"))
    assert build_heldout_set.main([]) == 1


# ---------- scoring ----------

def _sets():
    true = {f"i{k}": {"a", "b", "c"} for k in range(30)}
    good = {k: {"a", "b", "c"} for k in true}
    poor = {k: {"a", "x", "y"} for k in true}
    return true, good, poor


def test_bootstrap_interval_contains_point_estimate_and_is_reproducible():
    true, good, poor = _sets()
    one = evaluate_heldout.bootstrap(true, poor, good, rounds=300, seed=1)
    two = evaluate_heldout.bootstrap(true, poor, good, rounds=300, seed=1)
    assert one == two
    lo, hi = one["difference_ci95"]
    assert lo > 0 and hi <= 1  # a clearly better method has an interval above zero


def test_identical_methods_have_a_zero_width_difference_interval():
    true, good, _ = _sets()
    ci = evaluate_heldout.bootstrap(true, good, good, rounds=200, seed=1)["difference_ci95"]
    assert ci == [0.0, 0.0]


def test_verdict_wording():
    assert "LLM better" in evaluate_heldout.verdict([0.01, 0.2])
    assert "Keyword baseline better" in evaluate_heldout.verdict([-0.2, -0.01])
    assert "No reliable difference" in evaluate_heldout.verdict([-0.05, 0.1])


def test_noisy_small_difference_gets_a_wide_interval_and_a_matching_verdict():
    import random
    rng = random.Random(0)
    true = {f"i{k}": {"a", "b", "c", "d"} for k in range(40)}
    a = {k: {"a", "b"} | ({"x"} if rng.random() < 0.5 else set()) for k in true}
    b = {k: {"a", "b"} | ({"c"} if rng.random() < 0.5 else set()) for k in true}
    ci = evaluate_heldout.bootstrap(true, a, b, rounds=500, seed=2)["difference_ci95"]
    assert ci[0] < ci[1] and ci[1] - ci[0] > 0.02          # a 40-item sample cannot pin the difference down tightly
    expected = "LLM better" if ci[0] > 0 else ("Keyword baseline better" if ci[1] < 0 else "No reliable difference")
    assert expected in evaluate_heldout.verdict(ci)


# ---------- human review gate ----------

def test_review_gate_only_accepts_ok_or_fixed():
    assert import_heldout_labels.unreviewed({"A": "OK", "B": "fixed", "C": None, "D": "looks fine", "E": " Ok "}) == ["C", "D"]


def test_review_column_roundtrip(tmp_path):
    from openpyxl import load_workbook
    path = str(tmp_path / "s.xlsx")
    items = [{"id": "HC001", "source_type": "course", "context": "c", "title": "t", "text": "x"}]
    build_heldout_set.write_sheet(items, load_vocabulary()[:3], path)
    wb = load_workbook(path)
    wb["Label"].cell(row=2, column=7, value="OK")
    wb.save(path)
    assert import_heldout_labels.read_reviews(path) == {"HC001": "OK"}
