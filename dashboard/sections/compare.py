"""sections/compare.py -- see 2-3 programs' top gaps side by side."""

import pandas as pd
import plotly.express as px
import streamlit as st

from services.database import run_query


def render_compare():
    st.title("⚖️ Compare Programs")
    st.markdown("Pick 2-3 programs to see their top skill gaps side by side.")

    programs_df = run_query("SELECT program_id, university, program_name FROM programs ORDER BY university")
    programs_df["label"] = programs_df["university"] + " -- " + programs_df["program_name"]

    chosen_labels = st.multiselect(
        "Choose programs to compare (2-3 recommended)",
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
        recs = run_query(
            "SELECT skill_id, gap_value, priority_tier FROM recommendations WHERE program_id = ? ORDER BY priority_score DESC LIMIT 8",
            (program_id,),
        ).merge(skills_df, on="skill_id", how="left")
        recs["program_label"] = prog["label"]
        all_gap_rows.append(recs)

        with col:
            st.subheader(prog["university"])
            st.caption(f"{prog['program_name']}  |  {course_count} courses")
            if recs.empty:
                st.write("No significant gaps found.")
            else:
                for _, row in recs.iterrows():
                    tier_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(row["priority_tier"], "")
                    st.write(f"{tier_icon} **{row['canonical_name']}** -- +{row['gap_value']*100:.0f} pts")

    combined = pd.concat(all_gap_rows, ignore_index=True) if all_gap_rows else pd.DataFrame()
    if not combined.empty:
        st.markdown("---")
        st.subheader("Side-by-side gap sizes")
        fig = px.bar(
            combined, x="canonical_name", y="gap_value", color="program_label", barmode="group",
            labels={"canonical_name": "Skill", "gap_value": "Gap (market demand - coverage)", "program_label": "Program"},
        )
        fig.update_layout(yaxis_tickformat=".0%", height=450)
        st.plotly_chart(fig, use_container_width=True)
