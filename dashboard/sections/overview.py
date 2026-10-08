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
from utils.visuals import bridge_svg, mini_bar, stat_tiles
from utils.nav import (
    GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_PERSONALIZE,
    PAGE_BUILD_PROFILE, PAGE_HEATMAP, PAGE_METHODOLOGY, PAGE_ROLE_GROUPS, PAGE_TRENDS,
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
        SELECT p.program_id, p.university, p.program_name, s.canonical_name AS skill_name,
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
                Statistically significant after correction (q = {r["q_value"]:.3g}). A text mention is a proxy for coverage, not proof of what is taught.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("**How to read this**")
        st.caption(
            "Each bar is the share of texts that name the skill: course descriptions on one side, job postings on the other. "
            "The gap is the difference. AlignED tests every gap and corrects for running many tests before it shows one."
        )
        st.button(
            "Explore this analysis →", key="home_signal_btn", type="primary", use_container_width=True,
            on_click=jump_to_program_explorer, args=(label, OVERALL_MARKET_LABEL),
        )
        st.button("Why trust it? See the method", key="home_signal_method_btn", use_container_width=True,
                  on_click=jump_to, args=(GROUP_METHODOLOGY, PAGE_METHODOLOGY))


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
        MENTIONED_AT = 0.05  # a skill counts as "taught" when 5%+ of courses name it
        items = []
        for _, r in ex.iterrows():
            kind = "ok" if r["cov"] >= MENTIONED_AT else ("warn" if r["cov"] > 0 else "no")
            items.append((r["skill_name"], kind))
        n_ok = sum(1 for _, k in items if k == "ok")
        first = ex.iloc[0]
        card = f"""
        <div class="bridge-card">
            {bridge_svg(items)}
            <div class="bridge-legend">
                <span><i class="ad-key ad-key-ok"></i>Courses teach it</span>
                <span><i class="ad-key ad-key-warn"></i>Barely mentioned</span>
                <span><i class="ad-key ad-key-no"></i>Missing plank</span>
            </div>
            <p class="bridge-caption">Each plank is a skill employers want most. <b>{n_ok} of {len(items)}</b> are solid at
            {first["university"]}.</p>
        </div>"""
    st.markdown(
        f"""
        <div class="hero-panel">
            <div class="hero-left">
                <p class="hero-wordmark">Align<span class="wm-ed">ED</span></p>
                <p class="hero-motto">Align your education with the job market.</p>
                <p class="hero-headline">Where does graduate education diverge from the job market?</p>
                <p class="hero-tagline">Paste a job or pick a program. We show the missing skills, ranked, and courses that teach them.</p>
            </div>
            {card}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
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

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Under the hood ----
    st.markdown('<p class="section-eyebrow">Under The Hood</p>', unsafe_allow_html=True)
    stat_tiles([
        ("13", "programs"), ("1,378", "course descriptions"), ("1,660", "job postings"),
        ("1,597", "O*NET skills"), ("104 + 50", "development + held-out test items"),
    ])
    st.caption(
        "Gaps use two-proportion and Fisher's exact tests with false-discovery correction. Skills are found with a keyword "
        "baseline that beat a local LLM on held-out data. Data comes from a validated daily pipeline."
    )
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
