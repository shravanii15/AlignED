"""sections/overview.py -- the Overview page. Redesigned (Sprint 6) around
a "start an analysis" form as the primary action, not headline metrics --
a visitor should be able to use the product from the first screen, rather
than scrolling past a wall of numbers to find it. Metrics, the "how it
works" strip, and two secondary entry points (profile / market) come after."""

import streamlit as st

from services.database import run_query
from utils.nav import (
    GROUP_ANALYZE, GROUP_EXPLORE, GROUP_PERSONALIZE,
    PAGE_HEATMAP, PAGE_PROGRAM_EXPLORER, PAGE_BUILD_PROFILE,
    jump_to, jump_to_program_explorer,
)
from sections.program_explorer import OVERALL_MARKET_LABEL


def render_overview():
    st.markdown(
        """
        <div class="aligned-banner aligned-banner-compact">
            <h1>🎓 AlignED</h1>
            <p class="aligned-banner-kicker">Curriculum &times; Labor-Market Intelligence</p>
            <p>Do graduate programs teach the skills employers are asking for? AlignED compares real
            course descriptions with observed job-market demand using statistical testing, skill
            normalization, and labor-market evidence.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Start an analysis: the primary action, above the fold ----
    st.markdown('<p class="section-eyebrow">START AN ANALYSIS</p>', unsafe_allow_html=True)
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
            role_choice = st.selectbox("Target role", role_options, key="home_role_choice")
        st.button(
            "Analyze →", key="home_analyze_btn", type="primary", use_container_width=True,
            on_click=jump_to_program_explorer, args=(program_choice, role_choice),
        )
        st.caption("See ranked, statistically significant skill gaps for this program and role, with an evidence drill-down for every result.")

    # ---- Secondary entry points ----
    card_col1, card_col2 = st.columns(2)
    with card_col1:
        with st.container(border=True):
            st.markdown(
                """
                <div class="action-card-icon">👤</div>
                <div class="action-card-title">Analyze My Profile</div>
                <div class="action-card-desc">Paste your resume or skills, and see which real job roles
                fit you best, and what to learn next -- plus a downloadable report.</div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Build my profile →", key="card_personalize", use_container_width=True,
                on_click=jump_to, args=(GROUP_PERSONALIZE, PAGE_BUILD_PROFILE),
            )
    with card_col2:
        with st.container(border=True):
            st.markdown(
                """
                <div class="action-card-icon">📊</div>
                <div class="action-card-title">Explore the Market</div>
                <div class="action-card-desc">Browse skill coverage, demand trends, and how real job
                postings group into role families -- the raw data behind every claim.</div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Explore data →", key="card_explore", use_container_width=True,
                on_click=jump_to, args=(GROUP_EXPLORE, PAGE_HEATMAP),
            )

    st.markdown("---")

    # ---- Dataset stats (condensed, secondary) + emphasized results ----
    programs = run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"]
    courses = run_query("SELECT COUNT(*) AS n FROM courses").iloc[0]["n"]
    postings = run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"]
    # Overall-market scope only (cluster_id IS NULL) -- gap_scores and
    # recommendations also contain per-role-cluster rows now (see Program
    # Explorer's target-role selector), and counting those in here too
    # would inflate these headline numbers with rows from 9 different
    # scopes at once, which isn't what "significant gaps found" should mean.
    gaps = run_query("SELECT COUNT(*) AS n FROM gap_scores WHERE cluster_id IS NULL").iloc[0]["n"]
    recs = run_query("SELECT COUNT(*) AS n FROM recommendations WHERE cluster_id IS NULL").iloc[0]["n"]

    st.markdown('<p class="section-eyebrow">ANALYSIS SNAPSHOT</p>', unsafe_allow_html=True)
    st.caption(f"{programs} programs · {courses:,} courses · {postings:,} job postings (overall-market scope; Program Explorer lets you narrow to a specific target role)")

    result_col1, result_col2 = st.columns(2)
    result_col1.metric("Statistically significant gaps", gaps)
    result_col2.metric("Evidence-ranked recommendations", recs)
    st.markdown(
        '📚 **Skill taxonomy: U.S. Department of Labor O\\*NET** -- every skill on this dashboard comes from '
        "this real, external, publicly maintained standard. Nothing here is an invented list."
    )

    st.markdown("---")

    # ---- How it works, compact ----
    st.markdown('<p class="section-eyebrow">HOW IT WORKS</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="howitworks-strip">
            <div class="howitworks-step">Curricula</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Skill extraction</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">O&#42;NET normalization</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Market comparison</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Statistical gap testing</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">Recommendations</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "An AI extraction method was hand-validated against a classical keyword baseline on a 104-item "
        "hand-labeled test set (AI won, F1 0.400 vs. 0.364) before being chosen for full-scale analysis -- "
        "full reasoning on the Methodology page."
    )

    st.markdown("---")
    st.markdown(
        '<p style="color:#94A3B8; font-size:0.85rem;">Built by Shravani Kulkarni &middot; MS Data Science</p>',
        unsafe_allow_html=True,
    )
