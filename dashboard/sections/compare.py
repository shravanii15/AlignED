"""sections/compare.py: see 2-3 programs' top gaps side by side."""

import pandas as pd
import plotly.express as px
import streamlit as st

from services.database import run_query
from utils.charts import TIER_COLOR_MAP, apply_chart_theme
from utils.formatting import program_label
from utils.layout import page_header
from utils.visuals import mini_bar


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
            max_gap = max(float(recs["gap_value"].max()), 0.01) if not recs.empty else 0.01
            rows_html = "".join(
                f'<div class="vcard-row"><span class="vcard-name">{r["canonical_name"]}</span>'
                f'{mini_bar(r["gap_value"] / max_gap, TIER_COLOR_MAP.get(r["priority_tier"], "#667085"))}'
                f'<span class="vcard-val">{r["gap_value"]*100:.0f} pts</span></div>'
                for _, r in recs.iterrows()
            ) or "<p>No significant gaps found.</p>"
            st.markdown(
                f"""
                <div class="vcard vcard-accent">
                    <p class="signal-eyebrow">{prog["university"]}</p>
                    <p class="vcard-title">{prog["program_name"]}</p>
                    <p class="vcard-sub">{course_count} courses analyzed</p>
                    {rows_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    nonempty = [set(r["canonical_name"]) for r in all_gap_rows if not r.empty]
    if len(nonempty) >= 2:
        shared = sorted(set.intersection(*nonempty))
        st.markdown("<br>", unsafe_allow_html=True)
        if shared:
            chips = "".join(f'<span class="skill-chip skill-chip-missing">{n}</span>' for n in shared)
            st.markdown(
                f'<div class="result-hero"><div class="result-hero-text"><p class="result-hero-label">In common</p>'
                f'<p class="result-hero-title">{len(shared)} top gaps show up in every program you picked.</p>'
                f'<div class="skill-chip-row">{chips}</div></div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("These programs have no top gaps in common, so they differ in what they leave out.")

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
