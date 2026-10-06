"""sections/profile.py: "Build Your Profile". Paste your skills or resume
text and get best-matching roles, strengths and gaps for the top match,
example job openings, and a downloadable PDF career report."""

import pandas as pd
import streamlit as st

from services.database import run_query
from services.reports_pdf import build_profile_pdf_report
from utils.constants import AMBIGUOUS_GENERIC_TERMS, TOP_SKILLS_PER_CLUSTER
from utils.formatting import format_posting_details
from utils.layout import page_header
from utils.nav import PROFILE_RUN_KEY, PROFILE_TEXT_KEY
from utils.text import extract_user_skills
from utils.resume import resume_uploader
from utils.visuals import ring_svg


def render_profile_builder():
    page_header(
        "", "Which Jobs Fit Me",
        "Paste your skills, resume text, or courses taken. We match them against each family of jobs in the "
        "data and show the best fit, what to learn next, and example postings.",
        art="fit", pills=("Paste your skills", "Get job families"),
    )

    resume_uploader("Upload your resume (optional)", PROFILE_TEXT_KEY, "profile_resume_upload")
    user_text = st.text_area(
        "Your skills, resume text, or courses taken",
        key=PROFILE_TEXT_KEY,
        height=180,
        placeholder="e.g. I've taken courses in Python, statistics, and machine learning. Built a project using Docker and AWS...",
    )

    # The run flag persists in session state so results stay on screen when
    # the visitor clicks the PDF download (which reruns the script) or when
    # the Home page starts the plan with text already entered.
    if st.button("Find jobs that fit me", type="primary"):
        st.session_state[PROFILE_RUN_KEY] = True
    if not st.session_state.get(PROFILE_RUN_KEY):
        st.info("Paste your background above and click the button.")
        return

    if not user_text.strip():
        st.warning("Please paste some text first.")
        return

    tracked_df = run_query(
        """
        SELECT DISTINCT s.skill_id, s.canonical_name
        FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        """
    )
    tracked_df = tracked_df[~tracked_df["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]
    matched_skill_ids = extract_user_skills(user_text, tracked_df)

    if not matched_skill_ids:
        st.warning("No tracked skills matched. Try naming specific tools, languages or technologies (e.g. Python, SQL, Docker, Tableau).")
        return

    detected_names = tracked_df[tracked_df["skill_id"].isin(matched_skill_ids)]["canonical_name"].sort_values()
    st.markdown('<p class="section-eyebrow">Skills Detected in Your Text</p>', unsafe_allow_html=True)
    chips_html = "".join(f'<span class="skill-chip skill-chip-have">{name}</span>' for name in detected_names)
    st.markdown(f'<div class="skill-chip-row">{chips_html}</div>', unsafe_allow_html=True)

    # How well the user's skills overlap each role group's most in-demand
    # skills. This picks the best-fit role instead of asking the user to
    # guess one from a dropdown.
    cluster_skill_counts = run_query(
        """
        SELECT pcm.cluster_id, e.skill_id, COUNT(DISTINCT e.source_id) AS n
        FROM extractions e JOIN posting_cluster_map pcm ON pcm.posting_id = e.source_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        GROUP BY pcm.cluster_id, e.skill_id
        """
    )
    cluster_totals = run_query("SELECT cluster_id, COUNT(*) AS total FROM posting_cluster_map GROUP BY cluster_id")
    roles_df = run_query(
        "SELECT cluster_id, role_label FROM role_clusters WHERE role_label NOT LIKE 'Mixed%' AND role_label NOT LIKE 'Near-duplicate%'"
    )

    merged = cluster_skill_counts.merge(cluster_totals, on="cluster_id").merge(roles_df, on="cluster_id")
    merged["demand_rate"] = merged["n"] / merged["total"]
    # Inner join on purpose: tracked_df already excludes the generic,
    # keyword-ambiguous terms, so this removes them from the per-role
    # ranking instead of leaving them in with a blank name.
    merged = merged.merge(tracked_df, on="skill_id", how="inner")
    top_per_cluster = merged.sort_values("demand_rate", ascending=False).groupby("cluster_id").head(TOP_SKILLS_PER_CLUSTER)

    match_rows = []
    for cluster_id, group in top_per_cluster.groupby("cluster_id"):
        n_core_skills = len(group)
        overlap = int(group["skill_id"].isin(matched_skill_ids).sum())
        match_rows.append({
            "cluster_id": cluster_id,
            "role_label": group["role_label"].iloc[0],
            "skills_covered": overlap,
            "n_core_skills": n_core_skills,
            "match_score": overlap / n_core_skills,  # for ranking only, never shown as a percentage
        })
    role_matches_df = pd.DataFrame(match_rows).sort_values("match_score", ascending=False).reset_index(drop=True)

    best = role_matches_df.iloc[0]
    st.markdown(
        f"""
        <div class="result-hero">
            {ring_svg(best["match_score"], f'{int(best["skills_covered"])}/{int(best["n_core_skills"])}', "top skills covered", "#315CF5")}
            <div class="result-hero-text">
                <p class="result-hero-label">Your best fit</p>
                <p class="result-hero-title">{best["role_label"]}</p>
                <p class="result-hero-sub">You already mention {int(best["skills_covered"])} of the {int(best["n_core_skills"])} most requested skills for this kind of job. {len(matched_skill_ids)} skills were detected in your text.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-eyebrow">All Job Families, Ranked</p>', unsafe_allow_html=True)
    st.caption("Shows how many of a job family's most requested skills your text mentions. It is a simple count, not a score.")
    for _, row in role_matches_df.head(5).iterrows():
        pct = min(row["match_score"], 1.0) * 100
        st.markdown(
            f"""
            <div class="gap-compare-row">
                <div class="gap-compare-label" style="width:auto; min-width:220px; text-transform:none; letter-spacing:0; font-size:0.9rem !important;">{row['role_label']}</div>
                <div class="gap-bar-track"><div class="gap-bar-fill gap-bar-role" style="width:{pct:.1f}%"></div></div>
                <div class="gap-bar-value">{row['skills_covered']}/{row['n_core_skills']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    top_role = role_matches_df.iloc[0]
    top_cluster_id = int(top_role["cluster_id"])
    st.markdown(f'<p class="section-eyebrow">Deep Dive: {top_role["role_label"]}</p>', unsafe_allow_html=True)

    cluster_data = top_per_cluster[top_per_cluster["cluster_id"] == top_cluster_id]
    have_df = cluster_data[cluster_data["skill_id"].isin(matched_skill_ids)].sort_values("demand_rate", ascending=False)
    missing_df = cluster_data[~cluster_data["skill_id"].isin(matched_skill_ids)].sort_values("demand_rate", ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**You already show ({len(have_df)})**")
        if have_df.empty:
            st.write("No overlap yet with this role's top skills.")
        else:
            chips = "".join(
                f'<span class="skill-chip skill-chip-have">{row["canonical_name"]} &middot; {row["demand_rate"]*100:.0f}%</span>'
                for _, row in have_df.iterrows()
            )
            st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f"**Skills to learn next ({len(missing_df)})**")
        if missing_df.empty:
            st.write("You cover all of this role's top skills.")
        else:
            chips = "".join(
                f'<span class="skill-chip skill-chip-missing">{row["canonical_name"]} &middot; {row["demand_rate"]*100:.0f}%</span>'
                for _, row in missing_df.iterrows()
            )
            st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)
    st.caption("Percentages show how often each skill appears in this role's sampled postings.")

    sample_postings_df = run_query(
        """
        SELECT p.title, p.company, p.location, p.salary_min, p.salary_max, p.posted_date
        FROM postings p
        JOIN posting_cluster_map pcm ON pcm.posting_id = p.posting_id
        WHERE pcm.cluster_id = ? LIMIT 8
        """,
        (top_cluster_id,),
    )
    st.markdown('<p class="section-eyebrow">Example Postings for This Role</p>', unsafe_allow_html=True)
    # Most sampled postings (Kaggle historical set) have no location,
    # salary or date; extra detail is shown only when a posting has it.
    for _, row in sample_postings_df.iterrows():
        details = format_posting_details(row)
        if details:
            st.markdown(f"**{row['title']}**, {row['company']}  \n{details}")
        else:
            st.markdown(f"**{row['title']}**, {row['company']}")

    st.markdown("---")
    pdf_bytes = build_profile_pdf_report(role_matches_df, top_role["role_label"], have_df, missing_df, sample_postings_df)
    st.download_button(
        "Download my skill plan (PDF)", data=pdf_bytes,
        file_name="AlignED_My_Career_Report.pdf", mime="application/pdf",
    )

    st.caption(
        "Matching is simple keyword matching, the same method used for the full program analysis, so it can "
        "miss skills phrased differently. See Methodology."
    )
