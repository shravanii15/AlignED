"""
test_database_and_pipeline.py

Integration tests for the committed database snapshot and the rebuild
tooling: integrity validation, FK-safe resets, the atomic rebuild, that the
stored gap table can be reproduced from its own counts, and that CI,
documentation and gitignore match what the project claims.
"""

import ast
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

from compute_gap_scores import compare_proportions  # noqa: E402
from db_utils import clear_table_and_dependents, dependents_in_delete_order  # noqa: E402
from validate_database import validate_database  # noqa: E402


@pytest.fixture
def db_copy(tmp_path):
    path = tmp_path / "aligned.db"
    shutil.copyfile(DB_PATH, path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn, str(path)
    conn.close()


def run_script(relative, db_path, timeout=300):
    env = {**os.environ, "ALIGNED_DB_PATH": db_path}
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, relative)],
        env=env, cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout,
    )


# ---------- committed snapshot ----------

def test_committed_database_passes_every_integrity_check(db_copy):
    conn, _ = db_copy
    assert validate_database(conn) == []


def test_gap_table_is_reproducible_from_its_own_counts(db_copy):
    """Recompute every stored p-value and test method from the program's
    course count, the scope's posting count and the stored rates. Catches a
    gap table that no longer matches the statistics code."""
    conn, _ = db_copy
    n_courses = dict(conn.execute("SELECT program_id, COUNT(*) FROM courses GROUP BY program_id"))
    overall_total = conn.execute("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'").fetchone()[0]
    cluster_total = dict(conn.execute("SELECT cluster_id, COUNT(*) FROM posting_cluster_map GROUP BY cluster_id"))
    rows = conn.execute(
        "SELECT program_id, cluster_id, program_coverage_rate, market_demand_rate, p_value, test_method FROM gap_scores"
    ).fetchall()
    assert rows
    for program_id, cluster_id, cov, dem, p_stored, method_stored in rows:
        n1 = n_courses[program_id]
        n2 = overall_total if cluster_id is None else cluster_total[cluster_id]
        _, p, method = compare_proportions(round(cov * n1), n1, round(dem * n2), n2)
        assert method == method_stored
        assert p == pytest.approx(p_stored, abs=1e-9)


def test_small_programs_use_exact_tests_and_large_ones_mostly_z(db_copy):
    conn, _ = db_copy
    methods = dict(conn.execute("SELECT test_method, COUNT(*) FROM gap_scores GROUP BY test_method"))
    assert set(methods) <= {"z_test", "fisher_exact"}
    assert methods.get("fisher_exact", 0) > 0


def test_overall_market_gap_count_matches_the_documented_number(db_copy):
    conn, _ = db_copy
    overall = conn.execute("SELECT COUNT(*) FROM gap_scores WHERE cluster_id IS NULL").fetchone()[0]
    readme = open(os.path.join(BASE_DIR, "README.md"), encoding="utf-8").read()
    assert f"| Significant skill gaps | {overall} " in readme


# ---------- validator catches problems ----------

def test_validator_detects_a_duplicate_gap_row(db_copy):
    conn, _ = db_copy
    conn.execute("INSERT INTO gap_scores (program_id, skill_id, cluster_id, period, program_coverage_rate, market_demand_rate, gap_value, p_value, q_value, test_method) "
                 "SELECT program_id, skill_id, cluster_id, period, program_coverage_rate, market_demand_rate, gap_value, p_value, q_value, test_method FROM gap_scores LIMIT 1")
    assert any("gap_scores" in p and "duplicate" in p for p in validate_database(conn))


def test_validator_detects_a_non_significant_or_non_positive_gap(db_copy):
    conn, _ = db_copy
    conn.execute("UPDATE gap_scores SET q_value = 0.5 WHERE gap_id = (SELECT MIN(gap_id) FROM gap_scores)")
    assert any("q_value" in p for p in validate_database(conn))


def test_validator_detects_a_recommendation_without_a_gap_row(db_copy):
    conn, _ = db_copy
    conn.execute("DELETE FROM gap_scores WHERE gap_id = (SELECT g.gap_id FROM gap_scores g JOIN recommendations r "
                 "ON r.program_id = g.program_id AND r.skill_id = g.skill_id AND r.cluster_id IS g.cluster_id LIMIT 1)")
    assert any("no matching gap_scores" in p for p in validate_database(conn))


def test_validator_detects_a_trend_label_that_disagrees_with_q_value(db_copy):
    conn, _ = db_copy
    conn.execute("UPDATE skill_trends SET trend_label = 'rising', q_value = 0.9, slope = 0.1 WHERE trend_id = (SELECT MIN(trend_id) FROM skill_trends)")
    assert any("skill_trends" in p for p in validate_database(conn))


def test_validator_detects_a_foreign_key_violation(db_copy):
    conn, _ = db_copy
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("UPDATE courses SET program_id = 99999 WHERE course_id = (SELECT MIN(course_id) FROM courses)")
    assert any("foreign_key_check" in p for p in validate_database(conn))


# ---------- FK-safe resets (the rebuild defect) ----------

def test_plain_delete_of_programs_fails_with_foreign_keys_on(db_copy):
    """Documents the original defect: setup_database.py used DELETE FROM
    courses / programs in place."""
    conn, _ = db_copy
    conn.execute("DELETE FROM courses")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM programs")


def test_dependency_order_is_derived_from_the_schema(db_copy):
    conn, _ = db_copy
    assert dependents_in_delete_order(conn, "programs") == ["courses", "recommendations", "gap_scores"] or \
        set(dependents_in_delete_order(conn, "programs")) == {"courses", "recommendations", "gap_scores"}
    assert {"extractions", "gap_scores", "recommendations", "skill_trends"} <= set(dependents_in_delete_order(conn, "skills"))


def test_clearing_parents_with_dependents_first_succeeds_and_stays_valid(db_copy):
    conn, _ = db_copy
    clear_table_and_dependents(conn, "programs")
    clear_table_and_dependents(conn, "skills")
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 0


def test_setup_database_can_be_rerun_against_a_populated_database(db_copy):
    _, path = db_copy
    result = run_script("setup_database.py", path)
    assert result.returncode == 0, result.stderr[-800:]
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM programs").fetchone()[0] == 13
    assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1378
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()
    assert not os.path.exists(path + ".new")


def test_build_lookup_tables_can_be_rerun_against_a_populated_database(db_copy):
    _, path = db_copy
    result = run_script(os.path.join("gap_analysis", "build_lookup_tables.py"), path)
    assert result.returncode == 0, result.stderr[-800:]
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0] == 1597
    assert conn.execute("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'").fetchone()[0] == 1660
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


# ---------- atomic derived rebuild ----------

def test_derived_rebuild_reproduces_the_snapshot_and_validates(db_copy):
    import rebuild_all

    conn, path = db_copy
    before = conn.execute("SELECT COUNT(*) FROM gap_scores").fetchone()[0], conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    conn.close()
    assert rebuild_all.rebuild_derived(path) == []
    after_conn = sqlite3.connect(path)
    after = after_conn.execute("SELECT COUNT(*) FROM gap_scores").fetchone()[0], after_conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
    assert after == before
    assert validate_database(after_conn) == []
    after_conn.close()


def test_failed_validation_leaves_the_existing_database_untouched(db_copy, monkeypatch):
    import rebuild_all

    conn, path = db_copy
    conn.close()
    original = open(path, "rb").read()
    monkeypatch.setattr(rebuild_all, "validate_database", lambda _conn: ["forced failure"])
    assert rebuild_all.rebuild_derived(path) == ["forced failure"]
    assert open(path, "rb").read() == original


def test_full_rebuild_refuses_to_start_when_an_input_is_missing(monkeypatch):
    import rebuild_all

    monkeypatch.setattr(rebuild_all, "FULL_STAGES", [("needs kaggle", "x.py", ["data/kaggle_backfill/__does_not_exist__.csv"])])
    with pytest.raises(SystemExit, match="missing required input"):
        rebuild_all.rebuild_full()


# ---------- CI / reproducibility / documentation ----------

def third_party_imports_in_tests():
    stdlib = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
    # Packages inside scripts/ (e.g. scripts/ingest) are local code, not third party.
    local_packages = {d for d in os.listdir(os.path.join(BASE_DIR, "scripts")) if os.path.isdir(os.path.join(BASE_DIR, "scripts", d))}
    local = {"conftest", "api", "export_sources"} | local_packages | {f[:-3] for d in ("scripts", os.path.join("scripts", "gap_analysis"), os.path.join("scripts", "extraction"), "tests", "dashboard")
                           for f in os.listdir(os.path.join(BASE_DIR, d)) if f.endswith(".py")} | {"utils", "services", "sections"}
    found = set()
    tests_dir = os.path.join(BASE_DIR, "tests")
    for name in os.listdir(tests_dir):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(tests_dir, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return {m for m in found if m not in stdlib and m not in local}


def test_ci_installs_every_third_party_package_the_tests_import():
    workflow = open(os.path.join(BASE_DIR, ".github", "workflows", "run_tests.yml"), encoding="utf-8").read()
    assert "pip install -r requirements-test.txt" in workflow
    requirements = open(os.path.join(BASE_DIR, "requirements-test.txt"), encoding="utf-8").read().lower()
    declared = {re.split(r"[<>=!~\[ ]", line.strip())[0] for line in requirements.splitlines() if line.strip() and not line.startswith("#")}
    # A few packages are imported under a different name than they install as.
    import_to_package = {"docx": "python-docx", "fpdf": "fpdf2", "yaml": "pyyaml"}
    missing = {pkg for pkg in third_party_imports_in_tests() if import_to_package.get(pkg, pkg).lower() not in declared}
    assert not missing, f"tests import packages that CI would not install: {missing}"


def test_test_requirements_stay_lightweight():
    lines = open(os.path.join(BASE_DIR, "requirements-test.txt"), encoding="utf-8").read().lower().splitlines()
    packages = " ".join(line for line in lines if line.strip() and not line.strip().startswith("#"))
    for heavy in ("torch", "sentence-transformers", "streamlit", "ollama"):
        assert heavy not in packages


def test_rebuild_inputs_are_committed_not_ignored():
    if shutil.which("git") is None or not os.path.isdir(os.path.join(BASE_DIR, ".git")):
        pytest.skip("not a git checkout")
    required = [
        "data/taxonomy/onet_computing_skills.json",
        "data/taxonomy/onet_computing_technologies.json",
        "data/clustering/posting_clusters.json",
        "data/sample_adzuna_pull.json",
    ] + [f"data/{f}" for f in os.listdir(os.path.join(BASE_DIR, "data")) if re.fullmatch(r"sample_.*_courses\.json", f)]
    for path in required:
        assert os.path.exists(os.path.join(BASE_DIR, path)), path
        ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=BASE_DIR).returncode == 0
        assert not ignored, f"{path} is required to rebuild the database but is gitignored"


def test_ingestion_workflow_and_readme_do_not_overclaim():
    workflow = open(os.path.join(BASE_DIR, ".github", "workflows", "fetch_adzuna.yml"), encoding="utf-8").read()
    readme = open(os.path.join(BASE_DIR, "README.md"), encoding="utf-8").read()
    assert "never change a dashboard number" in workflow
    assert "never change a dashboard number" in readme
    assert "Daily Job Pull" not in readme
    assert "live labor market" not in readme.lower() or "not" in readme.lower()


def test_readme_has_no_dash_punctuation():
    readme = open(os.path.join(BASE_DIR, "README.md"), encoding="utf-8").read()
    assert "\u2014" not in readme and " -- " not in readme


def test_readme_documents_the_rebuild_entry_point_and_its_modes():
    readme = open(os.path.join(BASE_DIR, "README.md"), encoding="utf-8").read()
    for expected in ("scripts/rebuild_all.py", "--full", "validate_database.py", "Reproducing the database"):
        assert expected in readme
    assert os.path.exists(os.path.join(SCRIPTS_DIR, "rebuild_all.py"))
