"""sections/own_program.py: Analyze Your Program.

A visitor (a student, an advisor, a program office) provides a list of course descriptions and gets the same tested
gap analysis AlignED runs for the 13 built-in programs. Input is processed in memory for the session and never stored."""

import pandas as pd
import streamlit as st

from services.database import run_query
from services.own_program import MAX_COURSES, SMALL_CORPUS, CourseInputError, analyze, parse_csv, parse_pasted
from utils.layout import page_header
from utils.visuals import stat_tiles

TEXT_KEY = "own_program_text"
RUN_KEY = "own_program_run"
EXAMPLE_COURSES = """Introduction to Statistics. Probability, estimation, hypothesis testing and regression, with applications in R.

Database Systems. Relational design, SQL, indexing, transactions and query optimization.

Machine Learning. Supervised and unsupervised learning, model evaluation, and neural networks, with assignments in Python.

Software Engineering. Requirements, design patterns, testing, version control with Git, and agile teamwork.

Operating Systems. Processes, threads, memory management and file systems, with projects in C on Linux.

Data Visualization. Principles of visual design and building dashboards with Tableau.
"""


def _load_example():
    st.session_state[TEXT_KEY] = EXAMPLE_COURSES
    st.session_state[RUN_KEY] = True


def render_own_program():
    page_header(
        "", "Analyze Your Program",
        "Bring a course list from any program. AlignED finds the skills in your course descriptions and tests which ones "
        "job postings ask for much more often, using the same method as the 13 built-in programs.",
    )
    st.caption(
        f"Up to {MAX_COURSES} courses. Your text is processed in this session only; AlignED does not save it and sends it to no outside service."
    )

    left, right = st.columns([3, 2], gap="large")
    with left:
        text = st.text_area(
            "Paste course descriptions (separate courses with a blank line)", key=TEXT_KEY, height=220,
            placeholder="Course title. Description of what the course covers...",
        )
    with right:
        upload = st.file_uploader("Or upload a CSV", type=["csv"], key="own_program_csv",
                                  help="One row per course. A column named description (and optionally course_name or title) is used.")
        st.button("Try with an example", on_click=_load_example, use_container_width=True)
    if st.button("Run the analysis", type="primary"):
        st.session_state[RUN_KEY] = True
    if not st.session_state.get(RUN_KEY):
        st.info("Paste or upload your courses, then run the analysis. Or try the example.")
        return

    try:
        courses = parse_csv(upload.getvalue()) if upload is not None else parse_pasted(text)
    except CourseInputError as exc:
        st.warning(str(exc))
        return

    tracked = run_query(
        """
        SELECT DISTINCT s.skill_id, s.canonical_name FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        """
    )
    counts_df = run_query(
        "SELECT skill_id, COUNT(DISTINCT source_id) AS n FROM extractions WHERE source_type = 'posting' AND method = 'baseline_keyword' GROUP BY skill_id"
    )
    total = int(run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"])
    rows = analyze(courses, tracked, dict(zip(counts_df["skill_id"], counts_df["n"])), total)
    sig = [r for r in rows if r["significant"]]

    stat_tiles([(str(len(courses)), "courses read"), (str(len(rows)), "skills tested"), (str(len(sig)), "significant gaps")])
    if len(courses) < SMALL_CORPUS:
        st.warning(f"{len(courses)} courses is a small list. A small list can miss skills a full catalog would catch, so read gaps as leads, not conclusions.")

    st.markdown('<p class="section-eyebrow">Skills employers ask for that your courses do not</p>', unsafe_allow_html=True)
    if not sig:
        st.success("No skill showed a statistically significant gap with this course list.")
    else:
        table = pd.DataFrame([{
            "Skill": r["skill"], "Your courses": f"{r['your_courses']} of {len(courses)}", "Your coverage": f"{r['your_rate']*100:.1f}%",
            "Job postings": f"{r['market_rate']*100:.1f}%", "Gap (points)": round(r["gap"] * 100, 1), "q-value": f"{r['q_value']:.4f}", "Test": r["test"],
        } for r in sig])
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.download_button("Download results (CSV)", table.to_csv(index=False).encode("utf-8"), "aligned_your_program_gaps.csv", "text/csv")
    with st.expander("How to read this"):
        st.markdown(
            "- **Your coverage** is the share of your courses whose description names the skill. **Job postings** is the share of the "
            "1,660 sampled postings that name it.\n"
            "- A **gap** is shown only if it is positive and still significant after correcting for testing many skills at once.\n"
            "- A mention in a description is a proxy for coverage, not proof of how well it is taught, and the postings are a "
            "category-balanced sample, not the whole labor market."
        )
