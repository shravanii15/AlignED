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
from services.open_skills import (
    ALIASES, Corpus, correct_typos, job_terms, measure, measure_items, mentions, parse_items,
)
from utils.text import SKILL_ALIASES, normalize_term


@st.cache_resource
def _corpora(version):
    con = get_connection()
    postings = Corpus([r[0] for r in con.execute("SELECT description FROM postings")])
    courses = Corpus([r[0] for r in con.execute("SELECT description FROM courses")])
    return postings, courses


def fix_typos(user_text, tracked_df):
    """Correct obvious misspellings ("kubernets" -> "Kubernetes") and say so.

    Returns the corrected text, which the page then uses everywhere."""
    if not parse_items(user_text):
        return user_text
    postings, courses = _corpora(_db_version())
    vocabulary = set(tracked_df["canonical_name"]) | {s[0] for s in ALIASES.values()}
    corrected, fixes = correct_typos(user_text, vocabulary, postings, courses)
    if fixes:
        notes = ", ".join(f"“{typed}” as “{right}”" for typed, right in fixes.items())
        st.caption(f"Read {notes}. Check the spelling if that is not what you meant.")
    return corrected


def untracked_job_terms(job_text, tracked_df):
    """Skills in a posting that the tracked list does not already cover."""
    tracked = {normalize_term(n) for n in tracked_df["canonical_name"]}
    handled = {alias for alias, official in SKILL_ALIASES.items() if normalize_term(official) in tracked}
    return [t for t in job_terms(job_text) if t.lower() not in handled and normalize_term(t) not in tracked]


def render_job_extras(terms, my_text, title="Also in this posting, beyond AlignED's tracked tools"):
    """Table for skills a posting names that the tracked list misses, with
    whether the visitor listed each one and how the market treats it."""
    if not terms:
        return
    postings, courses = _corpora(_db_version())
    rows = []
    for term in terms:
        s = measure(term, postings, courses)
        row = {
            "Skill": term,
            "Job postings": round(s.posting_share * 100, 1),
            "Course descriptions": round(s.course_share * 100, 1),
        }
        row["You listed it"] = ("Yes" if mentions(term, my_text) else "No") if (my_text or "").strip() else "Add your skills above"
        row["What the data says"] = s.reading
        rows.append(row)
    st.markdown(f'<p class="section-eyebrow">{title}</p>', unsafe_allow_html=True)
    pct = st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        column_config={"Job postings": pct, "Course descriptions": pct,
                       "What the data says": st.column_config.TextColumn(width="large")},
    )
    st.caption(
        "These skills are read straight from the posting text and measured against the same "
        "postings and course descriptions. They are simple mention counts, outside AlignED's tested gap analysis."
    )


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
    st.dataframe(df, hide_index=True, width="stretch", column_config=config)
    st.caption(
        f"Shares are the percent of {len(postings):,} job postings that mention the skill and the percent of "
        f"{len(courses):,} course descriptions that name it. Course descriptions are short, so a skill they "
        "do not name may still be taught. Anything you type is measured, even if AlignED's main analysis "
        "does not track it."
    )
    return [s.term for s in signals]
