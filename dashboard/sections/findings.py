"""sections/findings.py: the Key Findings page.

Turns the 13 programs' gap results into three plain-language findings, each with its numbers and its caveat:
  1. Which skills are missing in almost every program.
  2. How the 13 programs compare (with what kind of course list each one is).
  3. What course descriptions mention most, as the contrast.

Everything is read from the same tables as the rest of the app, overall-market scope only, so nothing here
introduces a new number."""

import plotly.graph_objects as go
import streamlit as st

from services.database import run_query
from utils.charts import COVERAGE_GREEN, GAP_RED, apply_chart_theme
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.formatting import program_label
from utils.layout import page_header
from utils.visuals import stat_tiles

TOP_SKILLS_SHOWN = 10
# What kind of course list each corpus is (see docs/DATA_PROVENANCE.md). A gap against a department
# catalog is not the same claim as a gap against a program's own course list.
CORPUS_KIND = {
    "MS Analytics (OMS Analytics)": "Program course list",
    "MS Cybersecurity (OMS Cybersecurity)": "Program course list",
    "MS Computer Science (main CS catalog)": "Department catalog",
    "Online Master of Computer Science (MCS)": "Small sample",
    "MS Computer Science / MCS-DS (CS course catalog)": "Department catalog",
    "MS Computer Science (Align / CS catalog)": "Department catalog",
    "MS Computer Science (graduate CS courses)": "Graduate course list",
    "MS Computer Sciences / MS Data Science (elective pool)": "Elective pool",
    "MS Computer Science (CMSC catalog)": "Department catalog",
    "Cybersecurity (ENPM catalog)": "Department catalog",
    "MS Data Analytics (DAAN)": "Program course list",
    "MSCS / MS Data Science (CSE catalog)": "Department catalog",
    "MS Computer Science and Engineering (EECS catalog)": "Department catalog",
}


def render_findings():
    page_header(
        "", "Key Findings",
        "The main results across all 13 programs, in plain language. Each one comes with what it does and does not show.",
        art="grid", pills=("13 programs", "Overall job market"),
    )

    n_programs = int(run_query("SELECT COUNT(*) AS n FROM programs").iloc[0]["n"])
    skills_df = run_query(
        """
        SELECT s.canonical_name AS skill, COUNT(*) AS n_programs, AVG(g.gap_value) AS avg_gap,
               AVG(g.market_demand_rate) AS demand, AVG(g.program_coverage_rate) AS coverage
        FROM gap_scores g JOIN skills s ON s.skill_id = g.skill_id
        WHERE g.cluster_id IS NULL
        GROUP BY g.skill_id ORDER BY n_programs DESC, avg_gap DESC
        """
    )
    skills_df = skills_df[~skills_df["skill"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]
    programs_df = run_query(
        """
        SELECT p.program_id, p.university, p.program_name,
               (SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses,
               COUNT(g.skill_id) AS n_gaps, MAX(g.gap_value) AS biggest_gap
        FROM programs p LEFT JOIN gap_scores g ON g.program_id = p.program_id AND g.cluster_id IS NULL
        GROUP BY p.program_id
        """
    )
    if skills_df.empty or programs_df.empty:
        st.info("No gap results are available yet.")
        return

    n_total_gaps = int(programs_df["n_gaps"].sum())
    widespread = int((skills_df["n_programs"] >= n_programs * 0.75).sum())
    stat_tiles([
        (str(n_total_gaps), "significant gaps across programs"),
        (str(widespread), f"skills missing in {int(n_programs * 0.75)}+ of {n_programs} programs"),
        (f"{skills_df.iloc[0]['avg_gap']*100:.0f} pts", f"typical gap for {skills_df.iloc[0]['skill']}"),
    ])

    # ---- Finding 1 ----
    st.markdown('<p class="section-eyebrow">Finding 1 · Some skills are missing almost everywhere</p>', unsafe_allow_html=True)
    top = skills_df.head(TOP_SKILLS_SHOWN).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["n_programs"], y=top["skill"], orientation="h", marker_color=GAP_RED,
        text=[f"{n} of {n_programs}" for n in top["n_programs"]], textposition="outside",
        customdata=[[d * 100, c * 100, g * 100] for d, c, g in zip(top["demand"], top["coverage"], top["avg_gap"])],
        hovertemplate="%{y}<br>Significant gap in %{x} programs<br>Employers: %{customdata[0]:.0f}% of postings"
                      "<br>Courses: %{customdata[1]:.1f}% of descriptions<extra></extra>",
    ))
    fig.update_xaxes(range=[0, n_programs + 1.5], title="Programs where the skill is a significant gap")
    st.plotly_chart(apply_chart_theme(fig, height=380), use_container_width=True)
    st.caption(
        "Hands-on tools and languages lead the list. Course descriptions rarely name specific tools, so part of this "
        "is how catalogs are written, not only what is taught. Read it as where to look, not as proof of a teaching failure."
    )

    # ---- Finding 2 ----
    st.markdown('<p class="section-eyebrow">Finding 2 · How the 13 programs compare</p>', unsafe_allow_html=True)
    programs_df["label"] = [program_label(u, p) for u, p in zip(programs_df["university"], programs_df["program_name"])]
    programs_df["kind"] = programs_df["program_name"].map(CORPUS_KIND).fillna("Course list")
    programs_df = programs_df.sort_values("n_gaps", ascending=False)
    rows = [
        {
            "Program": r["label"], "Kind of course list": r["kind"], "Courses": int(r["n_courses"]),
            "Significant gaps": int(r["n_gaps"]), "Largest gap (pts)": f"{r['biggest_gap']*100:.0f}" if r["n_gaps"] else "-",
            "Note": "Small corpus, read with care" if r["n_courses"] < 30 else "",
        }
        for _, r in programs_df.iterrows()
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        "More gaps does not mean a worse program. A department catalog lists many courses and a small sample lists few, "
        "and a gap against a broad catalog means the catalog does not mention the skill. The programs with no gaps have only 5 to 19 "
        "courses, so the test has little power to find any. Compare programs of the same kind first."
    )

    # ---- Finding 3 ----
    st.markdown('<p class="section-eyebrow">Finding 3 · What course descriptions do mention</p>', unsafe_allow_html=True)
    covered = run_query(
        """
        SELECT s.canonical_name AS skill, COUNT(DISTINCT e.source_id) AS n_courses
        FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword'
        GROUP BY e.skill_id ORDER BY n_courses DESC LIMIT 25
        """
    )
    covered = covered[~covered["skill"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)].head(8)
    total_courses = int(programs_df["n_courses"].sum())
    fig2 = go.Figure(go.Bar(
        x=covered["n_courses"][::-1] / total_courses * 100, y=covered["skill"][::-1], orientation="h", marker_color=COVERAGE_GREEN,
        text=[f"{n / total_courses * 100:.0f}%" for n in covered["n_courses"][::-1]], textposition="outside",
    ))
    fig2.update_xaxes(title="Share of all 1,378 course descriptions that name the skill", ticksuffix="%")
    st.plotly_chart(apply_chart_theme(fig2, height=330), use_container_width=True)
    st.caption(
        "The contrast: courses name broad subjects, while job postings name tools. The skill list used here (O*NET) has no "
        "entry for subjects such as machine learning, so those do not appear on either side."
    )

    with st.expander("What these findings do not show"):
        st.markdown(
            f"""
            - **Not teaching quality.** A skill counts when its name appears in a public course description.
            - **Not the whole job market.** Demand is measured in a balanced sample of {int(run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]['n']):,} postings.
            - **Not equal corpora.** Programs differ in what their course list covers (see the table above and the Methodology page).
            - **Not a trend.** No demand trend held up after correcting for multiple tests.
            """
        )
