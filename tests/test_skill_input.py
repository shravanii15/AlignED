"""What a visitor typing into a skills box actually sees.

Regression: typing everyday names ("Excel", "Power BI", "AWS") matched
nothing, because skills are stored under longer official names, and the
page gave no useful feedback. These tests drive the real pages.
"""

import os
import sqlite3
import sys

import pandas as pd
import pytest



def _apptest():
    """CI installs only the light test requirements (no Streamlit), so the
    page-level tests skip there and run wherever Streamlit is installed.
    The plain matching tests below still run everywhere."""
    return pytest.importorskip("streamlit.testing.v1").AppTest


DASH = os.path.join(os.path.dirname(__file__), "..", "dashboard")
sys.path.insert(0, DASH)

from utils.constants import AMBIGUOUS_GENERIC_TERMS  # noqa: E402
from utils.text import extract_user_skills, unrecognized_items  # noqa: E402

DB = os.path.join(os.path.dirname(__file__), "..", "database", "aligned.db")


@pytest.fixture(scope="module")
def tracked():
    con = sqlite3.connect(DB)
    df = pd.read_sql(
        "SELECT DISTINCT s.skill_id, s.canonical_name FROM extractions e "
        "JOIN skills s ON s.skill_id = e.skill_id "
        "WHERE e.source_type='posting' AND e.method='baseline_keyword'", con)
    con.close()
    return df[~df["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]


def _names(text, tracked):
    ids = extract_user_skills(text, tracked)
    return set(tracked[tracked["skill_id"].isin(ids)]["canonical_name"])


@pytest.mark.parametrize("typed,official", [
    ("Excel", "Microsoft Excel"), ("excel", "Microsoft Excel"),
    ("Power BI", "Microsoft Power BI"), ("Spark", "Apache Spark"),
    ("Airflow", "Apache Airflow"), ("Java", "Oracle Java"),
    ("sklearn", "Scikit-learn"), ("Postgres", "PostgreSQL"),
    ("k8s", "Kubernetes"), ("Python", "Python"), ("python", "Python"),
])
def test_everyday_names_match_official_skills(tracked, typed, official):
    assert official in _names(typed, tracked)


def test_aliases_never_invent_a_skill_that_is_not_tracked(tracked):
    only_python = tracked[tracked["canonical_name"] == "Python"]
    assert _names("Excel, Power BI, AWS", only_python) == set()


def test_unrecognized_items_are_reported(tracked):
    unknown = unrecognized_items("Python, Docker, basket weaving, communication", tracked)
    assert unknown == ["basket weaving", "communication"]


def test_long_free_text_is_not_judged_item_by_item(tracked):
    paragraph = "I spent two years building data tools for a small research team and enjoyed it a lot"
    assert unrecognized_items(paragraph, tracked) == []


@pytest.mark.parametrize("page,box_label,button", [
    ("sections/profile.py", "Your skills, resume text, or courses taken", "Find jobs that fit me"),
])
@pytest.mark.parametrize("text", [
    "SQL", "Excel", "machine learning", "asdf qwerty", "!!!", "   ", "Python",
    "Python, SQL, Excel, Power BI, AWS", "x" * 5000, "Python\nDocker\nTableau",
    "I have worked with pandas, numpy and scikit-learn",
    "ÄÖÜ 数据科学 python", "<script>alert(1)</script> Python",
])
def test_profile_page_always_responds(page, box_label, button, text):
    at = _run_profile(text)
    assert not at.exception, at.exception
    shown = [e.value for e in at.warning] + [e.value for e in at.info] + [e.value for e in at.markdown]
    assert shown, "page showed nothing at all"


def _run_profile(text):
    script = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from sections.profile import render_profile_builder\n"
        "render_profile_builder()\n" % os.path.abspath(DASH)
    )
    at = _apptest().from_string(script, default_timeout=60).run()
    at.text_area[0].set_value(text)
    at.button[0].click()
    at.run()
    return at


@pytest.mark.parametrize("job,me", [
    ("Python Docker Tableau Kubernetes", "SQL"),
    ("Python Docker Tableau", "Excel, Power BI"),
    ("Python Docker Tableau", ""),
    ("nothing technical here at all", "Python"),
    ("Python Docker", "machine learning, communication"),
    ("", "Python"),
])
def test_match_page_always_responds(job, me):
    script = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from sections.match_job import render_match_job\n"
        "render_match_job()\n" % os.path.abspath(DASH)
    )
    at = _apptest().from_string(script, default_timeout=60).run()
    at.text_area[0].set_value(job)
    at.text_area[1].set_value(me)
    [b for b in at.button if b.label == "Check my match"][0].click()
    at.run()
    assert not at.exception, at.exception
    shown = [e.value for e in at.warning] + [e.value for e in at.markdown]
    assert shown


def _run_match(job, me):
    script = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from sections.match_job import render_match_job\n"
        "render_match_job()\n" % os.path.abspath(DASH)
    )
    at = _apptest().from_string(script, default_timeout=60).run()
    at.text_area[0].set_value(job)
    at.text_area[1].set_value(me)
    [b for b in at.button if b.label == "Check my match"][0].click()
    at.run()
    return at


def test_posting_with_only_untracked_skills_still_gets_a_result():
    """Regression: a posting of 'SQL, AWS' showed 'no tracked skills' and nothing else."""
    at = _run_match("SQL, AWS", "")
    assert not at.exception, at.exception
    assert not at.warning
    assert {"SQL", "AWS"} <= set(at.dataframe[0].value["Skill"])


def test_real_posting_surfaces_sql_and_aws_alongside_tracked_tools():
    job = ("Data Engineer. You will build pipelines in Python and Airflow, write complex SQL, "
           "and deploy on AWS using Docker. Experience with machine learning is a plus. " * 3)
    at = _run_match(job, "SQL, Python")
    assert not at.exception, at.exception
    extras = [d.value for d in at.dataframe if "You listed it" in d.value.columns][0].set_index("Skill")
    assert extras.loc["SQL", "You listed it"] == "Yes"
    assert extras.loc["AWS", "You listed it"] == "No"


def test_unrecognized_feedback_is_visible_on_match_page():
    script = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from sections.match_job import render_match_job\n"
        "render_match_job()\n" % os.path.abspath(DASH)
    )
    at = _apptest().from_string(script, default_timeout=60).run()
    at.text_area[0].set_value("Python Docker Tableau")
    at.text_area[1].set_value("Python, basket weaving")
    [b for b in at.button if b.label == "Check my match"][0].click()
    at.run()
    assert not at.exception, at.exception
    table = at.dataframe[0].value
    assert "basket weaving" in set(table["Skill"])        # every typed skill gets a row
    assert "In this posting" in table.columns


def test_no_best_fit_is_claimed_when_nothing_overlaps():
    """Regression: typing only 'Figma' showed 'Your best fit ... 0/15'."""
    at = _run_profile("SQL, AWS, machine learning, Figma, basket weaving")
    assert not at.exception, at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "Your best fit" not in page
    assert any("no best fit" in i.value for i in at.info)
    assert {"SQL", "Figma", "basket weaving"} <= set(at.dataframe[0].value["Skill"])


def test_best_fit_still_shown_when_there_is_overlap():
    at = _run_profile("Python, Docker, Linux")
    assert not at.exception, at.exception
    assert "Your best fit" in " ".join(m.value for m in at.markdown)


def test_sql_and_aws_get_results_on_fit_page():
    at = _run_profile("SQL, AWS, machine learning")
    assert not at.exception, at.exception
    table = at.dataframe[0].value
    assert {"SQL", "AWS", "machine learning"} <= set(table["Skill"])
    assert table.set_index("Skill").loc["SQL", "Job postings"] > 25


def test_misspelled_skill_is_read_correctly_on_fit_page():
    """Regression: 'kubernets' matched nothing."""
    at = _run_profile("Python, kubernets")
    assert not at.exception, at.exception
    assert any("Kubernetes" in c.value and "kubernets" in c.value for c in at.caption)
    skills = set(at.dataframe[0].value["Skill"])
    assert "Kubernetes" in skills and "kubernets" not in skills
    assert at.dataframe[0].value.set_index("Skill").loc["Kubernetes", "Job postings"] > 5


def test_misspelled_skill_is_read_correctly_on_match_page():
    at = _run_match("Python Docker Kubernetes Tableau", "kubernets, Pyhton")
    assert not at.exception, at.exception
    assert any("Kubernetes" in c.value for c in at.caption)
