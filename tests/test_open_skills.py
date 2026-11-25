"""Any skill a visitor types must get a result, not a rejection.

Runs against the real committed database, with no Streamlit needed (so it
also runs in CI).
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from services.open_skills import (  # noqa: E402
    Corpus, SkillSignal, measure, measure_items, mentions, parse_items,
)

DB = os.path.join(os.path.dirname(__file__), "..", "database", "aligned.db")


@pytest.fixture(scope="module")
def corpora():
    con = sqlite3.connect(DB)
    postings = Corpus([r[0] for r in con.execute("SELECT description FROM postings")])
    courses = Corpus([r[0] for r in con.execute("SELECT description FROM courses")])
    con.close()
    return postings, courses


# ---- parsing -------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("SQL, AWS and basic machine learning", ["SQL", "AWS", "machine learning"]),
    ("Python\nSQL\nAWS", ["Python", "SQL", "AWS"]),
    ("I have experience with SQL and Tableau", ["SQL", "Tableau"]),
    ("Python (3 years), R, C++, C#", ["Python", "R", "C++", "C#"]),
    ("Node.js.", ["Node.js"]),
    ("Research and Development, data viz", ["research and development", "data viz"]),
    ("Education\nSkills\nPython", ["Python"]),
    ("", []),
    ("   ", []),
])
def test_parse_items(text, expected):
    assert parse_items(text) == expected


def test_duplicates_are_removed_case_insensitively():
    assert parse_items("SQL, sql, Sql") == ["SQL"]


def test_item_count_is_capped():
    assert len(parse_items(", ".join(f"skill{i}" for i in range(500)))) == 40


def test_prose_does_not_turn_into_junk_items():
    prose = ("I spent two years building data tools for a small research team and enjoyed it, "
             "honestly it was great fun and a lot of work for me and the team overall, "
             "more words here to pass the forty word mark easily, okay good enough now yes")
    assert parse_items(prose) == []


def test_prose_still_finds_skills_with_everyday_names():
    prose = ("Over several years I built reporting for finance and operations teams, moved "
             "data between systems, wrote queries in SQL every day and later ran jobs on AWS, "
             "which gave me a good base for the work ahead of me in analytics roles overall")
    assert {"SQL", "AWS"} <= set(parse_items(prose))


# ---- matching ------------------------------------------------------------

@pytest.mark.parametrize("term,text,expected", [
    ("SQL", "Strong SQL skills required", True),
    ("sql", "Strong SQL skills required", True),
    ("AWS", "Experience with Amazon Web Services", True),
    ("R", "Proficient in R and Python", True),
    ("R", "the report was rendered", False),          # short names are case-sensitive
    ("Go", "we use Go and Rust", True),
    ("Go", "we go to market with Golang", False),       # lowercase "go" is just a word
    ("C", "C++ and C# experience", False),             # C must not match C++ / C#
    ("C++", "C++ and C# experience", True),
    ("dashboard", "build dashboards for execs", True),  # plural
    ("Java", "JavaScript and TypeScript", False),       # Java is not JavaScript
    ("machine learning", "Machine Learning engineer", True),
    ("ML", "ML models and machine learning", True),
])
def test_mentions(term, text, expected):
    assert mentions(term, text) is expected


# ---- measuring against the real data -------------------------------------

def test_sql_is_in_demand_and_rarely_named_in_courses(corpora):
    s = measure("SQL", *corpora)
    assert s.posting_share > 0.25
    assert s.course_share < 0.05
    assert "much more often" in s.reading


def test_aws_alias_counts_the_long_name_too(corpora):
    postings, courses = corpora
    assert measure("AWS", postings, courses).posting_n >= measure("Amazon Web Services", postings, courses).posting_n


def test_unknown_skill_gets_a_result_not_an_error(corpora):
    s = measure("basket weaving", *corpora)
    assert (s.posting_n, s.course_n) == (0, 0)
    assert "Not found" in s.reading


def test_any_mix_of_skills_returns_one_row_each(corpora):
    text = "Python, SQL, AWS, stakeholder management, Figma, basket weaving, C++, R"
    signals = measure_items(text, *corpora)
    assert {s.term for s in signals} == {"Python", "SQL", "AWS", "stakeholder management", "Figma", "basket weaving", "C++", "R"}
    shares = [s.posting_n for s in signals]
    assert shares == sorted(shares, reverse=True)       # most demanded first


def test_hostile_input_is_safe(corpora):
    for text in ["<script>alert(1)</script>", "(((", "[a-z]+", ".*", "\\", "a" * 5000, "%s%s%s", "💥, 数据科学"]:
        measure_items(text, *corpora)                   # must not raise


def test_empty_corpus_does_not_divide_by_zero():
    s = SkillSignal("x", 0, 0, 0, 0)
    assert s.posting_share == 0 and s.course_share == 0


def test_job_terms_reads_short_entry_as_list_and_prose_by_known_terms():
    from services.open_skills import job_terms
    assert job_terms("SQL, AWS") == ["SQL", "AWS"]
    prose = ("We are hiring a data engineer to build reliable pipelines. You will write SQL daily, "
             "run workloads on AWS, and partner with analysts across the business. Bachelor's degree, "
             "five plus years, strong communication, and a love of clean data are all expected here.")
    terms = job_terms(prose)
    assert {"SQL", "AWS"} <= set(terms)
    assert not any("bachelor" in t.lower() for t in terms)   # no junk fragments from prose


# ---- typos ---------------------------------------------------------------

@pytest.fixture(scope="module")
def vocabulary():
    from services.open_skills import ALIASES
    con = sqlite3.connect(DB)
    names = {r[0] for r in con.execute(
        "SELECT DISTINCT s.canonical_name FROM extractions e JOIN skills s ON s.skill_id=e.skill_id "
        "WHERE e.source_type='posting' AND e.method='baseline_keyword'")}
    con.close()
    return names | {s[0] for s in ALIASES.values()}


@pytest.mark.parametrize("typo,expected", [
    ("kubernets", "Kubernetes"), ("kuberentes", "Kubernetes"), ("pyhton", "Python"),
    ("tableu", "Tableau"), ("dockr", None), ("postgress", "PostgreSQL"),
    ("tensorflo", "TensorFlow"), ("javascipt", "JavaScript"),
])
def test_common_typos_are_recognized(vocabulary, typo, expected):
    from services.open_skills import suggest
    got = suggest(typo, vocabulary)
    if expected is not None:
        assert got == expected
    # "dockr" is too short to guess safely; it must not be "corrected" to something wrong
    else:
        assert got in (None, "Docker")


@pytest.mark.parametrize("word", ["basket weaving", "Figma", "SQL", "python", "Kubernetes", "rust", "ruby", "stakeholder management"])
def test_real_or_unrelated_words_are_left_alone(vocabulary, word):
    from services.open_skills import suggest
    assert suggest(word, vocabulary) is None


def test_correct_typos_rewrites_only_the_misspelled_item(corpora, vocabulary):
    from services.open_skills import correct_typos
    text, fixes = correct_typos("Python, kubernets, basket weaving, SQL", vocabulary, *corpora)
    assert fixes == {"kubernets": "Kubernetes"}
    assert text == "Python, Kubernetes, basket weaving, SQL"


def test_a_skill_with_data_is_never_corrected(corpora, vocabulary):
    from services.open_skills import correct_typos
    _, fixes = correct_typos("Salesforce, Terraform, Figma", vocabulary, *corpora)
    assert fixes == {}
