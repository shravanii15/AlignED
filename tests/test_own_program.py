"""Tests for the Analyze Your Program service (CSV/paste parsing and the gap analysis)."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from services import own_program as op  # noqa: E402


def test_pasted_blocks_split_on_blank_lines():
    assert op.parse_pasted("Course A. Python.\n\nCourse B. SQL.") == ["Course A. Python.", "Course B. SQL."]


def test_single_block_splits_on_lines():
    assert op.parse_pasted("Course A. Python.\nCourse B. SQL.") == ["Course A. Python.", "Course B. SQL."]


def test_empty_input_gives_a_friendly_error():
    with pytest.raises(op.CourseInputError):
        op.parse_pasted("   ")


def test_csv_uses_the_description_column_and_title():
    data = b"course_name,description,credits\nStats,Probability and regression,3\nDB,SQL and indexing,3\n"
    assert op.parse_csv(data) == ["Stats. Probability and regression", "DB. SQL and indexing"]


def test_csv_without_known_columns_uses_the_longest_text_column():
    data = b"code,blurb\nA1,Short\nA2,A much longer description of the course content here\n"
    assert op.parse_csv(data)[1].startswith("A much longer")


def test_oversize_and_too_many_courses_are_rejected():
    with pytest.raises(op.CourseInputError):
        op.parse_csv(b"x" * (op.MAX_FILE_BYTES + 1))
    with pytest.raises(op.CourseInputError):
        op.parse_pasted("\n".join(f"Course {i}" for i in range(op.MAX_COURSES + 1)))


def test_non_utf8_csv_is_rejected_politely():
    with pytest.raises(op.CourseInputError):
        op.parse_csv(b"description\n\xff\xfe\xfa\n")


def test_analysis_finds_a_gap_for_a_skill_the_courses_never_mention():
    tracked = pd.DataFrame({"skill_id": [1, 2], "canonical_name": ["Python", "Statistics tool"]})
    courses = ["Intro to philosophy and ethics."] * 40
    rows = op.analyze(courses, tracked, {1: 700, 2: 5}, 1660)
    by = {r["skill"]: r for r in rows}
    assert by["Python"]["significant"] and by["Python"]["gap"] == pytest.approx(700 / 1660)
    assert "Statistics tool" not in by  # below the minimum market mentions, so not tested


def test_a_skill_the_courses_cover_well_is_not_a_gap():
    tracked = pd.DataFrame({"skill_id": [1], "canonical_name": ["Python"]})
    courses = ["We use Python throughout this course."] * 60
    rows = op.analyze(courses, tracked, {1: 700}, 1660)
    assert not rows[0]["significant"]


def test_real_database_example_runs_end_to_end():
    import sqlite3
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    conn = sqlite3.connect(os.path.join(base, "database", "aligned.db"))
    tracked = pd.read_sql_query("SELECT DISTINCT s.skill_id, s.canonical_name FROM extractions e JOIN skills s ON s.skill_id = e.skill_id WHERE e.source_type='posting'", conn)
    counts = dict(conn.execute("SELECT skill_id, COUNT(DISTINCT source_id) FROM extractions WHERE source_type='posting' AND method='baseline_keyword' GROUP BY skill_id").fetchall())
    courses = op.parse_pasted("Database Systems. SQL and indexing.\n\nMachine Learning. Python and neural networks.")
    rows = op.analyze(courses, tracked, counts, 1660)
    assert rows and all("q_value" in r for r in rows)
