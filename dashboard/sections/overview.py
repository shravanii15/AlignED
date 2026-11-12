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
from services.robustness import gap_interval, load_robustness
from sections.program_explorer import OVERALL_MARKET_LABEL
from utils.formatting import evidence_strength, program_label
from utils.visuals import mini_bar
from utils.nav import (
    GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_OVERVIEW, GROUP_PERSONALIZE,
    PAGE_BUILD_PROFILE, PAGE_FINDINGS, PAGE_HEATMAP, PAGE_METHODOLOGY, PAGE_ROLE_GROUPS, PAGE_TRENDS,
    jump_to, jump_to_program_explorer, start_job_match,
)

# Skill-gap example is only drawn from programs with enough courses that
# a missing skill is not just a small-sample artifact.
EXAMPLE_MIN_COURSES = 30


def _render_signal():
    """One real finding, pulled from the data: the top recommended gap for the program with the most gaps.
    It is the centerpiece of the page, with the numbers and the evidence one click away."""
    sig = run_query(
        f"""
        SELECT p.program_id, r.skill_id, p.university, p.program_name, s.canonical_name AS skill_name,
               g.program_coverage_rate AS cov, g.market_demand_rate AS dem, g.gap_value, g.q_value,
               (SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses,
               (SELECT COUNT(*) FROM recommendations x WHERE x.program_id = p.program_id AND x.cluster_id IS NULL) AS n_recs
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        JOIN programs p ON p.program_id = r.program_id
        JOIN skills s ON s.skill_id = r.skill_id
        WHERE r.cluster_id IS NULL
          AND (SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) >= {EXAMPLE_MIN_COURSES}
        ORDER BY n_recs DESC, g.gap_value DESC
        LIMIT 1
        """
    )
    if sig.empty:
        return
    r = sig.iloc[0]
    label = program_label(r["university"], r["program_name"])
    cov_n = int(round(r["cov"] * r["n_courses"]))
    interval = gap_interval(load_robustness(), int(r["program_id"]), int(r["skill_id"]))
    ci_text = (f" 95% interval for the gap: {interval[0]*100:.0f} to {interval[1]*100:.0f} points, adjusted for postings "
               "from the same employer being alike.") if interval else ""
    q_text = "q < 0.001" if r["q_value"] < 0.001 else f"q = {r['q_value']:.3f}"
    st.markdown('<p class="section-eyebrow">A Real Signal From The Data</p>', unsafe_allow_html=True)
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(
            f"""
            <div class="vcard vcard-accent" style="border-top-color:#D94A4A;">
                <p class="vcard-title">{r["skill_name"]} &nbsp;<span class="arrow-chip arrow-down">{r["gap_value"]*100:+.1f} point gap</span></p>
                <p class="vcard-sub">{label} compared with the overall job market</p>
                <div class="vcard-row"><span class="vcard-name">Curriculum</span>{mini_bar(r["cov"], "#98A2B3")}<span class="vcard-val">{r["cov"]*100:.1f}%</span></div>
                <div class="vcard-row"><span class="vcard-name">Job market</span>{mini_bar(r["dem"], "#D94A4A")}<span class="vcard-val">{r["dem"]*100:.1f}%</span></div>
                <p class="vcard-sub" style="margin-top:0.6rem;">{cov_n} of {int(r["n_courses"])} course descriptions mention it, against {r["dem"]*100:.0f}% of sampled postings.
                Statistically significant after correction ({q_text}). {ci_text} A text mention is a proxy for coverage, not proof of what is taught.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("**How to read this**")
        st.caption(
            "Each bar is the share of texts that name the skill, in course descriptions and in job postings. "
            "The gap is the difference, and it is shown only after a significance test."
        )
        st.button(
            "Explore this analysis →", key="home_signal_btn", type="primary", use_container_width=True,
            on_click=jump_to_program_explorer, args=(label, OVERALL_MARKET_LABEL),
        )
        st.button("Key findings across all programs", key="home_findings_btn", use_container_width=True,
                  on_click=jump_to, args=(GROUP_OVERVIEW, PAGE_FINDINGS))


def render_overview():
    st.markdown(
        """
        <div class="hero">
            <p class="hero-wordmark">Align<span class="wm-ed">ED</span></p>
            <p class="hero-headline">Where does graduate education diverge from the job market?</p>
            <p class="hero-tagline">AlignED compares what 13 graduate computing programs teach with what job postings ask for,
            and tests every difference before it shows you one.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_signal()
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

    st.markdown('<p class="section-eyebrow">How it works</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="howitworks-strip">
            <div class="howitworks-step">1. Collect courses and job postings</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">2. Find skills in both (O*NET)</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">3. Test each gap statistically</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">4. Rank what to learn first</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Skills are found with a keyword method that beat an LLM on held-out data. Every gap is tested with a z-test or Fisher's exact test and corrected for multiple comparisons.")
