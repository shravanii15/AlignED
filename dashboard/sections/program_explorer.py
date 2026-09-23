"""sections/program_explorer.py -- pick a program AND a target role,
see its ranked, statistically significant skill-gap recommendations for
that specific combination, with Excel/PDF export.

Gap scoring and recommendations are now computed at two scopes: overall
market (every sampled posting) and per real role cluster (postings
mapped to one specific role, e.g. "Data Science / Data Engineering").
This page is where a visitor picks which of those they want to see --
"what does this program prepare me for, in general" vs. "what does this
program prepare me for, specifically for a Data Scientist role" are
genuinely different, independently-computed answers, not the same
numbers relabeled.
"""

import plotly.express as px
import streamlit as st

from services.database import run_query
from services.reports_excel import build_excel_report
from services.reports_pdf import build_pdf_report

OVERALL_MARKET_LABEL = "🌐 Overall market (all sampled postings)"


def render_program_explorer():
    st.title("📋 Program Explorer")
    st.markdown("Pick a program and a target role to see ranked, statistically significant skill gaps -- and what to do about them.")

    programs_df = run_query("SELECT program_id, university, program_name, tier FROM programs ORDER BY university")
    programs_df["label"] = programs_df["university"] + " -- " + programs_df["program_name"]
    selected_label = st.selectbox("Choose a program", programs_df["label"])
    selected = programs_df[programs_df["label"] == selected_label].iloc[0]
    program_id = int(selected["program_id"])

    # Only real, coherent role clusters are offered here -- "Mixed" and
    # "Near-duplicate" clusters were excluded from gap analysis entirely
    # (see compute_gap_scores.py), so there's no per-role data for them.
    clusters_df = run_query(
        """
        SELECT cluster_id, role_label FROM role_clusters
        WHERE role_label NOT LIKE 'Mixed%' AND role_label NOT LIKE 'Near-duplicate%'
        ORDER BY role_label
        """
    )
    role_options = [OVERALL_MARKET_LABEL] + list(clusters_df["role_label"])
    selected_role_label = st.selectbox(
        "Target role",
        role_options,
        help="Compare this program against the overall job-market sample, or narrow the comparison to postings for one specific role.",
    )

    if selected_role_label == OVERALL_MARKET_LABEL:
        cluster_id = None
        scope_display_name = "the overall market"
    else:
        cluster_id = int(clusters_df[clusters_df["role_label"] == selected_role_label]["cluster_id"].iloc[0])
        scope_display_name = selected_role_label

    course_count = run_query("SELECT COUNT(*) AS n FROM courses WHERE program_id = ?", (program_id,)).iloc[0]["n"]
    st.caption(f"Tier: {selected['tier']}  |  {course_count} real courses in this program  |  Target: {scope_display_name}")

    if cluster_id is None:
        recs_df = run_query(
            """
            SELECT r.skill_id, r.gap_value, r.trend_label, r.priority_score, r.priority_tier, r.rationale,
                   g.program_coverage_rate, g.market_demand_rate
            FROM recommendations r
            JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
            WHERE r.program_id = ? AND r.cluster_id IS NULL
            ORDER BY
                CASE r.priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                r.priority_score DESC
            """,
            (program_id,),
        )
    else:
        recs_df = run_query(
            """
            SELECT r.skill_id, r.gap_value, r.trend_label, r.priority_score, r.priority_tier, r.rationale,
                   g.program_coverage_rate, g.market_demand_rate
            FROM recommendations r
            JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
            WHERE r.program_id = ? AND r.cluster_id = ?
            ORDER BY
                CASE r.priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                r.priority_score DESC
            """,
            (program_id, cluster_id),
        )
    skills_df = run_query("SELECT skill_id, canonical_name FROM skills")
    recs_df = recs_df.merge(skills_df, on="skill_id", how="left")

    if recs_df.empty:
        st.warning(
            f"No statistically significant gaps were found for this program against {scope_display_name} "
            "(this can genuinely happen for very small programs with few courses, or a role cluster with fewer postings)."
        )
        return

    dl_col1, dl_col2 = st.columns(2)
    report_title_suffix = "" if cluster_id is None else f" (target role: {scope_display_name})"
    with dl_col1:
        # A real formatted Excel file, not a plain CSV -- CSV is just raw
        # comma-separated text, so it fundamentally cannot look
        # "professional" no matter how the columns are arranged (no
        # colors, no bold header, no cell shading). Excel can, while
        # still being just as sortable/filterable as a CSV would be.
        excel_bytes = build_excel_report(selected["university"], selected["program_name"] + report_title_suffix, course_count, recs_df)
        st.download_button(
            "⬇️ Download as Excel", data=excel_bytes,
            file_name=f"{selected['university']}_{selected['program_name']}_{scope_display_name}_recommendations.xlsx".replace(" ", "_"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with dl_col2:
        pdf_bytes = build_pdf_report(selected["university"], selected["program_name"] + report_title_suffix, course_count, recs_df)
        st.download_button(
            "⬇️ Download as PDF", data=pdf_bytes,
            file_name=f"{selected['university']}_{selected['program_name']}_{scope_display_name}_recommendations.pdf".replace(" ", "_"),
            mime="application/pdf",
        )

    tier_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for tier in ["high", "medium", "low"]:
        tier_df = recs_df[recs_df["priority_tier"] == tier]
        if tier_df.empty:
            continue
        st.subheader(f"{tier_colors[tier]} {tier.title()} priority")
        for _, row in tier_df.iterrows():
            trend_note = {"rising": "📈 rising demand", "falling": "📉 falling demand"}.get(row["trend_label"], "")
            with st.expander(f"{row['canonical_name']}  ({row['gap_value']*100:.0f} point gap)  {trend_note}"):
                st.write(row["rationale"])

    st.markdown("---")
    st.subheader("Gap size, visualized")
    chart_df = recs_df.sort_values("gap_value", ascending=True)
    fig = px.bar(
        chart_df, x="gap_value", y="canonical_name", orientation="h",
        color="priority_tier", color_discrete_map={"high": "#e15759", "medium": "#f1c232", "low": "#59a14f"},
        labels={"gap_value": f"Gap (demand within {scope_display_name} - program coverage)", "canonical_name": "Skill"},
    )
    fig.update_layout(xaxis_tickformat=".0%", height=max(300, len(chart_df) * 35))
    st.plotly_chart(fig, use_container_width=True)
