"""
test_recommendations.py

Tests for build_rationale() in generate_recommendations.py, the
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
    assert "no course description in this program names it" in text  # zero coverage is not shown as "0%"
    assert "0%" not in text.replace("40%", "")


def test_rising_trend_adds_upward_language():
    text = build_rationale(
        skill_name="Docker", coverage_rate=0.0, demand_rate=0.10,
        gap_value=0.10, trend_label="rising", slope=0.01,
    )
    assert "rising" in text
    assert "Docker" in text


def test_falling_trend_adds_downward_language():
    text = build_rationale(
        skill_name="Perl", coverage_rate=0.02, demand_rate=0.05,
        gap_value=0.03, trend_label="falling", slope=-0.01,
    )
    assert "falling" in text


def test_no_trend_label_does_not_falsely_claim_a_trend():
    """If there's no significant trend, the rationale must not claim one
   it should say plainly that no trend was detected, not silently
    omit the topic (which could read as implying a trend either way)."""
    text = build_rationale(
        skill_name="Git", coverage_rate=0.0, demand_rate=0.07,
        gap_value=0.07, trend_label="no clear trend", slope=None,
    )
    assert "No clear demand trend" in text
    assert "rising" not in text
    assert "falling" not in text


def test_default_scope_reads_as_overall_market():
    """scope_label defaults to 'Overall market' when not passed, so
    existing callers (and this test) keep working, the rationale
    should read as a generic market comparison, not name a specific role."""
    text = build_rationale(
        skill_name="SQL", coverage_rate=0.1, demand_rate=0.5,
        gap_value=0.4, trend_label="no clear trend", slope=None,
    )
    assert "job postings we looked at" in text


def test_role_specific_scope_names_the_role_in_the_rationale():
    """When a recommendation is generated against a specific role cluster
    (not the overall market), the rationale text must say so explicitly
   a reader shouldn't have to guess whether 'the market' means every
    posting or just this one target role."""
    text = build_rationale(
        skill_name="AWS", coverage_rate=0.02, demand_rate=0.31,
        gap_value=0.29, trend_label="no clear trend", slope=None,
        scope_label="Data Science / Data Engineering",
    )
    assert "Data Science / Data Engineering postings" in text


def test_tiny_coverage_is_not_rounded_to_zero_percent():
    text = build_rationale(
        skill_name="Linux", coverage_rate=0.004, demand_rate=0.15,
        gap_value=0.146, trend_label="no clear trend", slope=None,
    )
    assert "fewer than 1%" in text
    assert "0%" not in text.replace("15%", "")


def test_normal_coverage_is_shown_as_a_percentage():
    text = build_rationale(
        skill_name="SQL", coverage_rate=0.12, demand_rate=0.30,
        gap_value=0.18, trend_label="no clear trend", slope=None,
    )
    assert "only 12%" in text
