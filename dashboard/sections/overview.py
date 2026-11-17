"""sections/overview.py: the Home page.

Built around the two questions a visitor actually arrives with, not
around the analysis behind them:

  1. "I found a job: do I match it, what do I learn first?"
  2. "I am choosing a program: does it teach what employers want?"

Each gets one card with its own action. A real example from the data
sits underneath, and the deeper data pages are one small row of links.
"""

import plotly.graph_objects as go
import streamlit as st

from services.database import run_query
from services.robustness import gap_interval, load_robustness
from utils.charts import apply_chart_theme
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.formatting import program_label
from utils.visuals import mini_bar
from utils.nav import (
    GROUP_ABOUT, GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_OVERVIEW, GROUP_PERSONALIZE,
    PAGE_ABOUT, PAGE_BYO, PAGE_DATA_HEALTH, PAGE_FINDINGS, PAGE_MODEL_EVAL, PAGE_PROGRAM_EXPLORER,
    OVERALL_MARKET_LABEL, jump_to, jump_to_program_explorer, start_job_match,
)

# Skill-gap example is only drawn from programs with enough courses that
# a missing skill is not just a small-sample artifact.
EXAMPLE_MIN_COURSES = 30


def _signal_row():
    """The top recommended gap for the program with the most gaps (among programs with enough courses)."""
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
    return None if sig.empty else sig.iloc[0]


def _render_signal():
    """One real finding with its numbers and the evidence one click away."""
    r = _signal_row()
    if r is None:
        return
    label = program_label(r["university"], r["program_name"])
    cov_n = int(round(r["cov"] * r["n_courses"]))
    interval = gap_interval(load_robustness(), int(r["program_id"]), int(r["skill_id"]))
    ci_text = (f" 95% interval for the gap: {interval[0]*100:.0f} to {interval[1]*100:.0f} points, adjusted for postings "
               "from the same employer being alike.") if interval else ""
    q_text = "q < 0.001" if r["q_value"] < 0.001 else f"q = {r['q_value']:.3f}"
    st.markdown(
        f"""
        <div class="vcard" style="border-top-color:#D94A4A;">
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
    st.button("Explore this analysis \u2192", key="home_signal_btn", type="primary", use_container_width=True,
              on_click=jump_to_program_explorer, args=(label, OVERALL_MARKET_LABEL))


GITHUB = "https://github.com/shravanii15/AlignED"
STACK = ("Python", "SQL / SQLite", "Streamlit", "FastAPI", "dbt", "Prefect", "Docker", "GitHub Actions", "pytest")


def _finding_sentence():
    """One concrete result for the hero, from the same query as the signal card; empty if unavailable."""
    row = _signal_row()
    if row is None:
        return ""
    return (f"{row['skill_name']} appears in {row['dem']*100:.0f}% of sampled job postings but in "
            f"{int(round(row['cov'] * row['n_courses']))} of {int(row['n_courses'])} course descriptions at "
            f"{program_label(row['university'], row['program_name'])}.")


def _hero():
    """Full-width gradient masthead with the four headline numbers, all read from the database."""
    n_prog = int(run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"])
    n_courses = int(run_query("SELECT COUNT(*) AS n FROM courses").iloc[0]["n"])
    n_posts = int(run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"])
    n_gaps = int(run_query("SELECT COUNT(*) AS n FROM gap_scores WHERE cluster_id IS NULL").iloc[0]["n"])
    kpis = "".join(
        f'<div class="hero-kpi"><div class="hero-kpi-value">{v:,}</div><div class="hero-kpi-label">{lbl}</div></div>'
        for v, lbl in ((n_prog, "graduate programs"), (n_courses, "courses analysed"), (n_posts, "job postings"), (n_gaps, "statistically tested skill gaps"))
    )
    finding = _finding_sentence()
    finding_html = f'<p class="hero-finding"><b>Example finding.</b> {finding}</p>' if finding else ""
    stack = "".join(f"<span>{t}</span>" for t in STACK)
    st.markdown(
        f"""
        <div class="hero-band">
            <p class="hero-kicker">Curriculum vs. job-market skill-gap analysis</p>
            <h1>Where does graduate education diverge from <em>the job market</em>?</h1>
            <p class="hero-sub">AlignED compares what graduate computing programs teach with what employers ask for,
            and tests every difference before it shows you one.</p>
            {finding_html}
            <div class="hero-kpis">{kpis}</div>
            <div class="hero-badges">
                <span class="hb-label">Open project</span>
                <a href="{GITHUB}" target="_blank">GitHub repository</a>
                <a href="{GITHUB}/blob/main/docs/CASE_STUDY.md" target="_blank">Case study</a>
                <a href="{GITHUB}/blob/main/docs/EVALUATION.md" target="_blank">Evaluation report</a>
                <span class="hb-label" style="margin-left:0.8rem;">Built with</span>{stack}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _widespread_chart():
    """Top skills that are significant gaps in the most programs (overall-market scope)."""
    df = run_query(
        """
        SELECT s.canonical_name AS skill, COUNT(*) AS n_programs
        FROM gap_scores g JOIN skills s ON s.skill_id = g.skill_id
        WHERE g.cluster_id IS NULL GROUP BY g.skill_id ORDER BY n_programs DESC, AVG(g.gap_value) DESC
        """
    )
    df = df[~df["skill"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)].head(8).iloc[::-1]
    if df.empty:
        return
    n_prog = int(run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"])
    fig = go.Figure(go.Bar(x=df["n_programs"], y=df["skill"], orientation="h", marker_color="#2F5BEA",
                           text=df["n_programs"], textposition="outside", hovertemplate="%{y}: missing in %{x} programs<extra></extra>"))
    fig.update_layout(height=330, margin=dict(l=0, r=30, t=10, b=0), xaxis=dict(range=[0, n_prog + 1], title=f"Programs with a significant gap (of {n_prog})"), yaxis_title=None)
    st.plotly_chart(apply_chart_theme(fig), use_container_width=True, config={"displayModeBar": False})


def _feature_cards():
    cards = [
        ("Explore the gaps", "Pick a program and a job family. See each tested gap with its evidence.", "Open skill gaps", (GROUP_EXPLORE, PAGE_PROGRAM_EXPLORER)),
        ("Analyze your program", "Upload any course list and get the same tested analysis in seconds.", "Try it", (GROUP_PERSONALIZE, PAGE_BYO)),
        ("Check the evidence", "A keyword method beat an LLM on 50 unseen items. See the test and its limits.", "See the evaluation", (GROUP_METHODOLOGY, PAGE_MODEL_EVAL)),
        ("Watch the data pipeline", "A daily feed is validated and deduplicated. See how it has behaved.", "Open data health", (GROUP_METHODOLOGY, PAGE_DATA_HEALTH)),
    ]
    for i, (col, (title, desc, cta, dest)) in enumerate(zip(st.columns(4, gap="medium"), cards)):
        with col, st.container(border=True, key=f"feat_{i}"):
            st.markdown(f'<p class="path-title">{title}</p><p class="path-desc">{desc}</p>', unsafe_allow_html=True)
            st.button(cta + " \u2192", key=f"feat_btn_{i}", use_container_width=True, on_click=jump_to, args=dest)


def _steps():
    steps = [
        ("Collect", "1,378 course descriptions from 13 programs and 1,660 job postings."),
        ("Find skills", "Match both against the O*NET skill list with a keyword method."),
        ("Test each gap", "z-test or Fisher's exact test, corrected for many comparisons."),
        ("Rank", "Order what to learn first by size of gap and strength of evidence."),
    ]
    for i, (col, (title, desc)) in enumerate(zip(st.columns(4, gap="medium"), steps), 1):
        col.markdown(f'<div class="step-card"><span class="step-num">{i}</span><p class="step-title">{title}</p><p class="step-desc">{desc}</p></div>', unsafe_allow_html=True)


def _role_strip():
    roles = [
        ("Data science", "Hypothesis tests, small-sample (Fisher) tests, multiple-comparison correction, bootstrap intervals.", "Key findings", (GROUP_OVERVIEW, PAGE_FINDINGS)),
        ("Data engineering", "Daily validated ingestion, deduplication, dbt tests, atomic rebuilds, CI/CD.", "Data health", (GROUP_METHODOLOGY, PAGE_DATA_HEALTH)),
        ("Machine learning", "Held-out evaluation where an LLM lost to a keyword baseline, with error analysis.", "Model evaluation", (GROUP_METHODOLOGY, PAGE_MODEL_EVAL)),
        ("Product", "User paths, trade-offs and a product brief, with honest limits.", "Product brief", (GROUP_ABOUT, PAGE_ABOUT)),
        ("Forward-deployed", "Bring your own course list and get a tested analysis in seconds.", "Analyze a program", (GROUP_PERSONALIZE, PAGE_BYO)),
    ]
    st.markdown('<p class="section-eyebrow">What this project demonstrates</p>', unsafe_allow_html=True)
    for i, (col, (tag, desc, cta, dest)) in enumerate(zip(st.columns(5, gap="small"), roles)):
        with col, st.container(border=True, key=f"role_{i}"):
            st.markdown(f'<p class="role-tag">{tag}</p><p class="path-desc">{desc}</p>', unsafe_allow_html=True)
            st.button(cta + " \u2192", key=f"role_btn_{i}", use_container_width=True, on_click=jump_to, args=dest)


def render_overview():
    _hero()
    _role_strip()
    st.markdown('<p class="section-eyebrow">Try it yourself</p>', unsafe_allow_html=True)
    _render_paths()
    st.markdown('<p class="section-eyebrow">What the data says</p>', unsafe_allow_html=True)
    left, right = st.columns([3, 2], gap="large")
    with left:
        _render_signal()
    with right:
        st.markdown("**Skills missing from the most programs**")
        _widespread_chart()
        st.button("Key findings across all programs \u2192", key="home_findings_btn", use_container_width=True,
                  on_click=jump_to, args=(GROUP_OVERVIEW, PAGE_FINDINGS))
    st.markdown('<p class="section-eyebrow">Go deeper</p>', unsafe_allow_html=True)
    _feature_cards()
    st.markdown('<p class="section-eyebrow">How it works</p>', unsafe_allow_html=True)
    _steps()
    st.caption("Skills are found with a keyword method that beat an LLM on held-out data. A text mention is a proxy for coverage, not proof of what is taught.")


def _render_paths():
    programs_df = run_query(
        "SELECT p.program_id, p.university, p.program_name, "
        "(SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses, "
        "(SELECT COUNT(*) FROM recommendations r WHERE r.program_id = p.program_id AND r.cluster_id IS NULL) AS n_gaps "
        "FROM programs p ORDER BY p.university"
    )
    programs_df["label"] = [program_label(u, p) for u, p in zip(programs_df["university"], programs_df["program_name"])]
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
            job_text = st.text_area("Job posting", key="home_job_text", height=122, placeholder="Paste a job description here")
            st.button("Check how I match \u2192", key="home_match_btn", type="primary", use_container_width=True,
                      on_click=start_job_match, args=(job_text,))
    with right:
        with st.container(border=True):
            st.markdown('<p class="path-title">I am choosing a program</p>', unsafe_allow_html=True)
            st.markdown('<p class="path-desc">See which skills employers want that a program\'s courses do not mention.</p>', unsafe_allow_html=True)
            program_choice = st.selectbox("Program", programs_df["label"], index=default_idx, key="home_program_choice")
            role_choice = st.selectbox("Compared with jobs in", role_options, key="home_role_choice")
            st.button("Show me the gaps \u2192", key="home_analyze_btn", type="primary", use_container_width=True,
                      on_click=jump_to_program_explorer, args=(program_choice, role_choice))
