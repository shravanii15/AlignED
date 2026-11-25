"""
utils/skill_table.py: the "every skill you typed, measured" table shown on
Which Jobs Fit Me and Match a Job.

Anything a visitor types is measured against the raw postings and course
descriptions (see services/open_skills.py), so no skill is ever rejected
for being outside a fixed list.
"""

import pandas as pd
import streamlit as st

from services.database import _db_version, get_connection
from services.open_skills import Corpus, measure_items, mentions, parse_items


@st.cache_resource
def _corpora(version):
    con = get_connection()
    postings = Corpus([r[0] for r in con.execute("SELECT description FROM postings")])
    courses = Corpus([r[0] for r in con.execute("SELECT description FROM courses")])
    return postings, courses


def render_skill_signals(user_text, job_text=None, title="Every skill you listed, measured"):
    """Draw the table. Returns the list of typed items (empty if none)."""
    if not parse_items(user_text):
        return []
    postings, courses = _corpora(_db_version())
    signals = measure_items(user_text, postings, courses)
    if not signals:
        return []

    st.markdown(f'<p class="section-eyebrow">{title}</p>', unsafe_allow_html=True)
    rows = []
    for s in signals:
        row = {
            "Skill": s.term,
            "Job postings": round(s.posting_share * 100, 1),
            "Course descriptions": round(s.course_share * 100, 1),
            "What the data says": s.reading,
        }
        if job_text is not None:
            row["In this posting"] = "Yes" if mentions(s.term, job_text) else "No"
        rows.append(row)
    df = pd.DataFrame(rows)

    pct = st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
    config = {
        "Job postings": pct,
        "Course descriptions": pct,
        "What the data says": st.column_config.TextColumn(width="large"),
    }
    st.dataframe(df, hide_index=True, use_container_width=True, column_config=config)
    st.caption(
        f"Shares are the percent of {len(postings):,} job postings that mention the skill and the percent of "
        f"{len(courses):,} course descriptions that name it. Course descriptions are short, so a skill they "
        "do not name may still be taught. Anything you type is measured, even if AlignED's main analysis "
        "does not track it."
    )
    return [s.term for s in signals]
