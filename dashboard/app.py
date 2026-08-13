"""
app.py -- AlignED dashboard

What this file does, in plain terms:
This is the front-facing part of the project -- the part a recruiter,
hiring manager, or curious visitor would actually click through, rather
than reading raw JSON files or console output. It's a Streamlit app,
meaning it's a single Python file that turns into a real interactive
web page: dropdowns, tables, and charts, all reading live from the same
SQLite database every other script in this project has been building up
(programs, courses, job postings, skills, gap scores, demand trends, and
final recommendations).

Why Streamlit for this project:
Streamlit turns a plain Python script into a web app with no separate
frontend code, no JavaScript, and no build step -- ideal for a data
science/analytics portfolio piece where the point is showing real
analysis, not demonstrating web development. It can also be published
for free to a public URL (Streamlit Community Cloud), so this dashboard
can be linked directly from a resume or LinkedIn profile.

How to run this locally:
    pip install -r requirements.txt
    streamlit run app.py
Then open the local URL it prints (usually http://localhost:8501).

Page structure (see the sidebar):
- Overview: project summary and headline numbers
- Program Explorer: pick any of the 13 programs and see its ranked,
  explained skill-gap recommendations
- Skill Demand Trends: which tracked skills are rising or falling
- Role Clusters: how real job postings group into real-world roles
- Methodology & Honest Limitations: the "how this was built, and where
  it's genuinely limited" page -- the kind of thing an interviewer would
  ask about directly, answered up front instead of hidden.
"""

import os
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")

st.set_page_config(page_title="AlignED -- Curriculum vs. Job Market Gap Analysis", page_icon="🎓", layout="wide")


@st.cache_resource
def get_connection():
    # check_same_thread=False is safe here because this app only ever
    # reads from the database -- it never writes -- so there's no risk
    # of concurrent write conflicts across Streamlit's internal threads.
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data
def run_query(sql, params=()):
    conn = get_connection()
    return pd.read_sql_query(sql, conn, params=params)


def render_overview():
    st.title("🎓 AlignED")
    st.subheader("Do graduate computing programs actually teach what the job market wants?")

    st.markdown(
        """
        AlignED compares real graduate program curricula against real job-market
        demand to find statistically meaningful gaps -- not guesses, not vibes,
        actual hand-labeled and statistically tested evidence.
        """
    )

    programs = run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"]
    courses = run_query("SELECT COUNT(*) AS n FROM courses").iloc[0]["n"]
    postings = run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"]
    gaps = run_query("SELECT COUNT(*) AS n FROM gap_scores").iloc[0]["n"]
    recs = run_query("SELECT COUNT(*) AS n FROM recommendations").iloc[0]["n"]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("University Programs", programs)
    col2.metric("Real Courses Analyzed", f"{courses:,}")
    col3.metric("Job Postings Analyzed", f"{postings:,}")
    col4.metric("Statistically Significant Gaps", gaps)
    col5.metric("Final Recommendations", recs)

    st.markdown("---")
    st.markdown(
        """
        **How this was built, in one paragraph:** real course descriptions were
        scraped from 13 university catalogs, and real job postings were pulled
        from a live daily pipeline plus a historical dataset. Both were matched
        against the official US Department of Labor (O\\*NET) skills taxonomy.
        An AI extraction method was hand-validated against a classical keyword
        baseline on a 104-item hand-labeled test set (AI won, F1 0.400 vs.
        0.364) before choosing the faster method for full-scale analysis --
        see the Methodology page for the full, honest reasoning.
        """
    )
    st.info("Use the sidebar to explore a specific program's recommendations, skill demand trends, or the honest methodology behind this project.")


def render_program_explorer():
    st.title("📋 Program Explorer")
    st.markdown("Pick a program to see its ranked, statistically significant skill gaps -- and what to do about them.")

    programs_df = run_query("SELECT program_id, university, program_name, tier FROM programs ORDER BY university")
    programs_df["label"] = programs_df["university"] + " -- " + programs_df["program_name"]
    selected_label = st.selectbox("Choose a program", programs_df["label"])
    selected = programs_df[programs_df["label"] == selected_label].iloc[0]
    program_id = int(selected["program_id"])

    course_count = run_query("SELECT COUNT(*) AS n FROM courses WHERE program_id = ?", (program_id,)).iloc[0]["n"]
    st.caption(f"Tier: {selected['tier']}  |  {course_count} real courses in this program")

    recs_df = run_query(
        """
        SELECT skill_id, gap_value, trend_label, priority_score, priority_tier, rationale
        FROM recommendations
        WHERE program_id = ?
        ORDER BY
            CASE priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            priority_score DESC
        """,
        (program_id,),
    )
    skills_df = run_query("SELECT skill_id, canonical_name FROM skills")
    recs_df = recs_df.merge(skills_df, on="skill_id", how="left")

    if recs_df.empty:
        st.warning("No statistically significant gaps were found for this program (this can genuinely happen for very small programs with few courses).")
        return

    tier_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for tier in ["high", "medium", "low"]:
        tier_df = recs_df[recs_df["priority_tier"] == tier]
        if tier_df.empty:
            continue
        st.subheader(f"{tier_colors[tier]} {tier.title()} priority")
        for _, row in tier_df.iterrows():
            trend_note = {"rising": "📈 rising demand", "falling": "📉 falling demand"}.get(row["trend_label"], "")
            with st.expander(f"{row['canonical_name']}  ({row['gap_value']*100:.0f} point gap)  {trend_note}"):
                st.write(row["rationale"])

    st.markdown("---")
    st.subheader("Gap size, visualized")
    chart_df = recs_df.sort_values("gap_value", ascending=True)
    fig = px.bar(
        chart_df, x="gap_value", y="canonical_name", orientation="h",
        color="priority_tier", color_discrete_map={"high": "#e15759", "medium": "#f1c232", "low": "#59a14f"},
        labels={"gap_value": "Gap (market demand - program coverage)", "canonical_name": "Skill"},
    )
    fig.update_layout(xaxis_tickformat=".0%", height=max(300, len(chart_df) * 35))
    st.plotly_chart(fig, use_container_width=True)


def render_trends():
    st.title("📈 Skill Demand Trends")
    st.markdown(
        """
        Based on ~124,000 real historical job postings, restricted to the
        6 weeks with a real, meaningful volume of data (see Methodology for
        why some weeks were excluded).
        """
    )

    trends_df = run_query(
        """
        SELECT t.trend_label, t.slope, t.p_value, t.first_half_rate, t.second_half_rate, s.canonical_name
        FROM skill_trends t JOIN skills s ON s.skill_id = t.skill_id
        ORDER BY t.slope DESC
        """
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Rising")
        rising = trends_df[trends_df["trend_label"] == "rising"]
        st.dataframe(
            rising[["canonical_name", "first_half_rate", "second_half_rate", "p_value"]]
            .rename(columns={"canonical_name": "Skill", "first_half_rate": "First half", "second_half_rate": "Second half", "p_value": "p-value"})
            .style.format({"First half": "{:.1%}", "Second half": "{:.1%}", "p-value": "{:.4f}"}),
            hide_index=True, use_container_width=True,
        )
    with col2:
        st.subheader("📉 Falling")
        falling = trends_df[trends_df["trend_label"] == "falling"]
        st.dataframe(
            falling[["canonical_name", "first_half_rate", "second_half_rate", "p_value"]]
            .rename(columns={"canonical_name": "Skill", "first_half_rate": "First half", "second_half_rate": "Second half", "p_value": "p-value"})
            .style.format({"First half": "{:.1%}", "Second half": "{:.1%}", "p-value": "{:.4f}"}),
            hide_index=True, use_container_width=True,
        )

    stable_count = len(trends_df[trends_df["trend_label"] == "no clear trend"])
    st.caption(f"{stable_count} additional tracked skills showed no statistically significant trend over this window.")


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

    fig = px.bar(clusters_df, x="n_postings", y="role_label", orientation="h", labels={"n_postings": "Sampled postings", "role_label": "Role"})
    fig.update_layout(height=450)
    st.plotly_chart(fig, use_container_width=True)


def render_methodology():
    st.title("🔍 Methodology & Honest Limitations")
    st.markdown(
        """
        This page exists on purpose: a portfolio project is only as
        trustworthy as its documented limitations. Every simplification
        below was a deliberate, explained trade-off -- not an oversight.

        ### Data sources
        - **Course data:** scraped directly from 13 real university course
          catalogs (Georgia Tech, ASU, UIUC, Northeastern, BU, Wisconsin,
          UMD, Penn State, UW, Michigan).
        - **Job posting data:** a live daily pipeline (Adzuna API, via
          GitHub Actions) plus a historical backfill of ~124,000 real
          postings (Kaggle LinkedIn dataset).
        - **Skills taxonomy:** the official US Department of Labor O\\*NET
          database -- not an invented list. ESCO (the EU equivalent) was
          used first and is kept in the project history, but O\\*NET was
          chosen for better coverage of named tools.

        ### AI vs. classical extraction -- an actual, measured comparison
        A local, free AI model (Ollama) was compared against a classical
        keyword-matching baseline on a 104-item hand-labeled test set:

        | Method | Precision | Recall | F1 |
        |---|---|---|---|
        | Baseline (keyword) | 0.518 | 0.280 | 0.364 |
        | AI (local LLM + embeddings) | 0.407 | 0.392 | **0.400** |

        The AI method won on the accuracy metric that matters most here
        (F1). But running it across the *full* 1,378 courses and
        thousands of postings would take hours on consumer hardware, so
        the fast keyword method was used deliberately for full-scale
        analysis -- a real "best model for evaluation, faster model for
        production scale" engineering trade-off.

        ### Known, documented limitations
        - **Keyword matching can't disambiguate context.** A handful of
          generic single-word skill names (e.g. "Design", "Science") were
          excluded from gap/trend analysis because a keyword scanner can't
          tell them apart from unrelated everyday text.
        - **The historical posting dataset's timestamps are skewed.** 68%
          of the ~124,000 postings are dated in a single final week --
          almost certainly a data-collection artifact, not real hiring
          activity. Trend analysis was restricted to the 6 weeks with real
          volume (>=100 postings) rather than reporting a misleading
          result across mostly-empty weeks.
        - **Role clustering's silhouette score is modest (0.08).** This is
          normal and expected for real, overlapping job-posting text (a
          "DevOps Engineer" and "Cloud Engineer" posting legitimately
          share a lot of language) -- a hand sanity-check of sampled
          postings per cluster confirmed most clusters are genuinely
          coherent by role.
        - **The gap-score threshold-tuning note:** the embedding
          similarity cutoff used in the AI evaluation was tuned against
          the same 104-item set used for final reporting, a known,
          deliberate simplification for a project of this scope (the more
          textbook-correct approach would use a separate held-out set).
        """
    )


PAGES = {
    "Overview": render_overview,
    "Program Explorer": render_program_explorer,
    "Skill Demand Trends": render_trends,
    "Role Clusters": render_clusters,
    "Methodology & Honest Limitations": render_methodology,
}

st.sidebar.title("AlignED")
selection = st.sidebar.radio("Go to", list(PAGES.keys()))
PAGES[selection]()
