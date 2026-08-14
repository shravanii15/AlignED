"""sections/overview.py -- the Overview page: headline numbers + a
one-paragraph summary of the whole pipeline."""

import streamlit as st

from services.database import run_query


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
    gaps = run_query("SELECT COUNT(*) AS n FROM gap_scores").iloc[0]["n"]
    recs = run_query("SELECT COUNT(*) AS n FROM recommendations").iloc[0]["n"]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("University Programs", programs)
    col2.metric("Real Courses Analyzed", f"{courses:,}")
    col3.metric("Job Postings Analyzed", f"{postings:,}")
    col4.metric("Statistically Significant Gaps", gaps)
    col5.metric("Final Recommendations", recs)

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
    st.info("Use the sidebar to explore a specific program's recommendations, skill demand trends, or the honest methodology behind this project.")
