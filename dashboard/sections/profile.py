"""sections/profile.py -- "Build Your Profile": paste your own
skills/resume text and get a personalized analysis -- best-matching real
job roles, strengths/gaps for the top match, real example job openings,
and a downloadable personalized PDF career report."""

import pandas as pd
import streamlit as st

from services.database import run_query
from services.reports_pdf import build_profile_pdf_report
from utils.constants import AMBIGUOUS_GENERIC_TERMS, TOP_SKILLS_PER_CLUSTER
from utils.text import extract_user_skills


def render_profile_builder():
    st.title("🙋 Build Your Profile")
    st.markdown(
        """
        Paste your current skills, resume text, or a list of courses you've taken.
        We'll match your background against **every real role in the job-market data**,
        show which one fits you best, and generate a personalized career report --
        including real example job openings for that role.
        """
    )

    user_text = st.text_area(
        "Your skills / resume text / courses taken",
        height=180,
        placeholder="e.g. I've taken courses in Python, statistics, and machine learning. Built a project using Docker and AWS...",
    )

    if not st.button("🔍 Find my best-matching roles", type="primary"):
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
        st.warning("We couldn't match any tracked skills in what you pasted -- try naming specific tools/languages/technologies (e.g. Python, SQL, Docker, Tableau).")
        return

    # Compute how well the user's skills overlap with each real role's
    # most in-demand skills -- this is what "auto-detects" the best-fit
    # role instead of asking the user to guess one from a dropdown.
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
    # Inner join on purpose: tracked_df has already excluded the generic,
    # keyword-ambiguous terms, so an inner join here removes those skills
    # from the per-role ranking entirely, instead of a left join leaving
    # them in with a blank name (which would still let them occupy a
    # "top skill" slot).
    merged = merged.merge(tracked_df, on="skill_id", how="inner")
    top_per_cluster = merged.sort_values("demand_rate", ascending=False).groupby("cluster_id").head(TOP_SKILLS_PER_CLUSTER)

    match_rows = []
    for cluster_id, group in top_per_cluster.groupby("cluster_id"):
        overlap = group["skill_id"].isin(matched_skill_ids).sum()
        match_rows.append({
            "cluster_id": cluster_id,
            "role_label": group["role_label"].iloc[0],
            "match_score": overlap / len(group),
        })
    role_matches_df = pd.DataFrame(match_rows).sort_values("match_score", ascending=False).reset_index(drop=True)

    st.markdown("---")
    st.subheader("🎯 Your best-matching roles")
    for _, row in role_matches_df.head(5).iterrows():
        st.write(f"**{row['role_label']}** -- {row['match_score']*100:.0f}% match")
        st.progress(min(row["match_score"], 1.0))

    top_role = role_matches_df.iloc[0]
    top_cluster_id = int(top_role["cluster_id"])
    st.markdown("---")
    st.subheader(f"Deep dive: {top_role['role_label']}")

    cluster_data = top_per_cluster[top_per_cluster["cluster_id"] == top_cluster_id]
    have_df = cluster_data[cluster_data["skill_id"].isin(matched_skill_ids)].sort_values("demand_rate", ascending=False)
    missing_df = cluster_data[~cluster_data["skill_id"].isin(matched_skill_ids)].sort_values("demand_rate", ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**✅ Your strengths ({len(have_df)})**")
        for _, row in have_df.iterrows():
            st.write(f"🟢 {row['canonical_name']} -- in {row['demand_rate']*100:.0f}% of postings")
        if have_df.empty:
            st.write("No overlap yet with this role's top skills.")
    with col2:
        st.markdown(f"**🔴 Skills to prioritize ({len(missing_df)})**")
        for _, row in missing_df.iterrows():
            st.write(f"🔴 {row['canonical_name']} -- in {row['demand_rate']*100:.0f}% of postings")
        if missing_df.empty:
            st.write("Great coverage of this role's top skills!")

    sample_postings_df = run_query(
        """
        SELECT p.title, p.company FROM postings p
        JOIN posting_cluster_map pcm ON pcm.posting_id = p.posting_id
        WHERE pcm.cluster_id = ? LIMIT 8
        """,
        (top_cluster_id,),
    )
    st.markdown("---")
    st.subheader("💼 Example real job openings matching this role")
    st.caption("Pulled directly from the sampled job postings -- real listings, not generated examples.")
    for _, row in sample_postings_df.iterrows():
        st.write(f"• **{row['title']}** ({row['company']})")

    st.markdown("---")
    pdf_bytes = build_profile_pdf_report(role_matches_df, top_role["role_label"], have_df, missing_df, sample_postings_df)
    st.download_button(
        "⬇️ Download my personalized career report (PDF)", data=pdf_bytes,
        file_name="AlignED_My_Career_Report.pdf", mime="application/pdf",
    )

    st.caption(
        "This uses simple keyword matching, the same fast method used for the full-scale program analysis "
        "elsewhere in this project -- it can miss skills phrased differently than expected. See Methodology for details."
    )
