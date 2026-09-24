"""sections/trends.py -- observed demand momentum: exploratory signals
about which tracked skills' demand might be rising or falling.

Sprint 6, Phase 0.2 rewrite: this page used to classify a skill as
"rising"/"falling" based on raw p<0.05 across all 67 skills tested
together, with no correction for running that many simultaneous
significance tests -- the same multiple-comparisons problem gap scoring
already corrects for (see Methodology). Applying the same
Benjamini-Hochberg FDR correction here (scripts/gap_analysis/
compute_skill_trends.py) revealed that 9 skills looked significant at
raw p<0.05, but 0 survive FDR correction at q<0.05. So this page no
longer claims confirmed statistical trends -- it shows the strongest
directional signals in the data, explicitly labeled as exploratory, with
both the raw p-value and the FDR-corrected q-value visible for every one
so a visitor can see exactly why "signal" and "significant" aren't the
same claim here."""

import streamlit as st

from services.database import run_query
from utils.layout import page_header

SIGNIFICANCE_THRESHOLD = 0.05
TOP_SIGNALS_SHOWN = 10


def render_trends():
    page_header(
        "📈", "Observed Demand Momentum",
        "Exploratory directional signals from ~124,000 real historical job postings, restricted to the 6 weeks "
        "with a real, meaningful volume of data. These are early signals over a short window, not confirmed "
        "long-range trends or forecasts -- see below and Methodology for exactly why.",
    )

    trends_df = run_query(
        """
        SELECT t.trend_label, t.slope, t.p_value, t.q_value, t.first_half_rate, t.second_half_rate, s.canonical_name
        FROM skill_trends t JOIN skills s ON s.skill_id = t.skill_id
        ORDER BY t.q_value ASC
        """
    )

    n_raw_significant = int((trends_df["p_value"] < SIGNIFICANCE_THRESHOLD).sum())
    n_fdr_significant = int((trends_df["q_value"] < SIGNIFICANCE_THRESHOLD).sum())

    if n_fdr_significant == 0:
        st.warning(
            f"**None of the {len(trends_df)} tracked skills show a statistically confirmed trend after correcting "
            f"for running that many tests at once.** {n_raw_significant} looked significant using a raw p-value "
            "alone (the classic multiple-comparisons trap -- testing 67 skills together means a few \"significant\" "
            "results are expected purely from chance, even if every individual test is done correctly). After "
            "Benjamini-Hochberg FDR correction, the same standard gap scoring uses elsewhere on this dashboard, "
            "0 survive at q < 0.05. The table below shows the strongest directional signals anyway, clearly "
            "labeled as exploratory -- not because they're proven trends, but because the underlying direction "
            "and effect size can still be informative even when the correction is (correctly) conservative about "
            "calling them \"significant.\""
        )
    else:
        st.success(f"{n_fdr_significant} of {len(trends_df)} tracked skills show a statistically confirmed trend after FDR correction (q < {SIGNIFICANCE_THRESHOLD}).")

    st.markdown('<p class="section-eyebrow">STRONGEST DIRECTIONAL SIGNALS (EXPLORATORY)</p>', unsafe_allow_html=True)
    st.caption(
        "Ranked by FDR-corrected q-value (smallest = strongest signal), regardless of whether it clears the "
        "significance bar. A skill only gets a green/red 'rising'/'falling' badge if it actually clears q < 0.05."
    )

    top_signals = trends_df.head(TOP_SIGNALS_SHOWN).copy()
    for _, row in top_signals.iterrows():
        confirmed = row["q_value"] < SIGNIFICANCE_THRESHOLD
        direction = "📈 rising" if row["slope"] > 0 else "📉 falling"
        badge = f"**{direction}, confirmed**" if confirmed else f"{direction} (not statistically confirmed)"
        with st.container(border=True):
            st.markdown(f"**{row['canonical_name']}** -- {badge}")
            sig_col1, sig_col2, sig_col3, sig_col4 = st.columns(4)
            sig_col1.metric("Slope", f"{row['slope']*100:+.2f} pts/wk")
            sig_col2.metric("First half", f"{row['first_half_rate']*100:.1f}%")
            sig_col3.metric("Second half", f"{row['second_half_rate']*100:.1f}%")
            sig_col4.metric("q-value", f"{row['q_value']:.3f}")

    st.markdown("---")
    st.subheader("Full detail -- all tracked skills")

    def format_for_display(df):
        # Manual string formatting instead of pandas' .style.format(): the
        # Styler accessor has an optional jinja2 dependency that can be
        # missing/misconfigured in some environments, and formatting the
        # values directly (rather than relying on a styling layer) is
        # simpler and just as readable, with one less moving part to break
        # a deployed app.
        out = df[["canonical_name", "trend_label", "first_half_rate", "second_half_rate", "p_value", "q_value"]].copy()
        out["first_half_rate"] = out["first_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["second_half_rate"] = out["second_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["p_value"] = out["p_value"].map(lambda v: f"{v:.4f}")
        out["q_value"] = out["q_value"].map(lambda v: f"{v:.4f}")
        return out.rename(columns={
            "canonical_name": "Skill", "trend_label": "Label", "first_half_rate": "First half",
            "second_half_rate": "Second half", "p_value": "p-value", "q_value": "q-value (FDR-corrected)",
        })

    st.dataframe(format_for_display(trends_df), hide_index=True, use_container_width=True)
    st.caption(
        "'Label' reflects the FDR-corrected q-value, not the raw p-value -- this is intentionally a stricter, "
        "more defensible bar, consistent with how gap scoring works elsewhere on this dashboard."
    )
