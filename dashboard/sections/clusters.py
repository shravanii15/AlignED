"""sections/clusters.py -- "Role Groups": how real job postings group
into broad role families, with sample postings per group.

Named "Role Groups" rather than "Role Clusters" on purpose: "clusters"
reads as a precise, mathematically-validated result, but the silhouette
score behind this grouping is honestly modest (0.08) -- job descriptions
genuinely overlap a lot across occupations (a "DevOps Engineer" and
"Cloud Engineer" posting share most of their vocabulary). "Role Groups"
sets the right expectation: broad, embedding-based groupings of similar
postings, not strict, validated occupational categories."""

import plotly.express as px
import streamlit as st

from services.database import run_query


def render_clusters():
    st.title("🧩 Role Groups")
    st.markdown(
        """
        Real job postings were grouped into broad role families using
        AI-generated embeddings and k-means clustering -- so curricula can
        be compared against what a role generally needs, not one
        company's specific posting.
        """
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
            f"**Read these as broad role families, not strict occupational categories.** "
            f"Silhouette score: {silhouette:.4f} -- honestly modest, because real job-posting "
            f"text overlaps heavily across related roles (a \"DevOps Engineer\" and \"Cloud Engineer\" "
            f"posting share most of their vocabulary). Use the postings browser below to sanity-check "
            f"any group yourself rather than taking the label at face value. Full discussion on the "
            f"Methodology page."
        )

    chart_col, pie_col = st.columns([3, 2])
    with chart_col:
        fig = px.bar(clusters_df, x="n_postings", y="role_label", orientation="h", labels={"n_postings": "Sampled postings", "role_label": "Role"})
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)
    with pie_col:
        fig_pie = px.pie(clusters_df, names="role_label", values="n_postings", hole=0.45)
        fig_pie.update_traces(textposition="inside", textinfo="percent")
        fig_pie.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")
    st.subheader("See real postings inside a role group")
    st.caption("Pulled straight from the sampled job postings -- a real sanity check, not just a label.")
    cluster_choice = st.selectbox("Choose a role group", clusters_df["role_label"])
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
    # Honest note: the 1,660-posting sample used for role grouping and
    # gap analysis (Kaggle historical dataset) doesn't include location,
    # salary, or posted-date fields -- only the small, separate live
    # Adzuna pipeline captures those. So most cards below will show just
    # title + company; any extra detail is shown automatically whenever
    # a posting actually has it, rather than a placeholder claiming data
    # that doesn't exist.
    for _, row in sample_postings.iterrows():
        details = []
        if row["location"]:
            details.append(f"📍 {row['location']}")
        if row["salary_min"] or row["salary_max"]:
            lo, hi = row["salary_min"], row["salary_max"]
            if lo and hi:
                details.append(f"💰 ${lo:,.0f}–${hi:,.0f}")
            else:
                details.append(f"💰 ${(lo or hi):,.0f}")
        if row["posted_date"]:
            details.append(f"📅 {row['posted_date']}")
        if details:
            st.markdown(f"**{row['title']}** — {row['company']}  \n{'  ·  '.join(details)}")
        else:
            st.write(f"• **{row['title']}** ({row['company']})")
