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
from utils.visuals import mini_bar, stat_tiles

SIGNIFICANCE_THRESHOLD = 0.05
TOP_SIGNALS_SHOWN = 10


def render_trends():
    page_header(
        "", "Rising and Falling Skills",
        "Which skills are being asked for more or less often in job postings. This covers only a short window, "
        "so treat it as an early hint, not a forecast.",
        art="trend", pills=("Job postings over time", "Early hints only"),
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
            f"No skill shows a trend we can be confident in yet. {n_raw_significant} of {len(trends_df)} looked like "
            "they were changing, but with this many skills checked at once some will look that way by chance, and "
            "none held up after correcting for that. The biggest movers are shown below as early hints."
        )
    else:
        st.success(f"{n_fdr_significant} of {len(trends_df)} skills show a trend that held up after correcting for multiple checks.")

    st.markdown('<p class="section-eyebrow">Biggest Movers (Early Hints)</p>', unsafe_allow_html=True)
    st.caption("Ordered by how consistent the change is. Only changes that held up under the stricter check are marked confirmed.")

    top_signals = trends_df.head(TOP_SIGNALS_SHOWN).copy()
    max_rate = max(float(top_signals[["first_half_rate", "second_half_rate"]].max().max()), 0.01)
    rising = int((top_signals["slope"] > 0).sum())
    stat_tiles([
        (str(len(trends_df)), "skills tracked"),
        (str(rising), "of the top movers rising"),
        (str(len(top_signals) - rising), "of the top movers falling"),
        (str(n_fdr_significant), "confirmed trends"),
    ])
    cols = st.columns(2, gap="medium")
    for i, (_, row) in enumerate(top_signals.iterrows()):
        confirmed = row["q_value"] < SIGNIFICANCE_THRESHOLD
        up = row["slope"] > 0
        chip = f'<span class="arrow-chip {"arrow-up" if up else "arrow-down"}">{"▲ Rising" if up else "▼ Falling"}</span>'
        status = "confirmed" if confirmed else "early hint"
        color = "#1F9D68" if up else "#D94A4A"
        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="vcard vcard-accent" style="border-top-color:{color}; margin-bottom:0.9rem;">
                    <p class="vcard-title">{row["canonical_name"]} &nbsp;{chip}</p>
                    <p class="vcard-sub">{status} &middot; {row["slope"]*100:+.2f} pts per week</p>
                    <div class="vcard-row"><span class="vcard-name">Earlier weeks</span>{mini_bar(row["first_half_rate"] / max_rate, "#98A2B3")}<span class="vcard-val">{row["first_half_rate"]*100:.1f}%</span></div>
                    <div class="vcard-row"><span class="vcard-name">Later weeks</span>{mini_bar(row["second_half_rate"] / max_rate, color)}<span class="vcard-val">{row["second_half_rate"]*100:.1f}%</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<p class="section-eyebrow">All Tracked Skills</p>', unsafe_allow_html=True)
    st.caption("Full table with the statistics (p-value and FDR-adjusted q-value).")

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
