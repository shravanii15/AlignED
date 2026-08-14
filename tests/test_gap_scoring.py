"""
test_gap_scoring.py

Tests for the two-proportion z-test in compute_gap_scores.py -- this is
the statistical core of the whole gap-scoring step (the thing that turns
"this program has 0% coverage and the market has 40% demand" into a real,
defensible claim of "this is a statistically significant gap" rather than
just an eyeballed guess). If this function is wrong, every gap score in
the project is wrong, so it's the single highest-value place to have
real tests.
"""

from compute_gap_scores import two_proportion_z_test


def test_identical_rates_are_not_significant():
    """If a program covers a skill at exactly the same rate as the
    market demands it, there's no gap at all -- the p-value should be
    nowhere near significant."""
    z, p_value = two_proportion_z_test(x1=20, n1=100, x2=20, n2=100)
    assert p_value > 0.05
    assert z == 0.0


def test_large_clear_gap_is_significant():
    """A program with 0% coverage of a skill that shows up in 40% of a
    large sample of postings is exactly the kind of real, obvious gap
    the whole project is built to catch -- this should always come back
    significant."""
    z, p_value = two_proportion_z_test(x1=0, n1=200, x2=664, n2=1660)  # 664/1660 = 40%
    assert p_value < 0.05
    assert z > 0  # z = (p2 - p1) / se, and demand (p2) > coverage (p1) here, so z is positive


def test_tiny_sample_noise_is_not_falsely_significant():
    """A program with just 1 course out of 5 happening to mention a
    skill (20%) vs. a market demand of 25% is a small, plausible-by-chance
    difference -- the test should NOT call this significant just because
    the raw percentages differ. This is exactly the "small sample size ->
    noise, not a real signal" problem the z-test exists to guard against."""
    z, p_value = two_proportion_z_test(x1=1, n1=5, x2=415, n2=1660)  # 20% vs 25%
    assert p_value > 0.05


def test_zero_denominator_returns_not_significant():
    """A program with zero courses (shouldn't happen in practice, but a
    real function needs to handle it safely) must not divide by zero --
    it should return a safe "not significant" result instead of crashing."""
    z, p_value = two_proportion_z_test(x1=0, n1=0, x2=100, n2=1000)
    assert p_value == 1.0
    assert z == 0.0


def test_swapping_groups_flips_sign_but_not_significance():
    """The test should be symmetric: comparing (A vs B) and (B vs A)
    should find the same statistical significance, just with the sign of
    z flipped, since it's the same underlying question asked backwards."""
    z1, p1 = two_proportion_z_test(x1=10, n1=100, x2=50, n2=200)
    z2, p2 = two_proportion_z_test(x1=50, n1=200, x2=10, n2=100)
    assert round(p1, 10) == round(p2, 10)
    assert round(z1, 10) == round(-z2, 10)
