"""sections/compare.py: see 2-3 programs' top gaps side by side."""

import pandas as pd
import plotly.express as px
import streamlit as st

from services.database import run_query
from utils.charts import TIER_COLOR_MAP, apply_chart_theme
from utils.formatting import program_label
from utils.layout import page_header


def render_compare():
    page_header("", "Compare Programs", "Pick 2 or 3 programs to see their largest skill gaps against the same job-market sample.", art="compare", pills=("2 to 3 programs", "Same job data"))

    programs_df = run_query("SELECT program_id, university, program_name FROM programs ORDER BY university")
    programs_df["label"] = [program_label(u, p) for u, p in zip(programs_df["university"], programs_df["program_name"])]

    chosen_labels = st.multiselect(
        "Programs to compare",
        programs_df["label"],
        default=list(programs_df["label"].iloc[:2]),
    )
    if len(chosen_labels) < 2:
        st.info("Pick at least 2 programs to compare.")
        return

    chosen = programs_df[programs_df["label"].isin(chosen_labels)]
    skills_df = run_query("SELECT skill_id, canonical_name FROM skills")

    cols = st.columns(len(chosen))
    all_gap_rows = []
    for col, (_, prog) in zip(cols, chosen.iterrows()):
        program_id = int(prog["program_id"])
        course_count = run_query("SELECT COUNT(*) AS n FROM courses WHERE program_id = ?", (program_id,)).iloc[0]["n"]
        # Overall-market scope only (cluster_id IS NULL) keeps the
        # side-by-side comparison like-for-like across programs.
        recs = run_query(
            "SELECT skill_id, gap_value, priority_tier FROM recommendations WHERE program_id = ? AND cluster_id IS NULL ORDER BY priority_score DESC LIMIT 8",
            (program_id,),
        ).merge(skills_df, on="skill_id", how="left")
        recs["program_label"] = prog["label"]
        all_gap_rows.append(recs)

        with col:
            with st.container(border=True):
                st.markdown(f'<p class="signal-eyebrow">{prog["university"]}</p>', unsafe_allow_html=True)
                st.markdown(f'<p class="signal-title">{prog["program_name"]}</p>', unsafe_allow_html=True)
                st.caption(f"{course_count} courses analyzed")
                if recs.empty:
                    st.write("No significant gaps found.")
                else:
                    for _, row in recs.iterrows():
                        color = TIER_COLOR_MAP.get(row["priority_tier"], "#667085")
                        st.markdown(
                            f'<div class="compare-row"><span class="compare-skill">{row["canonical_name"]}</span>'
                            f'<span class="compare-gap" style="color:{color} !important;">+{row["gap_value"]*100:.0f} pts</span></div>',
                            unsafe_allow_html=True,
                        )

    combined = pd.concat([r for r in all_gap_rows if not r.empty], ignore_index=True) if any(not r.empty for r in all_gap_rows) else pd.DataFrame()
    if not combined.empty:
        st.markdown('<p class="section-eyebrow">Gap Sizes Side by Side</p>', unsafe_allow_html=True)
        fig = px.bar(
            combined, x="canonical_name", y="gap_value", color="program_label", barmode="group",
            labels={"canonical_name": "", "gap_value": "Gap (market demand minus coverage)", "program_label": ""},
        )
        fig.update_layout(yaxis_tickformat=".0%")
        apply_chart_theme(fig, height=440)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True)
        st.plotly_chart(fig, use_container_width=True)
