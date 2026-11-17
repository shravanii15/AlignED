"""sections/about.py: About and Product Brief. A role lens for different readers, the product thinking behind the
project, and an honest list of what is measured and what is only proposed."""

import os

import streamlit as st

from utils.layout import page_header

GITHUB = "https://github.com/shravanii15/AlignED"
ARCHITECTURE_SVG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "architecture.svg")

LENSES = {
    "Data Scientist": {
        "look": "Key Findings, Skill Gaps, Methodology & Limitations",
        "points": [
            "Each gap is tested (two-proportion z-test, Fisher's exact test for small counts) with Benjamini-Hochberg correction per program. Correction cut significant gaps from 236 to 170 and rising or falling trends from 9 to 0.",
            "A design-effect sensitivity check for postings clustered by employer keeps 166 of 170 gaps significant; a company-cluster bootstrap keeps all 170 intervals above zero.",
            "The posting sample is category-balanced, so results describe that sample, not the whole labor market.",
        ],
    },
    "Data / Analytics Engineer": {
        "look": "Data Health, Methodology & Limitations, the GitHub workflows",
        "points": [
            "A daily ingestion job (Prefect) validates and deduplicates a job feed; a weekly job compares new postings with the fixed sample and commits a small JSON file the app reads.",
            "The feed truncates descriptions to 500 characters. A naive comparison showed a false collapse in Python demand; the historical sample was re-measured on the same 500 characters before comparing.",
            "dbt tests, schema validation, an atomic full rebuild (build on a temp database, replace only after validation) and CI on every push.",
        ],
    },
    "ML Engineer": {
        "look": "Model Evaluation, Methodology & Limitations",
        "points": [
            "An LLM extractor beat a keyword baseline on the data it was tuned on, then lost on 50 unseen items (F1 0.198 vs 0.311, difference interval below zero). The keyword method was kept.",
            "Error analysis: both miss most broad skill areas; they tie on named tools. Recall, not precision, is the limit.",
            "Held-out code and labels are hashed and the development set is checked for overlap (max 14.8%). Labels are AI-drafted and human-verified, not independent.",
        ],
    },
    "Product Manager": {
        "look": "Overview, Match a Job, Product Brief below",
        "points": [
            "Problem: students choose programs, and which skills to learn next, without evidence of how the curriculum compares with hiring demand.",
            "Three entry points by user need: see a program's gaps, check one job posting against your skills, or analyze your own course list.",
            "Decisions were made on evidence and recorded: keep the keyword method, keep the fixed sample for statistics, show the weaker numbers rather than the bigger ones.",
        ],
    },
    "Forward-deployed Engineer": {
        "look": "Analyze Your Program, Match a Job, the API",
        "points": [
            "Analyze Your Program runs the same tested analysis on any course list a client supplies (CSV or pasted text), in session, with nothing stored.",
            "Input limits, encoding errors and small-sample warnings are handled with plain-language messages rather than stack traces.",
            "A versioned FastAPI service and Docker images expose the same results to other systems.",
        ],
    },
}

BRIEF = {
    "Users": "Graduate students choosing or finishing a program; academic advisors and program offices reviewing a curriculum.",
    "Job to be done": "Show me, with evidence, which skills employers ask for that my program does not cover, and what to learn first.",
    "Proposed success metrics (not yet measured)": "Share of visitors who complete a gap analysis or job match; return visits after the weekly refresh; advisors who say they would use it in a curriculum review.",
    "Trade-offs made": "Fixed sample over a live feed, so published numbers do not drift. A simpler, explainable extractor over an LLM that scored lower. Fewer, tested gaps over a longer list.",
    "Known limits": "Keyword matching misses broad skill areas; descriptions are a proxy for what is taught; the posting sample is not the whole market; 50 held-out items is small.",
    "Next": "Larger skill vocabulary, a second independent labeler, and a short user study with advisors.",
}


def render_about():
    page_header("", "About", "The person behind the project, how to read it for a given role, and the product thinking.")
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown(
            '<p class="about-name">Shravani Kulkarni</p>'
            '<p class="about-role">MS Data Science, Arizona State University &middot; graduating May 2027</p>'
            "<p class=\"about-story\">Students pick a graduate program without knowing whether it teaches what employers ask for. "
            "I built AlignED to answer that with evidence: I compared 1,378 course descriptions from 13 programs with 1,660 job postings, "
            "tested which skills are really missing, and then tested my own method on data it had never seen. "
            "The part I am proudest of is that the LLM approach I expected to win lost, so I shipped the simpler one and said so.</p>",
            unsafe_allow_html=True,
        )
    with right:
        with st.container(border=True):
            st.markdown('<p class="role-tag">Find the work</p>', unsafe_allow_html=True)
            st.link_button("GitHub repository", GITHUB, use_container_width=True)
            st.link_button("Case study", f"{GITHUB}/blob/main/docs/CASE_STUDY.md", use_container_width=True)
            st.link_button("Evaluation report", f"{GITHUB}/blob/main/docs/EVALUATION.md", use_container_width=True)

    st.markdown('<p class="section-eyebrow">If you are hiring for...</p>', unsafe_allow_html=True)
    tabs = st.tabs(list(LENSES))
    for tab, role in zip(tabs, LENSES):
        with tab:
            lens = LENSES[role]
            st.markdown(f"**Start with:** {lens['look']}")
            for point in lens["points"]:
                st.markdown(f"- {point}")

    if os.path.exists(ARCHITECTURE_SVG):
        st.markdown('<p class="section-eyebrow">How it is built</p>', unsafe_allow_html=True)
        st.image(ARCHITECTURE_SVG, use_container_width=True)

    st.markdown('<p class="section-eyebrow">Product brief</p>', unsafe_allow_html=True)
    cols = st.columns(2, gap="large")
    for i, (k, v) in enumerate(BRIEF.items()):
        with cols[i % 2], st.container(border=True):
            st.markdown(f'<p class="role-tag">{k}</p><p class="path-desc" style="margin:0;">{v}</p>', unsafe_allow_html=True)
    st.caption("Success metrics are proposals. The app has no analytics, so no usage numbers are claimed.")
