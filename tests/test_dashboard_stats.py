"""The dashboard's pure-Python tests must agree with the SciPy versions the pipeline uses."""

import os
import random
import sys

import pytest
from scipy.stats import false_discovery_control

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from compute_gap_scores import compare_proportions as scipy_compare  # noqa: E402
from services import stats  # noqa: E402


def test_matches_scipy_on_random_tables():
    rng = random.Random(5)
    for _ in range(400):
        n1, n2 = rng.randint(2, 300), rng.randint(50, 1700)
        x1, x2 = rng.randint(0, n1), rng.randint(0, n2)
        _, p_ref, method_ref = scipy_compare(x1, n1, x2, n2)
        p, method = stats.compare_proportions(x1, n1, x2, n2)
        assert method == method_ref
        assert p == pytest.approx(p_ref, rel=1e-6, abs=1e-9)


def test_fisher_small_table_known_value():
    # the example from compute_gap_scores: 0 of 5 courses vs 50 of 100 postings
    p, method = stats.compare_proportions(0, 5, 50, 100)
    assert method == "fisher_exact" and p == pytest.approx(0.058, abs=0.002)


def test_degenerate_inputs_are_not_significant():
    assert stats.compare_proportions(0, 10, 0, 100) == (1.0, "none")
    assert stats.compare_proportions(5, 0, 5, 100) == (1.0, "none")


def test_benjamini_hochberg_matches_scipy():
    rng = random.Random(9)
    ps = [rng.random() ** 3 for _ in range(60)]
    assert stats.benjamini_hochberg(ps) == pytest.approx(list(false_discovery_control(ps, method="bh")), rel=1e-9)
    assert stats.benjamini_hochberg([]) == []
