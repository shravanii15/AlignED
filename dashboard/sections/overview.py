"""sections/overview.py -- the Overview page: hero banner, headline
numbers, and three clickable "what do you want to do?" action cards that
jump straight to the relevant section -- the actual front door of the
product, not just a summary to scroll past."""

import streamlit as st

from services.database import run_query
from utils.nav import (
    GROUP_ANALYZE, GROUP_EXPLORE, GROUP_PERSONALIZE,
    PAGE_HEATMAP, PAGE_PROGRAM_EXPLORER, PAGE_BUILD_PROFILE,
    jump_to,
)


def render_overview():
    st.markdown(
        """
        <div class="aligned-banner">
            <h1>🎓 AlignED</h1>
            <p>Do graduate computing programs actually teach what the job market wants?
            Real curricula vs. real job postings, with statistical proof -- not guesses.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("University Programs", programs)
    col2.metric("Real Courses Analyzed", f"{courses:,}")
    col3.metric("Job Postings Analyzed", f"{postings:,}")
    col4.metric("Statistically Significant Gaps", gaps)
    col5.metric("Final Recommendations", recs)
    st.caption("Gap and recommendation counts above are the overall-market scope. Program Explorer lets you narrow the analysis to a specific target role.")
    st.markdown(
        '📚 **Skill taxonomy: U.S. Department of Labor O\\*NET** -- every skill on this dashboard comes from '
        "this real, external, publicly maintained standard. Nothing here is an invented list."
    )

    st.markdown("---")
    st.markdown('<p class="section-eyebrow">WHAT DO YOU WANT TO DO?</p>', unsafe_allow_html=True)

    card_col1, card_col2, card_col3 = st.columns(3)

    with card_col1:
        with st.container(border=True):
            st.markdown(
                """
                <div class="action-card-icon">🎯</div>
                <div class="action-card-title">Analyze a Program</div>
                <div class="action-card-desc">Pick a graduate program and a target role, and see exactly
                which in-demand skills it's missing -- with statistical proof.</div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Start analysis →", key="card_analyze", use_container_width=True,
                on_click=jump_to, args=(GROUP_ANALYZE, PAGE_PROGRAM_EXPLORER),
            )

    with card_col2:
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

    with card_col3:
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
    st.markdown(
        """
        **How this was built, in one paragraph:** real course descriptions were
        scraped from 13 university catalogs, and real job postings were pulled
        from a live daily pipeline plus a historical dataset. Both were matched
        against the official US Department of Labor (O\\*NET) skills taxonomy.
        An AI extraction method was hand-validated against a classical keyword
        baseline on a 104-item hand-labeled test set (AI won, F1 0.400 vs.
        0.364) before choosing the faster method for full-scale analysis --
        see the Methodology page for the full, honest reasoning.
        """
    )
    st.info("Use the cards above, or the sidebar, to explore a specific program's recommendations, skill demand trends, or the honest methodology behind this project.")
