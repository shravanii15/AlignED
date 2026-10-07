"""Static checks on the dbt project and a test of its export step (dbt itself runs in its own CI job)."""

import csv
import os
import re
import sqlite3
import sys

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "dbt"))
import export_sources  # noqa: E402


def _read(*parts):
    return open(os.path.join(BASE, *parts), encoding="utf-8").read()


def test_every_dbt_source_has_an_export():
    sources = yaml.safe_load(_read("dbt", "models", "staging", "sources.yml"))["sources"][0]["tables"]
    assert {t["name"] for t in sources} == set(export_sources.TABLES)


def test_every_model_is_documented_with_tests():
    declared = set()
    for folder in ("staging", "marts"):
        declared |= {m["name"] for m in yaml.safe_load(_read("dbt", "models", folder, "schema.yml"))["models"]}
        for f in os.listdir(os.path.join(BASE, "dbt", "models", folder)):
            if f.endswith(".sql"):
                assert f[:-4] in declared, f"{f} has no entry in schema.yml"


def test_dbt_project_has_data_tests_of_its_own():
    singular = [f for f in os.listdir(os.path.join(BASE, "dbt", "tests")) if f.endswith(".sql")]
    assert len(singular) >= 4


def test_ci_runs_dbt_build():
    workflow = _read(".github", "workflows", "run_tests.yml")
    assert "dbt build --project-dir dbt --profiles-dir dbt" in workflow and "requirements-dbt.txt" in workflow


def test_dbt_outputs_are_not_committed():
    ignore = _read(".gitignore")
    assert all(p in ignore for p in ("dbt/target/", "dbt/data/", "dbt/logs/"))


def test_profile_holds_no_secrets():
    profile = _read("dbt", "profiles.yml")
    assert not re.search(r"(password|token|secret|key)\s*:", profile, flags=re.I)


def test_export_writes_every_table_with_headers_and_blank_nulls(tmp_path):
    db = str(tmp_path / "t.db")
    conn = sqlite3.connect(db)
    conn.executescript(_read("database", "schema.sql"))
    conn.execute("INSERT INTO programs VALUES (1, 'U', 'P', NULL, NULL)")
    conn.commit()
    conn.close()
    counts = export_sources.export(db, str(tmp_path / "out"))
    assert set(counts) == set(export_sources.TABLES) and counts["programs"] == 1
    rows = list(csv.reader(open(tmp_path / "out" / "programs.csv", encoding="utf-8")))
    assert rows[0] == ["program_id", "university", "program_name", "tier"] and rows[1] == ["1", "U", "P", ""]
