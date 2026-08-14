"""
test_gap_scoring.py

Tests for the statistical core of compute_gap_scores.py:
- two_proportion_z_test(): the per-skill significance test
- apply_fdr_correction(): the Benjamini-Hochberg correction applied
  across each program's full set of tests, so that running ~70 tests at
  once doesn't produce a flood of false "significant" gaps just from
  sheer test volume (the classic multiple-comparisons problem).

If either of these is wrong, every gap score in the project is wrong, so
this is the single highest-value place in the whole codebase to have
real tests.
"""

from compute_gap_scores import apply_fdr_correction, two_proportion_z_test


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


def test_fdr_correction_never_makes_a_p_value_smaller():
    """Correcting for multiple comparisons can only make a result look
    LESS significant (or equally significant), never more -- that's the
    whole point of guarding against false positives. Every corrected
    q-value must be >= its original raw p-value."""
    raw_p_values = [0.001, 0.01, 0.03, 0.04, 0.2, 0.5, 0.8]
    q_values = apply_fdr_correction(raw_p_values)
    assert len(q_values) == len(raw_p_values)
    for p, q in zip(raw_p_values, q_values):
        assert q >= p - 1e-12  # tiny tolerance for floating point


def test_fdr_correction_filters_noise_but_keeps_real_signal():
    """The whole motivation for this correction, demonstrated directly:
    simulate 70 tests like a real program would run -- 65 that are pure
    random noise (no real effect) plus 5 with a genuinely tiny, real
    p-value. Pure chance alone means a handful of the 65 noise p-values
    will land under 0.05 and look "significant" before correction. After
    correction, most/all of that noise should be filtered out, while the
    5 genuinely strong signals must still survive -- that's exactly the
    behavior that makes the FDR correction worth having."""
    import random
    rng = random.Random(42)
    noise_p_values = [rng.uniform(0.001, 1.0) for _ in range(65)]
    real_signal_p_values = [0.0001] * 5
    all_p_values = noise_p_values + real_signal_p_values

    q_values = apply_fdr_correction(all_p_values)
    significant_before = sum(1 for p in all_p_values if p < 0.05)
    significant_after = sum(1 for q in q_values if q < 0.05)

    assert significant_after < significant_before  # correction removes some false positives
    assert all(q < 0.05 for q in q_values[-5:])  # the 5 genuinely real signals must still survive


def test_fdr_correction_empty_input():
    assert apply_fdr_correction([]) == []
