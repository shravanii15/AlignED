"""sections/program_explorer.py -- pick a program AND a target role,
see its ranked, statistically significant skill-gap recommendations for
that specific combination, with Excel/PDF export and a per-skill
evidence drill-down.

Gap scoring and recommendations are now computed at two scopes: overall
market (every sampled posting) and per real role cluster (postings
mapped to one specific role, e.g. "Data Science / Data Engineering").
This page is where a visitor picks which of those they want to see --
"what does this program prepare me for, in general" vs. "what does this
program prepare me for, specifically for a Data Scientist role" are
genuinely different, independently-computed answers, not the same
numbers relabeled.

Every recommendation shown here can be expanded into its underlying
evidence (raw counts, p-value, FDR-adjusted q-value, and the exact
gap+trend math behind its priority ranking) -- the point being that
nothing on this page should require the visitor to just trust a number;
they can always see exactly where it came from.
"""

import plotly.express as px
import streamlit as st

from services.database import run_query
from services.reports_excel import build_excel_report
from services.reports_pdf import build_pdf_report
from utils.layout import page_header
from utils.nav import EXPLORER_PROGRAM_KEY, EXPLORER_ROLE_KEY

OVERALL_MARKET_LABEL = "🌐 Overall market (all sampled postings)"
RISING_BOOST = 1.5     # kept in sync with scripts/gap_analysis/generate_recommendations.py
FALLING_PENALTY = 0.7  # kept in sync with scripts/gap_analysis/generate_recommendations.py


def render_program_explorer():
    page_header("📋", "Program Explorer", "Pick a program and a target role to see ranked, statistically significant skill gaps -- and what to do about them.")
    st.caption(
        "Skill taxonomy: U.S. Department of Labor O\\*NET -- a real, external standard, not an invented list. "
        "\"Coverage\" and \"demand\" below are text-mention rates in course descriptions and job postings, not "
        "measures of instructional depth or job requirement strength -- see Methodology for the full reasoning."
    )

    programs_df = run_query("SELECT program_id, university, program_name, tier FROM programs ORDER BY university")
    programs_df["label"] = programs_df["university"] + " -- " + programs_df["program_name"]

    # Bound to a session-state key (rather than a bare st.selectbox) so the
    # Overview page's "Start an analysis" form can pre-select a program
    # before jumping here -- see utils/nav.py's jump_to_program_explorer().
    if EXPLORER_PROGRAM_KEY not in st.session_state or st.session_state[EXPLORER_PROGRAM_KEY] not in list(programs_df["label"]):
        st.session_state[EXPLORER_PROGRAM_KEY] = programs_df["label"].iloc[0]
    selected_label = st.selectbox("Choose a program", programs_df["label"], key=EXPLORER_PROGRAM_KEY)
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
    if EXPLORER_ROLE_KEY not in st.session_state or st.session_state[EXPLORER_ROLE_KEY] not in role_options:
        st.session_state[EXPLORER_ROLE_KEY] = OVERALL_MARKET_LABEL
    selected_role_label = st.selectbox(
        "Target role",
        role_options,
        key=EXPLORER_ROLE_KEY,
        help="Compare this program against the overall job-market sample, or narrow the comparison to postings for one specific role.",
    )

    if selected_role_label == OVERALL_MARKET_LABEL:
        cluster_id = None
        scope_display_name = "the overall market"
        scope_total_postings = run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"]
    else:
        cluster_id = int(clusters_df[clusters_df["role_label"] == selected_role_label]["cluster_id"].iloc[0])
        scope_display_name = selected_role_label
        scope_total_postings = run_query(
            "SELECT COUNT(*) AS n FROM posting_cluster_map WHERE cluster_id = ?", (cluster_id,)
        ).iloc[0]["n"]

    course_count = run_query("SELECT COUNT(*) AS n FROM courses WHERE program_id = ?", (program_id,)).iloc[0]["n"]
    st.caption(f"Tier: {selected['tier']}  |  {course_count} real courses in this program  |  Target: {scope_display_name}  |  {scope_total_postings} postings in this scope")

    rec_query = """
        SELECT r.skill_id, r.gap_value, r.trend_label, r.priority_score, r.priority_tier, r.rationale,
               g.program_coverage_rate, g.market_demand_rate, g.p_value, g.q_value, g.period
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        WHERE r.program_id = ? AND r.cluster_id IS {}
        ORDER BY
            CASE r.priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            r.priority_score DESC
    """
    if cluster_id is None:
        recs_df = run_query(rec_query.format("NULL"), (program_id,))
    else:
        recs_df = run_query(rec_query.format("?"), (program_id, cluster_id))
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
        pdf_bytes = build_pdf_report(
            selected["university"], selected["program_name"] + report_title_suffix, course_count, recs_df,
            scope_display_name=scope_display_name, scope_total_postings=scope_total_postings,
        )
        st.download_button(
            "⬇️ Download as PDF", data=pdf_bytes,
            file_name=f"{selected['university']}_{selected['program_name']}_{scope_display_name}_recommendations.pdf".replace(" ", "_"),
            mime="application/pdf",
        )

    st.markdown("---")

    # Alignment snapshot: real counts only, deliberately NOT a single
    # invented "alignment %" score. This project's whole stance is that
    # gap scoring is a text-coverage signal, not a certified measure of
    # curriculum quality -- collapsing that into one made-up percentage
    # would undercut the honesty the rest of the dashboard argues for. So
    # this snapshot shows what was actually measured: how much data went
    # in, and how many statistically significant gaps came out.
    tier_counts = recs_df["priority_tier"].value_counts()
    st.markdown('<p class="section-eyebrow">ALIGNMENT SNAPSHOT</p>', unsafe_allow_html=True)
    snap_col1, snap_col2, snap_col3, snap_col4 = st.columns(4)
    snap_col1.metric("Courses analyzed", course_count)
    snap_col2.metric("Postings in scope", scope_total_postings)
    snap_col3.metric("Significant gaps", len(recs_df))
    snap_col4.metric("Largest-gap items", int(tier_counts.get("high", 0)))
    st.caption(
        f"Against {scope_display_name}, {len(recs_df)} skills showed a statistically significant coverage gap "
        f"(after FDR correction) out of the skills this program's courses and this scope's postings both touched on. "
        "A program can genuinely cover many more skills than appear below -- only significant gaps are listed."
    )

    st.markdown("---")
    tier_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    # Reworded from "High/Medium/Low priority" (which reads as an
    # externally validated importance ranking) to "largest observed
    # gaps" -- the tiers are just a rank-based cut (top 3 / next 4 /
    # rest) of gap size adjusted by demand trend, not a claim that a
    # 'high' item objectively matters more in some absolute sense.
    tier_section_titles = {
        "high": "Largest observed gaps",
        "medium": "Notable gaps",
        "low": "Smaller, still-significant gaps",
    }
    st.caption(
        "Grouped by priority signal (gap size, adjusted for demand trend) -- a ranking within THIS program+scope's "
        "own results, not an externally validated importance score. See each item's evidence for the exact math."
    )
    for tier in ["high", "medium", "low"]:
        tier_df = recs_df[recs_df["priority_tier"] == tier]
        if tier_df.empty:
            continue
        st.subheader(f"{tier_colors[tier]} {tier_section_titles[tier]}")
        for _, row in tier_df.iterrows():
            trend_note = {"rising": "📈 rising demand", "falling": "📉 falling demand"}.get(row["trend_label"], "")
            cov_pct = row["program_coverage_rate"] * 100
            dem_pct = row["market_demand_rate"] * 100
            max_pct = max(cov_pct, dem_pct, 1)

            with st.container(border=True):
                st.markdown(f"**{row['canonical_name']}**  &nbsp; `{row['gap_value']*100:.0f} point gap`  {trend_note}", unsafe_allow_html=True)
                st.write(row["rationale"])

                # Gap visualization: curriculum coverage vs. market demand,
                # side by side -- makes the gap immediately visible instead
                # of requiring the visitor to compare two percentages by eye.
                st.markdown(
                    f"""
                    <div class="gap-compare">
                        <div class="gap-compare-row">
                            <div class="gap-compare-label">Curriculum</div>
                            <div class="gap-bar-track"><div class="gap-bar-fill gap-bar-curriculum" style="width:{cov_pct/max_pct*100:.1f}%"></div></div>
                            <div class="gap-bar-value">{cov_pct:.1f}%</div>
                        </div>
                        <div class="gap-compare-row">
                            <div class="gap-compare-label">Job market</div>
                            <div class="gap-bar-track"><div class="gap-bar-fill gap-bar-market" style="width:{dem_pct/max_pct*100:.1f}%"></div></div>
                            <div class="gap-bar-value">{dem_pct:.1f}%</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Evidence drill-down, as a compact structured card instead
                # of a wall of markdown bullets -- exact counts, raw and
                # FDR-corrected significance, and the priority-score math,
                # so nothing here has to just be taken on faith.
                x_courses = round(row["program_coverage_rate"] * course_count)
                x_postings = round(row["market_demand_rate"] * scope_total_postings)
                trend_desc = {
                    "rising": f"x {RISING_BOOST} (rising demand)",
                    "falling": f"x {FALLING_PENALTY} (falling demand)",
                }.get(row["trend_label"], "x 1.0 (no clear trend)")

                with st.expander("Why am I seeing this? (evidence)"):
                    st.markdown(
                        f"""
                        | | |
                        |---|---|
                        | Curriculum coverage | **{x_courses} of {course_count}** courses ({cov_pct:.1f}%) |
                        | Market demand | **{x_postings} of {scope_total_postings}** postings ({dem_pct:.1f}%), scope: {scope_display_name} |
                        | Gap | **{row['gap_value']*100:.1f} percentage points** |
                        | Raw p-value | `{row['p_value']:.4f}` |
                        | FDR-adjusted q-value | `{row['q_value']:.4f}` (this is what decides significance) |
                        | Data period | {row['period']} |
                        | Method | Two-proportion z-test + Benjamini-Hochberg FDR correction |
                        """
                    )
                    st.caption(
                        f"Priority signal = gap ({row['gap_value']*100:.1f} pts) x trend modifier ({trend_desc}) "
                        f"= {row['priority_score']*100:.1f}. Used only to rank results within this program+scope -- "
                        f"not a validated measure of real-world importance."
                    )

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
