"""
test_text_matching.py

Tests for dashboard/utils/text.py's extract_user_skills(), which powers the
skill plan and the job-match tool. The risky part is very short skill names
("R", "Go", "C"): matched case-insensitively they fire on ordinary English,
so they are matched case-sensitively and the tests pin that behavior down.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from utils.text import extract_user_skills  # noqa: E402

VOCAB = pd.DataFrame({
    "skill_id": [1, 2, 3, 4, 5],
    "canonical_name": ["Python", "R", "Go", "SQL", "Machine learning"],
})


def names(ids):
    return set(VOCAB[VOCAB["skill_id"].isin(ids)]["canonical_name"])


def test_matches_regardless_of_case_for_normal_names():
    assert names(extract_user_skills("I use python and SQL daily", VOCAB)) == {"Python", "SQL"}


def test_multiword_skill_is_matched():
    assert "Machine learning" in names(extract_user_skills("Experience with machine learning", VOCAB))


def test_ordinary_word_go_is_not_the_go_language():
    assert "Go" not in names(extract_user_skills("We go to market quickly", VOCAB))


def test_capitalised_go_and_r_are_matched():
    assert names(extract_user_skills("Experience with Go and R", VOCAB)) == {"Go", "R"}


def test_lowercase_r_inside_a_sentence_is_not_the_r_language():
    assert "R" not in names(extract_user_skills("you are r great fit", VOCAB))


def test_skill_name_inside_a_longer_word_is_not_matched():
    assert "Go" not in names(extract_user_skills("Experience with Google Cloud", VOCAB))
    assert "Python" not in names(extract_user_skills("Pythonic style", VOCAB))


def test_empty_text_matches_nothing():
    assert extract_user_skills("", VOCAB) == set()
