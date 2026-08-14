"""
test_extraction.py

Tests for the keyword-matching logic in extract_baseline.py and
extract_common.py -- the fast, non-AI extraction method used across the
whole project at full scale (courses, postings, trend detection). The
trickiest part of this code is the word-boundary handling for symbols
like "C++" and "C#" (documented at length in build_match_pattern's
docstring), which is exactly the kind of thing that's easy to silently
break during a refactor without a test catching it.
"""

from extract_baseline import build_combined_pattern, build_match_pattern, extract_terms_from_text, extract_terms_from_text_fast
from extract_common import normalize_term


def test_java_does_not_match_inside_javascript():
    """The classic word-boundary bug: 'Java' is a real vocabulary term
    and a real substring of 'JavaScript', but they're different skills
    and must not be confused."""
    pattern = build_match_pattern("Java")
    assert pattern.search("I have experience with Java") is not None
    assert pattern.search("I have experience with JavaScript") is None


def test_symbol_terms_match_correctly():
    """C++ and C# contain regex-special and non-word characters, which
    is exactly why build_match_pattern() doesn't use Python's plain \\b
    word-boundary marker (see its docstring) -- these two cases are the
    reason that custom boundary logic exists at all."""
    cpp_pattern = build_match_pattern("C++")
    assert cpp_pattern.search("5 years of C++ experience") is not None
    assert cpp_pattern.search("Concurrency and parallelism") is None  # must not match inside "Concurrency"

    csharp_pattern = build_match_pattern("C#")
    assert csharp_pattern.search("Built APIs in C# and .NET") is not None


def test_matching_is_case_insensitive():
    pattern = build_match_pattern("Python")
    assert pattern.search("expert in PYTHON programming") is not None
    assert pattern.search("expert in python programming") is not None


def test_extract_terms_from_text_finds_all_present_terms():
    vocabulary = [
        {"term": "Python", "type": "technology"},
        {"term": "Docker", "type": "technology"},
        {"term": "Kubernetes", "type": "technology"},
    ]
    vocabulary_with_patterns = [(entry, build_match_pattern(entry["term"])) for entry in vocabulary]
    found = extract_terms_from_text("Looking for a Python and Docker expert.", vocabulary_with_patterns)
    found_terms = {f["term"] for f in found}
    assert found_terms == {"Python", "Docker"}


def test_combined_pattern_matches_same_as_individual_patterns():
    """The combined-regex approach (build_combined_pattern) was built
    purely as a speed optimization over the original one-pattern-per-term
    approach (build_match_pattern + extract_terms_from_text) -- it must
    find the exact same matches, just faster. This test is the guarantee
    that optimization didn't quietly change the results."""
    terms = ["Python", "Docker", "C++", "Git"]
    text = "5 years of C++ and Python. Familiar with Docker and Git workflows."

    vocabulary_with_patterns = [({"term": t, "type": "technology"}, build_match_pattern(t)) for t in terms]
    slow_result = {f["term"] for f in extract_terms_from_text(text, vocabulary_with_patterns)}

    term_lookup = {normalize_term(t): {"term": t, "type": "technology"} for t in terms}
    combined_pattern = build_combined_pattern(terms)
    fast_result = {f["term"] for f in extract_terms_from_text_fast(text, combined_pattern, term_lookup)}

    assert slow_result == fast_result == {"Python", "Docker", "C++", "Git"}


def test_normalize_term_collapses_whitespace_and_lowercases():
    assert normalize_term("  Python   Programming ") == "python programming"
    assert normalize_term("SQL") == "sql"
