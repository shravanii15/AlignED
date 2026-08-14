"""sections/trends.py -- which tracked skills are statistically rising
or falling in demand (trend detection, not forecasting -- see the
Methodology page for why that distinction matters)."""

import plotly.express as px
import streamlit as st

from services.database import run_query


def render_trends():
    st.title("📈 Skill Demand Trends")
    st.markdown(
        """
        Based on ~124,000 real historical job postings, restricted to the
        6 weeks with a real, meaningful volume of data (see Methodology for
        why some weeks were excluded).
        """
    )

    trends_df = run_query(
        """
        SELECT t.trend_label, t.slope, t.p_value, t.first_half_rate, t.second_half_rate, s.canonical_name
        FROM skill_trends t JOIN skills s ON s.skill_id = t.skill_id
        ORDER BY t.slope DESC
        """
    )

    movers = trends_df[trends_df["trend_label"].isin(["rising", "falling"])].copy()
    if not movers.empty:
        st.subheader("Momentum: rising vs. falling skills")
        movers["slope_pct"] = movers["slope"] * 100
        movers_sorted = movers.sort_values("slope_pct")
        fig = px.bar(
            movers_sorted, x="slope_pct", y="canonical_name", orientation="h",
            color="trend_label", color_discrete_map={"rising": "#16A34A", "falling": "#DC2626"},
            labels={"slope_pct": "Change in demand rate, points per week", "canonical_name": "Skill", "trend_label": "Trend"},
        )
        fig.update_layout(height=max(350, len(movers_sorted) * 28), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Before vs. after: first half vs. second half of the window")
        before_after = movers.melt(
            id_vars=["canonical_name", "trend_label"],
            value_vars=["first_half_rate", "second_half_rate"],
            var_name="period", value_name="rate",
        )
        before_after["period"] = before_after["period"].map({"first_half_rate": "First half", "second_half_rate": "Second half"})
        fig2 = px.bar(
            before_after, x="canonical_name", y="rate", color="period", barmode="group",
            labels={"rate": "Demand rate", "canonical_name": "Skill", "period": "Period"},
            color_discrete_map={"First half": "#94A3B8", "Second half": "#2563EB"},
        )
        fig2.update_layout(yaxis_tickformat=".1%", height=400, xaxis_tickangle=-35)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("Full detail")

    def format_for_display(df):
        # Manual string formatting instead of pandas' .style.format(): the
        # Styler accessor has an optional jinja2 dependency that can be
        # missing/misconfigured in some environments, and formatting the
        # values directly (rather than relying on a styling layer) is
        # simpler and just as readable, with one less moving part to break
        # a deployed app.
        out = df[["canonical_name", "first_half_rate", "second_half_rate", "p_value"]].copy()
        out["first_half_rate"] = out["first_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["second_half_rate"] = out["second_half_rate"].map(lambda v: f"{v*100:.1f}%")
        out["p_value"] = out["p_value"].map(lambda v: f"{v:.4f}")
        return out.rename(columns={
            "canonical_name": "Skill", "first_half_rate": "First half",
            "second_half_rate": "Second half", "p_value": "p-value",
        })

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Rising")
        rising = trends_df[trends_df["trend_label"] == "rising"]
        st.dataframe(format_for_display(rising), hide_index=True, use_container_width=True)
    with col2:
        st.subheader("📉 Falling")
        falling = trends_df[trends_df["trend_label"] == "falling"]
        st.dataframe(format_for_display(falling), hide_index=True, use_container_width=True)

    stable_count = len(trends_df[trends_df["trend_label"] == "no clear trend"])
    st.caption(f"{stable_count} additional tracked skills showed no statistically significant trend over this window.")
