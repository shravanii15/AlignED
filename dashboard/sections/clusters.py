"""sections/clusters.py -- how real job postings group into real-world
roles, with sample postings per cluster."""

import plotly.express as px
import streamlit as st

from services.database import run_query


def render_clusters():
    st.title("🧩 Role Clusters")
    st.markdown(
        """
        Real job postings were grouped by the actual role they describe (not
        job title alone) using AI-generated embeddings and k-means
        clustering, so curricula can be compared against what a role needs
        in general -- not one company's specific posting.
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
        st.caption(f"Best number of clusters chosen automatically via silhouette score: {silhouette:.4f}. See Methodology for why this number is honestly modest, and what it means.")

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
    st.subheader("See real postings inside a cluster")
    st.caption("Pulled straight from the sampled job postings -- a real sanity check, not just a label.")
    cluster_choice = st.selectbox("Choose a role cluster", clusters_df["role_label"])
    cluster_id = int(clusters_df[clusters_df["role_label"] == cluster_choice]["cluster_id"].iloc[0])
    sample_postings = run_query(
        """
        SELECT p.title, p.company FROM postings p
        JOIN posting_cluster_map pcm ON pcm.posting_id = p.posting_id
        WHERE pcm.cluster_id = ?
        LIMIT 8
        """,
        (cluster_id,),
    )
    for _, row in sample_postings.iterrows():
        st.write(f"• **{row['title']}** ({row['company']})")
