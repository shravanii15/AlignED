"""
test_trends.py

Tests for classify_trend() and apply_fdr_correction() in
compute_skill_trends.py.

classify_trend() turns a regression slope + significance value into the
"rising" / "falling" / "no clear trend" label shown throughout the
dashboard -- a small function, but it's the exact boundary where a real
statistical result becomes a plain-English claim, so it's worth pinning
down precisely.

Phase 0.2 (Sprint 6) change: classify_trend()'s second argument is now
the Benjamini-Hochberg FDR-corrected q-value, not the raw p-value --
testing ~67 skills for a trend simultaneously has the same
multiple-comparisons problem gap scoring already corrects for, and using
the raw p-value alone overstated confidence (verified on this project's
real data: 9 skills looked significant at raw p<0.05, 0 survived FDR
correction at q<0.05). The tests below use the q_value parameter name to
make that explicit -- a test still written as p_value=... would now fail
with a TypeError, which is the point: it forces any future caller to
notice the semantic change.
"""

from compute_skill_trends import apply_fdr_correction, classify_trend


def test_significant_positive_slope_is_rising():
    assert classify_trend(slope=0.02, q_value=0.01) == "rising"


def test_significant_negative_slope_is_falling():
    assert classify_trend(slope=-0.015, q_value=0.03) == "falling"


def test_non_significant_positive_slope_is_no_clear_trend():
    """A positive slope alone isn't enough -- if the q-value says it
    could plausibly be noise (or chance from running many tests at once),
    it must NOT be labeled 'rising'. This is the exact bug class the
    whole trend-detection step exists to avoid (see the sparse-weeks
    data-quality issue documented in the script)."""
    assert classify_trend(slope=0.05, q_value=0.5) == "no clear trend"


def test_non_significant_negative_slope_is_no_clear_trend():
    assert classify_trend(slope=-0.05, q_value=0.9) == "no clear trend"


def test_boundary_q_value_is_not_significant():
    """q_value exactly at the threshold should NOT count as significant
    -- the significance test in the project is a strict less-than, not
    less-than-or-equal."""
    assert classify_trend(slope=0.01, q_value=0.05) == "no clear trend"


def test_fdr_correction_never_makes_a_result_more_significant():
    """Each corrected q-value must be >= its raw p-value -- FDR
    correction can only make a result look less significant, never more,
    which is exactly the conservative direction wanted when guarding
    against false positives from running many tests at once."""
    p_values = [0.001, 0.01, 0.03, 0.2, 0.8]
    q_values = apply_fdr_correction(p_values)
    assert all(q >= p for p, q in zip(p_values, q_values))


def test_fdr_correction_can_eliminate_all_raw_significant_results():
    """Reproduces this project's real finding: several skills can look
    significant at raw p<0.05 while none survive FDR correction once
    the full family of ~67 simultaneous tests is accounted for."""
    p_values = [0.008, 0.012, 0.02, 0.03, 0.04] + [0.3] * 62
    q_values = apply_fdr_correction(p_values)
    assert sum(1 for p in p_values if p < 0.05) == 5
    assert sum(1 for q in q_values if q < 0.05) == 0


def test_fdr_correction_empty_input():
    assert apply_fdr_correction([]) == []
