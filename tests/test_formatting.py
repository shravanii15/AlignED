"""Regression tests for posting display helpers.

Bug: NULLs from SQLite arrive as NaN after pandas, NaN is truthy, and the
dashboard showed "nan · nan · nan" under example postings.
"""

import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from utils.formatting import clean_text, format_posting_details, posting_headline  # noqa: E402

NAN = float("nan")


def test_all_missing_values_give_no_details():
    row = {"location": NAN, "salary_min": NAN, "salary_max": NAN, "posted_date": NAN}
    assert format_posting_details(row) is None


def test_none_and_text_nan_are_missing():
    row = {"location": "nan", "salary_min": None, "salary_max": None, "posted_date": "None"}
    assert format_posting_details(row) is None


def test_details_show_only_what_exists():
    row = {"location": "Chicago", "salary_min": NAN, "salary_max": NAN, "posted_date": "2026-08-10T15:09:32Z"}
    assert format_posting_details(row) == "Chicago  ·  2026-08-10"


def test_equal_salary_bounds_show_one_number():
    row = {"location": None, "salary_min": 142871.56, "salary_max": 142871.56, "posted_date": None}
    assert format_posting_details(row) == "$142,872"


def test_salary_range():
    row = {"location": None, "salary_min": 90000, "salary_max": 120000, "posted_date": None}
    assert format_posting_details(row) == "$90,000 to $120,000"


def test_headline_never_contains_nan_or_none():
    assert posting_headline({"title": "Data Scientist", "company": NAN}) == "Data Scientist"
    assert posting_headline({"title": "Data Scientist", "company": None}) == "Data Scientist"
    assert posting_headline({"title": "Data Scientist", "company": "PayPal"}) == "Data Scientist, PayPal"


def test_pandas_row_with_nulls_has_no_nan_text():
    df = pd.DataFrame(
        [{"title": "Analyst", "company": None, "location": None,
          "salary_min": None, "salary_max": None, "posted_date": None},
         {"title": "Scientist", "company": "X", "location": "NYC",
          "salary_min": 100000.0, "salary_max": 100000.0, "posted_date": "2026-01-02"}]
    )
    for _, row in df.iterrows():
        text = f"{posting_headline(row)} {format_posting_details(row) or ''}".lower()
        assert "nan" not in text and "none" not in text


def test_clean_text():
    assert clean_text(math.nan) is None
    assert clean_text("  ") is None
    assert clean_text(" Boston ") == "Boston"
