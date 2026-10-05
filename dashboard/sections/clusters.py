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


def render_clusters():
    page_header(
        "", "Job Families",
        "Job postings sorted into broad families of similar jobs, so programs can be compared against what a "
        "kind of job generally needs instead of one company's posting.",
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

    chart_col, pie_col = st.columns([3, 2])
    with chart_col:
        st.markdown('<p class="section-eyebrow">Postings per Family</p>', unsafe_allow_html=True)
        chart_df = clusters_df.sort_values("n_postings", ascending=True)
        fig = px.bar(chart_df, x="n_postings", y="role_label", orientation="h", labels={"n_postings": "Sampled postings", "role_label": ""})
        fig.update_traces(marker_color=BRAND)
        apply_chart_theme(fig, height=420)
        st.plotly_chart(fig, use_container_width=True)
    with pie_col:
        st.markdown('<p class="section-eyebrow">Share of Sample</p>', unsafe_allow_html=True)
        fig_pie = px.pie(clusters_df, names="role_label", values="n_postings", hole=0.55)
        fig_pie.update_traces(textposition="inside", textinfo="percent")
        apply_chart_theme(fig_pie, height=420)
        fig_pie.update_layout(showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

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
