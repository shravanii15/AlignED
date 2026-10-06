"""sections/overview.py: the Home page.

Built around the two questions a visitor actually arrives with, not
around the analysis behind them:

  1. "I found a job: do I match it, what do I learn first?"
  2. "I am choosing a program: does it teach what employers want?"

Each gets one card with its own action. A real example from the data
sits underneath, and the deeper data pages are one small row of links.
"""

import streamlit as st

from services.database import run_query
from sections.program_explorer import OVERALL_MARKET_LABEL
from utils.formatting import evidence_strength, program_label
from utils.nav import (
    GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_PERSONALIZE,
    PAGE_BUILD_PROFILE, PAGE_HEATMAP, PAGE_METHODOLOGY, PAGE_ROLE_GROUPS, PAGE_TRENDS,
    jump_to, jump_to_program_explorer, start_job_match,
)

# Skill-gap example is only drawn from programs with enough courses that
# a missing skill is not just a small-sample artifact.
EXAMPLE_MIN_COURSES = 30


def render_overview():
    programs_total = int(run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"])
    courses_total = int(run_query("SELECT COUNT(*) AS n FROM courses").iloc[0]["n"])
    signal_row = run_query(
        f"""
        SELECT p.university, p.program_name, s.canonical_name AS skill_name,
               g.program_coverage_rate, g.market_demand_rate, g.gap_value, g.q_value
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        JOIN programs p ON p.program_id = r.program_id
        JOIN skills s ON s.skill_id = r.skill_id
        WHERE r.cluster_id IS NULL
          AND g.program_coverage_rate > 0
          AND (SELECT COUNT(*) FROM courses c WHERE c.program_id = r.program_id) >= {EXAMPLE_MIN_COURSES}
        ORDER BY g.gap_value DESC
        LIMIT 1
        """
    )
    if not signal_row.empty:
        h = signal_row.iloc[0]
        h_cov, h_dem = h["program_coverage_rate"] * 100, h["market_demand_rate"] * 100
        h_max = max(h_cov, h_dem, 1)
        card = f"""
        <div class="hero-card">
            <p class="hero-card-eyebrow">What an answer looks like</p>
            <p class="hero-card-skill">{h["skill_name"]}</p>
            <div class="hero-card-row"><span>Courses</span><div class="hero-card-track"><div class="hero-card-fill hero-card-fill-c" style="width:{max(h_cov/h_max*100, 2):.0f}%"></div></div><b>{h_cov:.0f}%</b></div>
            <div class="hero-card-row"><span>Job postings</span><div class="hero-card-track"><div class="hero-card-fill hero-card-fill-m" style="width:{h_dem/h_max*100:.0f}%"></div></div><b>{h_dem:.0f}%</b></div>
            <p class="hero-card-gap">{h["gap_value"]*100:.0f}-point gap</p>
            <p class="hero-card-src">{h["university"]}, {h["program_name"]}</p>
        </div>"""
    else:
        card = ""
    st.markdown(
        f"""
        <div class="hero-panel">
            <div class="hero-left">
                <p class="hero-wordmark">AlignED</p>
                <p class="hero-tagline">Does a graduate program teach what employers ask for? Find out, skill by skill, and get a plan for what to learn next.</p>
                <div class="hero-pills">
                    <span>{programs_total} programs</span><span>{courses_total:,} courses</span><span>1,660 job postings</span>
                </div>
            </div>
            {card}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Two paths ----
    programs_df = run_query(
        "SELECT p.program_id, p.university, p.program_name, "
        "(SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses, "
        "(SELECT COUNT(*) FROM recommendations r WHERE r.program_id = p.program_id AND r.cluster_id IS NULL) AS n_gaps "
        "FROM programs p ORDER BY p.university"
    )
    programs_df["label"] = [program_label(u, p) for u, p in zip(programs_df["university"], programs_df["program_name"])]
    # Default to the full-size program with the most gaps, so the first
    # click shows real results instead of an "only 5 courses" empty state.
    eligible = programs_df[programs_df["n_courses"] >= EXAMPLE_MIN_COURSES]
    default_idx = int(eligible["n_gaps"].idxmax())
    clusters_df = run_query(
        """
        SELECT cluster_id, role_label FROM role_clusters
        WHERE role_label NOT LIKE 'Mixed%' AND role_label NOT LIKE 'Near-duplicate%'
        ORDER BY role_label
        """
    )
    role_options = [OVERALL_MARKET_LABEL] + list(clusters_df["role_label"])

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown('<p class="path-title">I found a job I want</p>', unsafe_allow_html=True)
            st.markdown('<p class="path-desc">Paste the posting. See which skills it asks for, which you already have, and what to learn first.</p>', unsafe_allow_html=True)
            job_text = st.text_area(
                "Job posting", key="home_job_text", height=122,
                placeholder="Paste a job description here",
            )
            st.button(
                "Check how I match →", key="home_match_btn", type="primary", use_container_width=True,
                on_click=start_job_match, args=(job_text,),
            )
    with right:
        with st.container(border=True):
            st.markdown('<p class="path-title">I am choosing a program</p>', unsafe_allow_html=True)
            st.markdown('<p class="path-desc">See which skills employers want that a program\'s courses do not mention.</p>', unsafe_allow_html=True)
            program_choice = st.selectbox("Program", programs_df["label"], index=default_idx, key="home_program_choice")
            role_choice = st.selectbox("Compared with jobs in", role_options, key="home_role_choice")
            st.button(
                "Show me the gaps →", key="home_analyze_btn", type="primary", use_container_width=True,
                on_click=jump_to_program_explorer, args=(program_choice, role_choice),
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- A real example, pulled live ----
    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Deeper pages, one quiet row ----
    st.markdown('<p class="section-eyebrow">Dig Deeper</p>', unsafe_allow_html=True)
    more0, more1, more2, more3, more4 = st.columns(5)
    more0.button("Which jobs fit me", key="more_fit_btn", use_container_width=True, on_click=jump_to, args=(GROUP_PERSONALIZE, PAGE_BUILD_PROFILE))
    more1.button("Skills by program", key="more_heatmap_btn", use_container_width=True, on_click=jump_to, args=(GROUP_EXPLORE, PAGE_HEATMAP))
    more2.button("Rising and falling skills", key="more_trends_btn", use_container_width=True, on_click=jump_to, args=(GROUP_EXPLORE, PAGE_TRENDS))
    more3.button("Job families", key="more_families_btn", use_container_width=True, on_click=jump_to, args=(GROUP_EXPLORE, PAGE_ROLE_GROUPS))
    more4.button("How it works", key="more_method_btn", use_container_width=True, on_click=jump_to, args=(GROUP_METHODOLOGY, PAGE_METHODOLOGY))

    st.markdown("---")
    st.markdown(
        '<p class="site-footer"><b>Built by Shravani Kulkarni</b> &middot; MS Data Science &middot; '
        '<a href="https://github.com/shravanii15/AlignED" target="_blank">GitHub ↗</a></p>',
        unsafe_allow_html=True,
    )
