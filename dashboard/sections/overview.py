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
    # Example program for the hero: the full-size program whose top gaps
    # show the most visible course coverage, so the bars are not all empty.
    example = run_query(
        f"""
        SELECT r.program_id, p.university, p.program_name, s.canonical_name AS skill_name,
               g.program_coverage_rate AS cov, g.market_demand_rate AS dem, g.gap_value,
               (SELECT COUNT(*) FROM gap_scores x WHERE x.program_id = r.program_id AND x.cluster_id IS NULL) AS n_gaps
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        JOIN programs p ON p.program_id = r.program_id
        JOIN skills s ON s.skill_id = r.skill_id
        WHERE r.cluster_id IS NULL
          AND (SELECT COUNT(*) FROM courses c WHERE c.program_id = r.program_id) >= {EXAMPLE_MIN_COURSES}
        ORDER BY r.program_id, g.gap_value DESC
        """
    )
    card = ""
    if not example.empty:
        best_pid, best_total = None, -1.0
        for pid, grp in example.groupby("program_id"):
            total = grp.head(5)["cov"].sum()
            if total > best_total:
                best_pid, best_total = pid, total
        ex = example[example["program_id"] == best_pid].head(5)
        MENTIONED_AT = 0.05  # a skill counts as "mentioned" when 5%+ of courses name it
        marks = []
        n_ok = 0
        for _, r in ex.iterrows():
            kind = "ok" if r["cov"] >= MENTIONED_AT else ("warn" if r["cov"] > 0 else "no")
            n_ok += kind == "ok"
            marks.append(f'<span class="ad-skill ad-{kind}">{r["skill_name"]}</span>')
        first = ex.iloc[0]
        skill_line = ", ".join(marks[:-1]) + (" and " + marks[-1] if len(marks) > 1 else "")
        card = f"""
        <div class="hero-card ad-card">
            <p class="ad-kicker">Example job posting</p>
            <p class="ad-title">Software Engineer</p>
            <p class="ad-body">We are hiring an engineer to build and ship reliable software.
            Day to day you will work with {skill_line}. You collaborate with
            data and product teams and own features from idea to launch.</p>
            <div class="ad-legend">
                <span><i class="ad-key ad-key-ok"></i>Taught in courses</span>
                <span><i class="ad-key ad-key-warn"></i>Barely mentioned</span>
                <span><i class="ad-key ad-key-no"></i>Missing</span>
            </div>
            <p class="ad-score"><b>{n_ok} of {len(ex)}</b> skills in this ad appear in the courses of<br>
            <span>{first["university"]}, {first["program_name"]}</span></p>
        </div>"""
    st.markdown(
        f"""
        <div class="hero-panel">
            <div class="hero-left">
                <p class="hero-wordmark">Align<span class="wm-ed">ED</span></p>
                <p class="hero-motto">Align your education with the job market.</p>
                <p class="hero-headline">Is your degree missing the skills employers want?</p>
                <p class="hero-tagline">Paste a job or pick a program. We show the missing skills, ranked, and courses that teach them.</p>
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
