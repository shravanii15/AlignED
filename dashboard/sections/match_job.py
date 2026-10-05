"""sections/match_job.py: "Match a Job". Paste a job posting and your own
skills, see which of the skills the job asks for you already have, which
you are missing, and which to learn first.

Works for any student regardless of program: it only needs the shared
O*NET-derived skill vocabulary, the same keyword matching the rest of the
dashboard uses, and the sampled postings for "how common is this skill".
"""

import pandas as pd
import streamlit as st

from services.database import run_query
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.layout import page_header
from utils.nav import MATCH_RUN_KEY, jump_to_course_finder
from utils.text import extract_user_skills

JOB_TEXT_KEY = "match_job_text"
MY_SKILLS_KEY = "match_my_skills"
LEARN_FIRST_SHOWN = 6

EXAMPLE_JOB = (
    "Data Engineer. We are looking for an engineer to build and maintain data pipelines. "
    "You will write Python and SQL, orchestrate jobs with Airflow, process data with Spark and Kafka, "
    "deploy services in Docker on AWS, and use Git for version control. Experience with Kubernetes, "
    "Snowflake and Tableau is a plus."
)
EXAMPLE_SKILLS = "I know Python and SQL, I have used Git, and I took a statistics course and a machine learning course."


def _load_example():
    st.session_state[JOB_TEXT_KEY] = EXAMPLE_JOB
    st.session_state[MY_SKILLS_KEY] = EXAMPLE_SKILLS
    st.session_state[MATCH_RUN_KEY] = True


def _market_demand():
    """Share of the sampled postings that mention each skill."""
    total = int(run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"])
    counts = run_query(
        """
        SELECT e.skill_id, COUNT(DISTINCT e.source_id) AS n
        FROM extractions e
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        GROUP BY e.skill_id
        """
    )
    counts["demand"] = counts["n"] / max(total, 1)
    return dict(zip(counts["skill_id"], counts["demand"]))


def render_match_job():
    page_header(
        "", "Match a Job",
        "Paste a job posting you like and your own skills. See what you already have, what is missing, and what to learn first.",
    )

    top_col, btn_col = st.columns([3, 1])
    with btn_col:
        st.button("Try an example", on_click=_load_example, use_container_width=True)

    col_job, col_me = st.columns(2, gap="large")
    with col_job:
        job_text = st.text_area(
            "The job posting", key=JOB_TEXT_KEY, height=230,
            placeholder="Paste the full job description here",
        )
    with col_me:
        my_text = st.text_area(
            "Your skills", key=MY_SKILLS_KEY, height=230,
            placeholder="Paste your resume text, or just list your skills and the courses you have taken",
        )

    if st.button("Check my match", type="primary"):
        st.session_state[MATCH_RUN_KEY] = True
    if not st.session_state.get(MATCH_RUN_KEY):
        st.info("Paste a job posting and your skills, then click Check my match. Or click Try an example.")
        return
    if not job_text.strip():
        st.warning("Paste a job posting first.")
        return

    tracked_df = run_query(
        """
        SELECT DISTINCT s.skill_id, s.canonical_name
        FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        """
    )
    tracked_df = tracked_df[~tracked_df["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]
    names = dict(zip(tracked_df["skill_id"], tracked_df["canonical_name"]))

    job_ids = extract_user_skills(job_text, tracked_df)
    if not job_ids:
        st.warning("No known skills found in that posting. Try pasting the full description, including the requirements section.")
        return
    my_ids = extract_user_skills(my_text, tracked_df) if my_text.strip() else set()

    demand = _market_demand()
    have = sorted((i for i in job_ids if i in my_ids), key=lambda i: -demand.get(i, 0))
    missing = sorted((i for i in job_ids if i not in my_ids), key=lambda i: -demand.get(i, 0))
    n_total = len(job_ids)

    # ---- Headline ----
    if my_text.strip():
        pct = len(have) / n_total * 100
        headline = f"You have {len(have)} of the {n_total} skills this job asks for."
        sub = "Learn the missing ones below, starting with the most common." if missing else "You cover every skill we could detect in this posting."
        track = (
            f'<div class="signal-track" style="height:14px;"><div class="signal-fill signal-fill-coverage" style="width:{pct:.0f}%"></div></div>'
        )
    else:
        headline = f"This job asks for {n_total} skills we can detect."
        sub = "Add your skills above and click Check my match to see how you compare."
        track = ""
    st.markdown(
        f"""
        <div class="answer-banner">
            <p class="answer-banner-label">Your match</p>
            <p class="answer-banner-text">{headline}</p>
            {track}
            <p class="answer-banner-sub">{sub}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Skill chips ----
    if my_text.strip():
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**You already have ({len(have)})**")
            chips = "".join(f'<span class="skill-chip skill-chip-have">{names[i]}</span>' for i in have) or "None yet."
            st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Missing ({len(missing)})**")
            chips = "".join(f'<span class="skill-chip skill-chip-missing">{names[i]}</span>' for i in missing) or "Nothing missing."
            st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)
    else:
        chips = "".join(f'<span class="skill-chip skill-chip-have">{names[i]}</span>' for i in sorted(job_ids, key=lambda i: -demand.get(i, 0)))
        st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)

    # ---- What to learn first ----
    if my_text.strip() and missing:
        st.markdown('<p class="section-eyebrow">Learn These First</p>', unsafe_allow_html=True)
        st.caption("Ordered by how often each skill appears across the 1,660 tech job postings we looked at, so the first ones help with the most jobs.")
        for rank, sid in enumerate(missing[:LEARN_FIRST_SHOWN], start=1):
            with st.container(border=True):
                left, right = st.columns([3, 2])
                with left:
                    st.markdown(
                        f'<div class="skill-card-head"><span class="skill-rank">{rank}</span>'
                        f'<span class="skill-card-name">{names[sid]}</span></div>'
                        f'<p class="skill-card-meta">Appears in {demand.get(sid, 0)*100:.0f}% of the postings we looked at</p>',
                        unsafe_allow_html=True,
                    )
                with right:
                    st.button(
                        f"Find courses on {names[sid]} →", key=f"match_courses_{int(sid)}",
                        on_click=jump_to_course_finder, args=(names[sid],), use_container_width=True,
                    )

    # ---- Copyable summary ----
    if my_text.strip():
        lines = [f"Job match: {len(have)} of {n_total} skills."]
        if have:
            lines.append("Have: " + ", ".join(names[i] for i in have))
        if missing:
            lines.append("To learn: " + ", ".join(names[i] for i in missing))
        st.markdown('<p class="section-eyebrow">Copy Your Results</p>', unsafe_allow_html=True)
        st.code("\n".join(lines), language=None)

    st.caption(
        "Skills are matched by name against a list of about 250 tools and technologies from the US Department of Labor's O*NET database. "
        "Soft skills and skills phrased in other words can be missed."
    )
