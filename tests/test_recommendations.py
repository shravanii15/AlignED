"""
test_recommendations.py

Tests for build_rationale() in generate_recommendations.py -- the
function that turns raw numbers into the plain-English sentence shown
for every recommendation in the dashboard and PDF/Excel reports. Since
this text is user-facing, these tests check that the right numbers
actually appear in the right sentence, and that the trend-specific
wording only appears when it should.
"""

from generate_recommendations import build_rationale


def test_base_rationale_includes_skill_name_and_percentages():
    text = build_rationale(
        skill_name="Python", coverage_rate=0.0, demand_rate=0.40,
        gap_value=0.40, trend_label="no clear trend", slope=None,
    )
    assert "Python" in text
    assert "40%" in text  # demand rate
    assert "0%" in text  # coverage rate


def test_rising_trend_adds_upward_language():
    text = build_rationale(
        skill_name="Docker", coverage_rate=0.0, demand_rate=0.10,
        gap_value=0.10, trend_label="rising", slope=0.01,
    )
    assert "trending upward" in text
    assert "Docker" in text


def test_falling_trend_adds_downward_language():
    text = build_rationale(
        skill_name="Perl", coverage_rate=0.02, demand_rate=0.05,
        gap_value=0.03, trend_label="falling", slope=-0.01,
    )
    assert "trending downward" in text


def test_no_trend_label_does_not_falsely_claim_a_trend():
    """If there's no significant trend, the rationale must not claim one
    -- it should say plainly that no trend was detected, not silently
    omit the topic (which could read as implying a trend either way)."""
    text = build_rationale(
        skill_name="Git", coverage_rate=0.0, demand_rate=0.07,
        gap_value=0.07, trend_label="no clear trend", slope=None,
    )
    assert "No significant demand trend" in text
    assert "trending upward" not in text
    assert "trending downward" not in text
