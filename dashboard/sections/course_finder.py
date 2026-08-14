"""sections/course_finder.py -- search/filter real courses across all
13 programs by keyword or specific tracked skill."""

import streamlit as st

from services.database import run_query


def render_course_finder():
    st.title("🔎 Course Finder")
    st.markdown(
        "Looking for courses that build a specific skill (e.g. Python, Docker, Machine Learning)? "
        "Search or filter below -- no upload needed, this searches real course descriptions across all 13 programs directly."
    )

    search_text = st.text_input("Search course names/descriptions (e.g. 'software', 'security', 'machine learning')")

    tracked_skills_df = run_query(
        """
        SELECT DISTINCT s.skill_id, s.canonical_name
        FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword'
        ORDER BY s.canonical_name
        """
    )
    skill_filter = st.multiselect("...or filter by a specific tracked skill", tracked_skills_df["canonical_name"])

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
        st.info("Type a search term or pick a skill above to find matching courses.")
        return

    results = run_query(base_query, tuple(params))
    st.caption(f"{len(results)} matching course(s) found (showing up to 100).")
    for _, row in results.iterrows():
        with st.expander(f"{row['course_name']}  --  {row['university']}"):
            st.caption(row["program_name"])
            st.write(row["description"] or "(no description available)")
