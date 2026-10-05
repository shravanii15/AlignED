"""sections/trends.py: observed demand momentum, exploratory signals about
which tracked skills' demand might be rising or falling.

Trend tests get the same Benjamini-Hochberg FDR correction as gap scoring
(scripts/gap_analysis/compute_skill_trends.py). 9 skills look significant
at raw p < 0.05, but 0 survive correction at q < 0.05, so this page shows
the strongest directional signals labeled as exploratory, with both the
raw p-value and the corrected q-value visible."""

import streamlit as st

from services.database import run_query
from utils.layout import page_header

SIGNIFICANCE_THRESHOLD = 0.05
TOP_SIGNALS_SHOWN = 10


def render_trends():
    page_header(
        "", "Observed Demand Momentum",
        "Exploratory signals from about 124,000 historical postings, limited to the 6 weeks with enough "
        "volume. These are early signals over a short window, not confirmed trends or forecasts.",
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
            f"None of the {len(trends_df)} tracked skills show a confirmed trend after correcting for multiple "
            f"tests. {n_raw_significant} looked significant on a raw p-value, but with this many simultaneous "
            "tests a few false positives are expected. After Benjamini-Hochberg correction, the same standard "
            "used for gap scoring, none survive at q < 0.05. The strongest directional signals are shown "
            "below as exploratory."
        )
    else:
        st.success(f"{n_fdr_significant} of {len(trends_df)} tracked skills show a confirmed trend after FDR correction (q < {SIGNIFICANCE_THRESHOLD}).")

    st.markdown('<p class="section-eyebrow">Strongest Directional Signals (Exploratory)</p>', unsafe_allow_html=True)
    st.caption("Ranked by q-value, smallest first. A skill is labeled confirmed only if q < 0.05.")

    top_signals = trends_df.head(TOP_SIGNALS_SHOWN).copy()
    for _, row in top_signals.iterrows():
        confirmed = row["q_value"] < SIGNIFICANCE_THRESHOLD
        direction = "Rising" if row["slope"] > 0 else "Falling"
        badge = f"{direction}, confirmed" if confirmed else f"{direction}, not confirmed"
        with st.container(border=True):
            st.markdown(f'<p class="signal-skill-name" style="font-size:1.15rem !important; margin-bottom:0.2rem;">{row["canonical_name"]}</p>', unsafe_allow_html=True)
            st.caption(badge)
            sig_col1, sig_col2, sig_col3, sig_col4 = st.columns(4)
            sig_col1.metric("Slope", f"{row['slope']*100:+.2f} pts/wk")
            sig_col2.metric("First half", f"{row['first_half_rate']*100:.1f}%")
            sig_col3.metric("Second half", f"{row['second_half_rate']*100:.1f}%")
            sig_col4.metric("q-value", f"{row['q_value']:.3f}")

    st.markdown('<p class="section-eyebrow">All Tracked Skills</p>', unsafe_allow_html=True)

    def format_for_display(df):
        # Formatted as strings directly, avoiding pandas' Styler, which
        # has an optional jinja2 dependency that can be missing in
        # deployed environments.
        out = df[["canonical_name", "trend_label", "first_half_rate", "second_half_rate", "p_value", "q_value"]].copy()
        out["first_half_rate"] = out["first_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["second_half_rate"] = out["second_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["p_value"] = out["p_value"].map(lambda v: f"{v:.4f}")
        out["q_value"] = out["q_value"].map(lambda v: f"{v:.4f}")
        return out.rename(columns={
            "canonical_name": "Skill", "trend_label": "Label", "first_half_rate": "First half",
            "second_half_rate": "Second half", "p_value": "p-value", "q_value": "q-value (FDR)",
        })

    st.dataframe(format_for_display(trends_df), hide_index=True, use_container_width=True)
    st.caption("Labels use the FDR-corrected q-value, not the raw p-value.")
