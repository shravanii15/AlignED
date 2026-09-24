"""sections/heatmap.py -- a visual grid of programs x skills, real
coverage percentages."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.database import run_query
from utils.layout import page_header


def render_heatmap():
    page_header(
        "🗺️", "Skill Coverage Heatmap",
        "<b>How to read this:</b> each cell shows what percent of a program's courses cover a skill. "
        "Darker blue = more covered. Most cells are blank/near-white -- that's the real finding, not a "
        "rendering issue: course descriptions rarely name specific tools by name (see the caption below).",
    )

    num_skills = st.slider("Number of skills to show (fewer = easier to read)", min_value=5, max_value=20, value=10)

    # Overall-market scope only (cluster_id IS NULL) -- gap_scores also
    # contains per-role-cluster rows now, and counting those here too
    # would count the same skill/program pair up to 9 extra times (once
    # per real role cluster), badly skewing "most commonly gapped."
    top_skills_df = run_query(
        """
        SELECT s.skill_id, s.canonical_name, COUNT(*) AS n_programs_gapped
        FROM gap_scores g JOIN skills s ON s.skill_id = g.skill_id
        WHERE g.cluster_id IS NULL
        GROUP BY g.skill_id ORDER BY n_programs_gapped DESC LIMIT ?
        """,
        (num_skills,),
    )
    programs_df = run_query("SELECT program_id, university FROM programs ORDER BY university")
    # Short labels (university only) instead of the full "university -- long
    # program name" string -- much easier to scan on a crowded axis.
    programs_df["short_label"] = programs_df["university"].str.replace("University of ", "U. ", regex=False)
    # De-duplicate universities that appear more than once (e.g. Georgia
    # Tech has 3 programs) by appending a short suffix.
    dupe_counts = {}
    short_labels = []
    for uni in programs_df["short_label"]:
        dupe_counts[uni] = dupe_counts.get(uni, 0) + 1
        short_labels.append(uni if dupe_counts[uni] == 1 else f"{uni} ({dupe_counts[uni]})")
    programs_df["short_label"] = short_labels

    # Pull TRUE coverage directly from the course/extraction data for
    # every program x skill pair, not just the ones that happened to
    # clear the significance test in gap_scores -- otherwise a program
    # that covers a skill a little (but not enough to be "significant")
    # gets shown identically to a program that covers it 0%, which is
    # misleading.
    coverage_df = run_query(
        """
        SELECT c.program_id, e.skill_id, COUNT(DISTINCT e.source_id) AS n_covering,
               (SELECT COUNT(*) FROM courses WHERE program_id = c.program_id) AS n_total
        FROM extractions e
        JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword'
          AND e.skill_id IN ({})
        GROUP BY c.program_id, e.skill_id
        """.format(",".join(str(s) for s in top_skills_df["skill_id"])),
    )

    matrix = pd.DataFrame(0.0, index=programs_df["short_label"], columns=top_skills_df["canonical_name"])
    program_label_by_id = dict(zip(programs_df["program_id"], programs_df["short_label"]))
    skill_name_by_id = dict(zip(top_skills_df["skill_id"], top_skills_df["canonical_name"]))
    for _, row in coverage_df.iterrows():
        label = program_label_by_id.get(row["program_id"])
        skill_name = skill_name_by_id.get(row["skill_id"])
        if label is not None and skill_name is not None and row["n_total"] > 0:
            matrix.loc[label, skill_name] = row["n_covering"] / row["n_total"]

    # Sort both axes by total coverage (descending) rather than leaving
    # them in arbitrary database order -- this pulls whatever real signal
    # exists toward the top-left corner instead of scattering it randomly
    # across the grid, which reads as a deliberately designed view rather
    # than a random dump of near-empty cells.
    matrix = matrix.loc[matrix.sum(axis=1).sort_values(ascending=False).index]
    matrix = matrix[matrix.sum(axis=0).sort_values(ascending=False).index]

    # Real, honest finding worth stating plainly: course catalog
    # descriptions rarely name specific tools the way job postings do, so
    # true coverage for these skills tops out in the single digits almost
    # everywhere. Locking the color scale to 0-100% would flatten all of
    # that into "uniform color" and hide the real (small) variation that
    # does exist -- so the scale is set to the actual data range instead,
    # with a sensible floor so it doesn't get overly sensitive.
    data_max = max(matrix.values.max(), 0.05)

    # A sequential white-to-blue scale, not a red/yellow/green diverging
    # one. Diverging scales are for data centered on a meaningful
    # midpoint ("bad" vs. "good"); this data is skewed almost entirely
    # near zero, so a diverging scale paints nearly the whole grid in
    # full-intensity "alarm" red -- technically accurate, but it reads
    # as a broken page rather than a real, calm finding. White-to-blue
    # instead makes 0% cells blank/neutral and lets actual coverage
    # stand out, which is a much more legible way to show "mostly
    # near-zero, with a few real pockets of coverage."
    text_matrix = [[f"{v*100:.0f}%" if v > 0 else "" for v in row] for row in matrix.values]

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values, x=matrix.columns, y=matrix.index,
            colorscale="Blues", zmin=0, zmax=data_max,
            text=text_matrix,
            texttemplate="%{text}", textfont={"size": 11, "color": "#1E293B"},
            xgap=3, ygap=3,  # thin gaps between cells so the grid reads as designed, not as a solid block
            colorbar=dict(title="Coverage", tickformat=".0%", thickness=14),
            hovertemplate="Program: %{y}<br>Skill: %{x}<br>Coverage: %{z:.1%}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(420, len(matrix.index) * 34),
        xaxis_tickangle=-35,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"This uses each program's real, full coverage rate (not just the significant-gap subset). "
        f"An honest finding on its own: even the best-covered program/skill pair here only reaches {data_max*100:.0f}% -- "
        f"course descriptions rarely name specific tools the way job postings do, which is why the color scale is "
        f"stretched to this data's real range instead of the full 0-100%, and why most cells are blank rather than colored."
    )
