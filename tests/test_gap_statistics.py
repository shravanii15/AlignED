"""
test_gap_statistics.py

compare_proportions() must use Fisher's exact test when expected cell counts
are small. The z-test's normal approximation is unreliable there, and the
project has programs with only 5, 13 and 19 course descriptions.
"""

import pytest
from scipy.stats import fisher_exact

from compute_gap_scores import compare_proportions, expected_cell_counts, two_proportion_z_test


def test_zero_of_five_vs_fifty_of_hundred_uses_fisher_and_is_not_significant():
    """The confirmed defect: the z-test gives p = 0.0289 (falsely
    significant); Fisher's exact test gives p = 0.0580."""
    _, z_p = two_proportion_z_test(0, 5, 50, 100)
    assert z_p < 0.05
    _, p, method = compare_proportions(0, 5, 50, 100)
    assert method == "fisher_exact"
    assert p == pytest.approx(0.057968968, abs=1e-6)
    assert p >= 0.05


def test_fisher_p_value_matches_scipy_directly():
    _, p, method = compare_proportions(1, 5, 25, 100)
    assert method == "fisher_exact"
    assert p == pytest.approx(fisher_exact([[1, 4], [25, 75]])[1])


def test_zero_of_five_vs_ten_of_hundred_is_not_significant():
    _, p, method = compare_proportions(0, 5, 10, 100)
    assert method == "fisher_exact"
    assert p > 0.05


def test_large_samples_keep_the_z_test():
    z, p, method = compare_proportions(0, 200, 664, 1660)
    assert method == "z_test"
    assert z > 0 and p < 1e-10
    assert (z, p) == two_proportion_z_test(0, 200, 664, 1660)


def test_method_switches_exactly_at_the_expected_count_threshold():
    # 5 courses, 5 successes of 105 total -> smallest expected cell is 5*5/105 < 5
    assert compare_proportions(0, 5, 5, 100)[2] == "fisher_exact"
    # a comfortably large table has every expected count >= 5
    assert min(expected_cell_counts(20, 100, 40, 100)) >= 5
    assert compare_proportions(20, 100, 40, 100)[2] == "z_test"


@pytest.mark.parametrize("args", [(0, 0, 5, 10), (3, 10, 0, 0), (0, 0, 0, 0)])
def test_zero_denominators_are_not_testable(args):
    assert compare_proportions(*args) == (0.0, 1.0, "none")


def test_equal_proportions_give_p_of_one():
    _, p, _ = compare_proportions(20, 100, 20, 100)
    assert p == pytest.approx(1.0)


def test_both_zero_percent_and_both_hundred_percent_are_not_testable():
    assert compare_proportions(0, 10, 0, 100) == (0.0, 1.0, "none")
    assert compare_proportions(10, 10, 100, 100) == (0.0, 1.0, "none")


def test_counts_out_of_range_raise():
    with pytest.raises(ValueError):
        compare_proportions(6, 5, 1, 10)
    with pytest.raises(ValueError):
        compare_proportions(-1, 5, 1, 10)


def test_p_values_are_always_valid_probabilities():
    for x1, n1, x2, n2 in [(0, 5, 50, 100), (3, 13, 200, 1660), (0, 295, 664, 1660), (1, 19, 9, 1660)]:
        _, p, _ = compare_proportions(x1, n1, x2, n2)
        assert 0.0 <= p <= 1.0
