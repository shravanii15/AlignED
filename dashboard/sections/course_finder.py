"""sections/course_finder.py: search/filter courses across all 13 programs
by keyword or tracked skill."""

import html

import streamlit as st

from services.database import run_query
from utils.layout import page_header
from utils.nav import COURSE_FINDER_SKILLS_KEY


def _pick_skill(skill):
    st.session_state[COURSE_FINDER_SKILLS_KEY] = [skill]


def render_course_finder():
    page_header("", "Course Finder", "Find courses across all 13 programs that mention a skill you want to learn.", art="search", pills=("13 programs", "1,378 courses"))

    search_text = st.text_input("Search course names and descriptions", placeholder="e.g. security, machine learning")

    tracked_skills_df = run_query(
        """
        SELECT DISTINCT s.skill_id, s.canonical_name
        FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword'
        ORDER BY s.canonical_name
        """
    )
    valid_skills = set(tracked_skills_df["canonical_name"])
    st.session_state[COURSE_FINDER_SKILLS_KEY] = [
        s for s in st.session_state.get(COURSE_FINDER_SKILLS_KEY, []) if s in valid_skills
    ]
    skill_filter = st.multiselect("Filter by skill", tracked_skills_df["canonical_name"], key=COURSE_FINDER_SKILLS_KEY)

    base_query = """
        SELECT c.course_name, c.description, p.university, p.program_name
        FROM courses c JOIN programs p ON p.program_id = c.program_id
        WHERE 1=1
    """
    params = []
    if search_text:
        base_query += " AND (c.course_name LIKE ? OR c.description LIKE ?)"
        params += [f"%{search_text}%", f"%{search_text}%"]
    if skill_filter:
        skill_ids = tracked_skills_df[tracked_skills_df["canonical_name"].isin(skill_filter)]["skill_id"].tolist()
        placeholders = ",".join(str(s) for s in skill_ids)
        base_query += f"""
            AND c.course_id IN (
                SELECT CAST(source_id AS INTEGER) FROM extractions
                WHERE source_type='course' AND method='baseline_keyword' AND skill_id IN ({placeholders})
            )
        """
    base_query += " LIMIT 100"

    if not search_text and not skill_filter:
        st.markdown('<p class="section-eyebrow">Popular Skills to Try</p>', unsafe_allow_html=True)
        popular = [s for s in ["Python", "SQL", "Docker", "Kubernetes", "Git", "Linux", "AWS", "Tableau"] if s in valid_skills]
        for col, skill in zip(st.columns(len(popular) or 1), popular):
            col.button(skill, key=f"cf_pop_{skill}", use_container_width=True, on_click=_pick_skill, args=(skill,))
        st.caption("Click a skill to see every course across the 13 programs that mentions it.")
        return

    results = run_query(base_query, tuple(params))
    st.markdown(f'<p class="section-eyebrow">{len(results)} matching courses (showing up to 100)</p>', unsafe_allow_html=True)
    for _, row in results.iterrows():
        desc = (row["description"] or "(no description available)").strip()
        if len(desc) > 320:
            desc = desc[:320].rsplit(" ", 1)[0] + "..."
        st.markdown(
            f"""
            <div class="course-card">
                <p class="course-card-title">{html.escape(row["course_name"])}</p>
                <p class="course-card-uni">{html.escape(row["university"])} &middot; {html.escape(row["program_name"])}</p>
                <p class="course-card-desc">{html.escape(desc)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
