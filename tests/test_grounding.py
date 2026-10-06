"""
test_grounding.py

Regression tests for how free-text skill terms (an LLM's own words) are
grounded to the O*NET vocabulary. The original implementation used
difflib character similarity with a 0.70 cutoff, which mapped "SQL" to
"NoSQL", "Machine Learning" to "Active Learning" and "statistics" to
"STATISTICA". These tests run against the project's real 1,597-term
vocabulary (the skills table in the committed database).
"""

import os
import sqlite3

import pytest

from extract_common import (
    GROUNDING_LOG, build_normalized_lookup, build_variant_index, fuzzy_match_term,
    ground_term, is_lexical_conflict, normalize_term,
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "aligned.db")


@pytest.fixture(scope="module")
def vocab():
    conn = sqlite3.connect(DB_PATH)
    vocabulary = [{"term": row[0], "type": "technology"} for row in conn.execute("SELECT canonical_name FROM skills")]
    conn.close()
    lookup = build_normalized_lookup(vocabulary)
    return vocabulary, lookup, build_variant_index(lookup)


def grounded(raw, vocab):
    vocabulary, lookup, index = vocab
    entry, method = ground_term(raw, vocabulary, lookup, index)
    return (entry["term"] if entry else None), method


def test_sql_never_maps_to_nosql_or_mysql(vocab):
    term, _ = grounded("SQL", vocab)
    assert term not in {"NoSQL", "MySQL", "PostgreSQL"}
    assert term == "Structured query language SQL"


def test_machine_learning_never_maps_to_active_learning(vocab):
    term, _ = grounded("Machine Learning", vocab)
    assert term != "Active Learning"


def test_statistics_never_maps_to_statistica(vocab):
    term, _ = grounded("statistics", vocab)
    assert term != "STATISTICA"


@pytest.mark.parametrize("raw, expected", [
    ("AWS", "Amazon Web Services AWS software"),
    ("Amazon Web Services", "Amazon Web Services AWS software"),
    ("Kafka", "Apache Kafka"),
    ("Airflow", "Apache Airflow"),
])
def test_known_abbreviations_ground_through_the_alias_map(vocab, raw, expected):
    term, method = grounded(raw, vocab)
    assert term == expected
    assert method == "alias"


@pytest.mark.parametrize("raw", ["MySQL", "Python", "Git", "NoSQL", "Active Learning", "Docker"])
def test_exact_terms_stay_exact_and_case_insensitive(vocab, raw):
    assert grounded(raw, vocab) == (raw, "exact")
    assert grounded(raw.upper(), vocab)[0] == raw
    assert grounded("  " + raw.lower() + "  ", vocab)[0] == raw


def test_plural_and_punctuation_variants_ground_by_variant(vocab):
    assert grounded("Pythons", vocab) == ("Python", "variant")


def test_unknown_terms_are_dropped_not_force_fit(vocab):
    assert grounded("quantum basket weaving", vocab) == (None, "none")
    assert grounded("", vocab) == (None, "none")


def test_fuzzy_match_term_wrapper_returns_entry_or_none(vocab):
    vocabulary, lookup, index = vocab
    assert fuzzy_match_term("Python", vocabulary, lookup)["term"] == "Python"
    assert fuzzy_match_term("SQL", vocabulary, lookup)["term"] != "NoSQL"


def test_alias_whose_target_is_missing_from_vocabulary_is_ignored():
    vocabulary = [{"term": "Python", "type": "technology"}]
    lookup = build_normalized_lookup(vocabulary)
    assert ground_term("SQL", vocabulary, lookup)[0] is None


def test_variant_collision_is_rejected_as_ambiguous():
    vocabulary = [{"term": "Data Tool", "type": "technology"}, {"term": "Data Tools", "type": "technology"}]
    lookup = build_normalized_lookup(vocabulary)
    entry, method = ground_term("data-tool", vocabulary, lookup)
    assert entry is None and method == "none"


def test_every_grounding_decision_is_logged(vocab):
    before = len(GROUNDING_LOG)
    grounded("Kafka", vocab)
    assert len(GROUNDING_LOG) == before + 1
    assert GROUNDING_LOG[-1][2] == "alias"


@pytest.mark.parametrize("raw, candidate, conflict", [
    ("sql", "nosql", True),
    ("sql", "mysql", True),
    ("java", "javascript", True),
    ("machine learning", "active learning", True),
    ("statistics", "statistica", True),
    ("azure", "microsoft azure software", False),
    ("terraform", "ibm terraform", False),
    ("cloud infrastructure", "cloud computing", False),
])
def test_lexical_conflict_guard_for_embedding_matches(raw, candidate, conflict):
    assert is_lexical_conflict(raw, candidate) is conflict


def test_embedding_fallback_rejects_close_but_wrong_neighbour(monkeypatch):
    """renormalize.ground_with_embeddings must not let a high embedding
    score turn SQL into MySQL. Uses a fake similarity row, so no model or
    torch is needed."""
    import sys
    import types

    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = object
    fake.util = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    import importlib
    import renormalize
    importlib.reload(renormalize)

    vocabulary = [{"term": "MySQL", "type": "technology"}, {"term": "Cloud computing", "type": "technology"}]
    lookup = build_normalized_lookup(vocabulary)
    index = build_variant_index(lookup)

    entry, method = renormalize.ground_with_embeddings("SQL", vocabulary, lookup, index, [0.95, 0.10])
    assert entry is None

    entry, method = renormalize.ground_with_embeddings("cloud infrastructure", vocabulary, lookup, index, [0.10, 0.90])
    assert entry["term"] == "Cloud computing" and method == "embedding"

    entry, _ = renormalize.ground_with_embeddings("something else", vocabulary, lookup, index, [0.20, 0.30])
    assert entry is None


def test_normalize_term_is_unchanged():
    assert normalize_term("  Machine   Learning ") == "machine learning"
