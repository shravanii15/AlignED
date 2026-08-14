"""
test_trends.py

Tests for classify_trend() in compute_skill_trends.py -- the function
that turns a raw regression slope + p-value into the "rising" / "falling"
/ "no clear trend" label shown throughout the dashboard. This is a small
function, but it's the exact boundary where a real statistical result
becomes a plain-English claim, so it's worth pinning down precisely.
"""

from compute_skill_trends import classify_trend


def test_significant_positive_slope_is_rising():
    assert classify_trend(slope=0.02, p_value=0.01) == "rising"


def test_significant_negative_slope_is_falling():
    assert classify_trend(slope=-0.015, p_value=0.03) == "falling"


def test_non_significant_positive_slope_is_no_clear_trend():
    """A positive slope alone isn't enough -- if the p-value says it
    could plausibly be noise, it must NOT be labeled 'rising'. This is
    the exact bug class the whole trend-detection step exists to avoid
    (see the sparse-weeks data-quality issue documented in the script)."""
    assert classify_trend(slope=0.05, p_value=0.5) == "no clear trend"


def test_non_significant_negative_slope_is_no_clear_trend():
    assert classify_trend(slope=-0.05, p_value=0.9) == "no clear trend"


def test_boundary_p_value_is_not_significant():
    """p_value exactly at the threshold should NOT count as significant
    -- the significance test in the project is a strict less-than, not
    less-than-or-equal."""
    assert classify_trend(slope=0.01, p_value=0.05) == "no clear trend"
