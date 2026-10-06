"""sections/clusters.py: "Role Groups", how sampled job postings group into
broad role families, with sample postings per group.

Named "Role Groups" rather than "Role Clusters" on purpose: the silhouette
score behind the grouping is modest (0.08), because job descriptions
overlap heavily across related occupations. The name sets the right
expectation: broad, embedding-based groupings, not strict categories."""

import plotly.express as px
import streamlit as st

from services.database import run_query
from utils.charts import BRAND, apply_chart_theme
from utils.formatting import format_posting_details
from utils.layout import page_header
from utils.visuals import mini_bar


def render_clusters():
    page_header(
        "", "Job Families",
        "Job postings sorted into broad families of similar jobs, so programs can be compared against what a "
        "kind of job generally needs instead of one company's posting.",
        art="families", pills=("1,660 postings", "Grouped by similarity"),
    )

    clusters_df = run_query(
        """
        SELECT rc.cluster_id, rc.role_label, rc.silhouette_score, COUNT(pcm.posting_id) AS n_postings
        FROM role_clusters rc
        LEFT JOIN posting_cluster_map pcm ON pcm.cluster_id = rc.cluster_id
        GROUP BY rc.cluster_id
        ORDER BY n_postings DESC
        """
    )
    silhouette = clusters_df["silhouette_score"].iloc[0] if not clusters_df.empty else None
    if silhouette is not None:
        st.info(
            "These families are rough. Related jobs share a lot of wording, so some postings could fit more than one "
            "family. Browse the postings below to judge for yourself."
        )

        with st.expander("Technical note"):
            st.markdown(
                "Postings were embedded with a sentence-transformer model and grouped with k-means. "
                f"The silhouette score is modest ({silhouette:.2f}), which is expected when related roles use similar language."
            )

    total_postings = max(int(clusters_df["n_postings"].sum()), 1)
    top_skills = run_query(
        """
        SELECT pcm.cluster_id, s.canonical_name, COUNT(DISTINCT e.source_id) AS n
        FROM extractions e
        JOIN posting_cluster_map pcm ON pcm.posting_id = e.source_id
        JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        GROUP BY pcm.cluster_id, s.skill_id
        """
    )
    palette = ["#315CF5", "#1F9D68", "#7C3AED", "#E08A3C", "#0E7490", "#D94A4A", "#4C7DFF", "#B45309", "#475569", "#BE185D"]
    st.markdown('<p class="section-eyebrow">The Families</p>', unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for i, (_, fam) in enumerate(clusters_df.iterrows()):
        share = fam["n_postings"] / total_postings
        skills = top_skills[top_skills["cluster_id"] == fam["cluster_id"]].sort_values("n", ascending=False).head(4)
        chips = "".join(f'<span class="skill-chip skill-chip-have">{n}</span>' for n in skills["canonical_name"])
        color = palette[i % len(palette)]
        with cols[i % 3]:
            st.markdown(
                f"""
                <div class="vcard vcard-accent" style="border-top-color:{color}; margin-bottom:0.9rem;">
                    <p class="vcard-title">{fam["role_label"]}</p>
                    <p class="vcard-sub">{int(fam["n_postings"])} postings &middot; {share*100:.0f}% of the sample</p>
                    {mini_bar(share / (clusters_df["n_postings"].max() / total_postings), color)}
                    <p class="vcard-sub" style="margin-top:0.7rem !important;">Most asked for</p>
                    <div class="skill-chip-row">{chips or "No tracked skills"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<p class="section-eyebrow">Browse Postings in a Family</p>', unsafe_allow_html=True)
    cluster_choice = st.selectbox("Job family", clusters_df["role_label"])
    cluster_id = int(clusters_df[clusters_df["role_label"] == cluster_choice]["cluster_id"].iloc[0])
    sample_postings = run_query(
        """
        SELECT p.title, p.company, p.location, p.salary_min, p.salary_max, p.posted_date
        FROM postings p
        JOIN posting_cluster_map pcm ON pcm.posting_id = p.posting_id
        WHERE pcm.cluster_id = ?
        LIMIT 8
        """,
        (cluster_id,),
    )
    # Most sampled postings (Kaggle historical set) have no location,
    # salary or date; extra detail is shown only when a posting has it.
    for _, row in sample_postings.iterrows():
        details = format_posting_details(row)
        if details:
            st.markdown(f"**{row['title']}**, {row['company']}  \n{details}")
        else:
            st.markdown(f"**{row['title']}**, {row['company']}")
