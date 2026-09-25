"""sections/overview.py -- the Overview page.

Full redesign pass (not a patch): a light, editorial hero instead of a
filled blue banner; a live "THE SIGNAL" example -- the single largest
real gap in the database right now, pulled from the actual data rather
than hardcoded, so the homepage demonstrates the product instead of just
describing it; a command-center style analysis form; a lightweight text
list (not heavy cards) for the two secondary entry points; research-style
big-number statistics; and a compact footer with author credit."""

import streamlit as st

from services.database import run_query
from utils.nav import (
    GROUP_ANALYZE, GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_PERSONALIZE,
    PAGE_COMPARE, PAGE_HEATMAP, PAGE_METHODOLOGY, PAGE_BUILD_PROFILE,
    jump_to, jump_to_program_explorer,
)
from sections.program_explorer import OVERALL_MARKET_LABEL


def render_overview():
    # ---- Hero ----
    st.markdown('<p class="hero-kicker">Curriculum &times; Labor-Market Intelligence</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-title">Where do graduate computing curricula diverge from the skills appearing '
        'in the job market?</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="hero-subtitle">AlignED compares real course descriptions with demand observed in a '
        'sampled set of real job postings, using a common skill taxonomy and statistical testing -- not guesses.</p>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ---- THE SIGNAL: a live example, not a mockup. Pulls the single
    # largest real gap currently in the database (overall-market scope)
    # so the homepage demonstrates the analysis instead of describing it.
    signal_row = run_query(
        """
        SELECT p.university, p.program_name, s.canonical_name AS skill_name,
               g.program_coverage_rate, g.market_demand_rate, g.gap_value, g.q_value
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        JOIN programs p ON p.program_id = r.program_id
        JOIN skills s ON s.skill_id = r.skill_id
        WHERE r.cluster_id IS NULL
        ORDER BY g.gap_value DESC
        LIMIT 1
        """
    )
    if not signal_row.empty:
        sig = signal_row.iloc[0]
        cov_pct = sig["program_coverage_rate"] * 100
        dem_pct = sig["market_demand_rate"] * 100
        max_pct = max(cov_pct, dem_pct, 1)
        st.markdown('<p class="section-eyebrow">The Signal -- a Real Example, Live From the Database</p>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f'<p class="signal-eyebrow">{sig["university"]} -- {sig["program_name"]}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="signal-skill-name">{sig["skill_name"]}</p>', unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="signal-row">
                    <div class="signal-label">Curriculum</div>
                    <div class="signal-track"><div class="signal-fill signal-fill-coverage" style="width:{cov_pct/max_pct*100:.1f}%"></div></div>
                    <div class="signal-value">{cov_pct:.1f}%</div>
                </div>
                <div class="signal-row">
                    <div class="signal-label">Job market</div>
                    <div class="signal-track"><div class="signal-fill signal-fill-market" style="width:{dem_pct/max_pct*100:.1f}%"></div></div>
                    <div class="signal-value">{dem_pct:.1f}%</div>
                </div>
                <div class="signal-gap-line">
                    <span class="signal-gap-value">+{sig['gap_value']*100:.1f} percentage-point gap</span>
                    &nbsp;&middot;&nbsp; q &lt; {max(sig['q_value'], 0.0001):.4f}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Explore this analysis →", key="signal_explore_btn",
                on_click=jump_to_program_explorer, args=(f"{sig['university']} -- {sig['program_name']}", OVERALL_MARKET_LABEL),
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Command center: the primary action ----
    st.markdown('<p class="section-eyebrow">Explore a Curriculum</p>', unsafe_allow_html=True)
    with st.container(border=True):
        programs_df = run_query("SELECT program_id, university, program_name FROM programs ORDER BY university")
        programs_df["label"] = programs_df["university"] + " -- " + programs_df["program_name"]
        clusters_df = run_query(
            """
            SELECT cluster_id, role_label FROM role_clusters
            WHERE role_label NOT LIKE 'Mixed%' AND role_label NOT LIKE 'Near-duplicate%'
            ORDER BY role_label
            """
        )
        role_options = [OVERALL_MARKET_LABEL] + list(clusters_df["role_label"])

        form_col1, form_col2 = st.columns(2)
        with form_col1:
            program_choice = st.selectbox("Program", programs_df["label"], key="home_program_choice")
        with form_col2:
            role_choice = st.selectbox("Compared with", role_options, key="home_role_choice")
        st.button(
            "Analyze program →", key="home_analyze_btn", type="primary", use_container_width=True,
            on_click=jump_to_program_explorer, args=(program_choice, role_choice),
        )
        st.caption("40+ skills compared per program &middot; statistical gap testing &middot; evidence for every result", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Lightweight secondary entry points (text list, not cards) ----
    st.markdown('<p class="section-eyebrow">What Else Do You Want to Explore?</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="explore-item">
            <div class="explore-item-title">Compare programs</div>
            <div class="explore-item-desc">See 2-3 programs' top overall-market gaps side by side, against the same reference sample.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button("Compare programs →", key="explore_compare_btn", on_click=jump_to, args=(GROUP_ANALYZE, PAGE_COMPARE))

    st.markdown(
        """
        <div class="explore-item">
            <div class="explore-item-title">Analyze my profile</div>
            <div class="explore-item-desc">Paste your resume or skills and see which real job roles fit you best, and what to learn next.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button("Build my profile →", key="explore_profile_btn", on_click=jump_to, args=(GROUP_PERSONALIZE, PAGE_BUILD_PROFILE))

    st.markdown(
        """
        <div class="explore-item">
            <div class="explore-item-title">Explore the market</div>
            <div class="explore-item-desc">Browse skill coverage, demand momentum, and how real job postings group into role families.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button("Explore data →", key="explore_market_btn", on_click=jump_to, args=(GROUP_EXPLORE, PAGE_HEATMAP))

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- THE DATASET: research-style big numbers, not sidebar-sized text ----
    programs = run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"]
    courses = run_query("SELECT COUNT(*) AS n FROM courses").iloc[0]["n"]
    postings = run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"]
    gaps = run_query("SELECT COUNT(*) AS n FROM gap_scores WHERE cluster_id IS NULL").iloc[0]["n"]

    st.markdown('<p class="section-eyebrow">The Dataset</p>', unsafe_allow_html=True)
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stats = [
        (stat_col1, f"{programs}", "Programs"),
        (stat_col2, f"{courses:,}", "Course Descriptions"),
        (stat_col3, f"{postings:,}", "Job Postings"),
        (stat_col4, f"{gaps}", "Significant Gap Signals"),
    ]
    for col, number, label in stats:
        with col:
            st.markdown(f'<div class="stat-block"><div class="stat-number">{number}</div><div class="stat-label">{label}</div></div>', unsafe_allow_html=True)
    st.caption(
        "Analysis snapshot &middot; O\\*NET-derived skill taxonomy &middot; category-balanced job-posting sample "
        "(see Methodology for what that means)",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ---- How it works, compact ----
    st.markdown('<p class="section-eyebrow">How It Works</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="howitworks-strip">
            <div class="howitworks-step">Course Data</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Skill Extraction</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">O&#42;NET Normalization</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Market Comparison</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Statistical Testing</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Gap Evidence</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "An AI extraction method was benchmarked against a classical keyword baseline on a 104-item hand-labeled "
        "test set (AI won on F1, 0.400 vs. 0.364) -- full reasoning on the Methodology page."
    )

    st.markdown("---")

    # ---- Footer ----
    footer_col1, footer_col2 = st.columns([3, 1])
    with footer_col1:
        st.markdown(
            '<p class="site-footer"><b>Built by Shravani Kulkarni</b> &middot; MS Data Science, Analytics &amp; '
            'Engineering<br>Python &middot; SQLite &middot; Streamlit &middot; Plotly</p>',
            unsafe_allow_html=True,
        )
    with footer_col2:
        st.markdown(
            '<p class="site-footer" style="text-align:right;">'
            '<a href="https://github.com/shravanii15/AlignED" target="_blank">GitHub ↗</a></p>',
            unsafe_allow_html=True,
        )
        st.button("Methodology →", key="footer_methodology_btn", on_click=jump_to, args=(GROUP_METHODOLOGY, PAGE_METHODOLOGY))
