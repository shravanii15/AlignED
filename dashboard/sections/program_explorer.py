"""sections/program_explorer.py: the "Skill Gaps" page. Pick a program and a
kind of job, get the top skills employers ask for that the program's course
descriptions do not mention, each with a button to find courses that teach
it. The statistics behind every skill sit in a collapsed "How we know"
panel, and the full list plus Excel/PDF downloads are below the answer.

Gap scoring and recommendations exist at two scopes: the overall market
(every sampled posting) and per job family (postings mapped to one role
cluster). The two are independently computed, not the same numbers
relabeled.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.database import run_query
from services.reports_excel import build_excel_report
from services.reports_pdf import build_pdf_report
from utils.charts import TIER_COLOR_MAP, apply_chart_theme
from utils.formatting import evidence_strength, program_label, safe_filename
from utils.layout import page_header
from services.skill_picture import market_picture
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.visuals import stat_tiles
from utils.nav import EXPLORER_PROGRAM_KEY, EXPLORER_ROLE_KEY, jump_to_course_finder

OVERALL_MARKET_LABEL = "Overall market (all sampled postings)"
RISING_BOOST = 1.5     # kept in sync with scripts/gap_analysis/generate_recommendations.py
FALLING_PENALTY = 0.7  # kept in sync with scripts/gap_analysis/generate_recommendations.py
TOP_SKILLS_SHOWN = 5


def _skill_card(row, rank, course_count, scope_total_postings, key_prefix):
    """One skill gap as a compact card: name, courses-vs-postings bars, a
    plain sentence, a 'find courses' action, and the statistics collapsed."""
    trend_note = {"rising": "demand rising", "falling": "demand falling"}.get(row["trend_label"], "")
    cov_pct = row["program_coverage_rate"] * 100
    dem_pct = row["market_demand_rate"] * 100
    max_pct = max(cov_pct, dem_pct, 1)
    cov_text = "none named" if cov_pct == 0 else ("<1%" if cov_pct < 1 else f"{cov_pct:.1f}%")
    meta = f"{row['gap_value']*100:.0f}-point gap  ·  evidence: {evidence_strength(row['q_value']).lower()}"
    if trend_note:
        meta += f"  ·  {trend_note}"

    with st.container(border=True):
        st.markdown(
            f'<div class="skill-card-head"><span class="skill-rank">{rank}</span>'
            f'<span class="skill-card-name">{row["canonical_name"]}</span></div>'
            f'<p class="skill-card-meta">{meta}</p>',
            unsafe_allow_html=True,
        )
        st.write(row["rationale"])
        st.markdown(
            f"""
            <div class="gap-compare">
                <div class="gap-compare-row">
                    <div class="gap-compare-label">Courses</div>
                    <div class="gap-bar-track"><div class="gap-bar-fill gap-bar-curriculum" style="width:{cov_pct/max_pct*100:.1f}%"></div></div>
                    <div class="gap-bar-value">{cov_text}</div>
                </div>
                <div class="gap-compare-row">
                    <div class="gap-compare-label">Job postings</div>
                    <div class="gap-bar-track"><div class="gap-bar-fill gap-bar-market" style="width:{dem_pct/max_pct*100:.1f}%"></div></div>
                    <div class="gap-bar-value">{dem_pct:.1f}%</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            f"Find courses that mention {row['canonical_name']} →",
            key=f"{key_prefix}_courses_{int(row['skill_id'])}",
            on_click=jump_to_course_finder, args=(row["canonical_name"],),
        )

        test_name = "Fisher's exact test" if row["test_method"] == "fisher_exact" else "two-proportion z-test"
        x_courses = round(row["program_coverage_rate"] * course_count)
        x_postings = round(row["market_demand_rate"] * scope_total_postings)
        trend_desc = {
            "rising": f"x {RISING_BOOST} (rising demand)",
            "falling": f"x {FALLING_PENALTY} (falling demand)",
        }.get(row["trend_label"], "x 1.0 (no clear trend)")
        with st.expander("How we know"):
            st.markdown(
                f"""
                | | |
                |---|---|
                | In course descriptions | **{x_courses} of {course_count}** courses ({cov_pct:.1f}%). A skill missing here may still be taught |
                | In job postings | **{x_postings} of {scope_total_postings}** postings ({dem_pct:.1f}%) |
                | Gap | **{row['gap_value']*100:.1f} percentage points** |
                | Strength of evidence | **{evidence_strength(row['q_value'])}** (the gap is unlikely to be due to chance) |
                | Technical detail | p = {row['p_value']:.4f}, FDR-adjusted q = {row['q_value']:.4f} ({test_name}, Benjamini-Hochberg correction) |
                """
            )
            st.caption(
                f"Ranking score = gap ({row['gap_value']*100:.1f} pts) x demand-trend adjustment ({trend_desc}) "
                f"= {row['priority_score']*100:.1f}. Used only to order this list."
            )


STRENGTHS_SHOWN = 6


def _strengths(program_id):
    """(skill, n_courses) pairs most often named in the program's course descriptions."""
    covered = run_query(
        """
        SELECT s.canonical_name, COUNT(DISTINCT e.source_id) AS n_courses
        FROM extractions e
        JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword' AND c.program_id = ?
        GROUP BY s.skill_id ORDER BY n_courses DESC, s.canonical_name
        """,
        (program_id,),
    )
    covered = covered[~covered["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)].head(STRENGTHS_SHOWN)
    return [(r["canonical_name"], int(r["n_courses"])) for _, r in covered.iterrows()]


def _render_strengths(program_id, course_count):
    """What the program's course descriptions DO name, so each program has
    its own profile and the page is not only a list of what is missing."""
    covered = run_query(
        """
        SELECT s.canonical_name, COUNT(DISTINCT e.source_id) AS n_courses
        FROM extractions e
        JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        JOIN skills s ON s.skill_id = e.skill_id
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword' AND c.program_id = ?
        GROUP BY s.skill_id ORDER BY n_courses DESC, s.canonical_name
        """,
        (program_id,),
    )
    covered = covered[~covered["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)].head(STRENGTHS_SHOWN)
    if covered.empty:
        return
    chips = "".join(
        f'<span class="skill-chip skill-chip-have">{r["canonical_name"]} &middot; {int(r["n_courses"])} of {int(course_count)} courses</span>'
        for _, r in covered.iterrows()
    )
    st.markdown('<p class="section-eyebrow">What This Program Does Name</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="skill-chip-row">{chips}</div>', unsafe_allow_html=True)
    st.caption("The skills most often named in this program's course descriptions.")


def _render_gap_list(recs_df, course_count, scope_display_name, scope_total_postings, true_gap_count, program_id):
    """The answer banner, strengths and ranked gap cards."""
    # ---- The answer, first ----
    biggest = recs_df.iloc[0]
    stat_tiles([
        (f"{course_count}", "courses analyzed"),
        (f"{true_gap_count}", "skills missing"),
        (f"{biggest['canonical_name']}", "top priority skill"),
        (f"{biggest['gap_value']*100:.0f} pts", "its gap size"),
    ])
    top = recs_df.head(TOP_SKILLS_SHOWN)
    chips = "".join(f'<span class="skill-chip skill-chip-missing">{name}</span>' for name in top["canonical_name"])
    st.markdown(
        f"""
        <div class="answer-banner">
            <p class="answer-banner-label">The short answer</p>
            <p class="answer-banner-text">{true_gap_count} {"skill" if true_gap_count == 1 else "skills"} that employers ask for ({scope_display_name}) {"is" if true_gap_count == 1 else "are"} missing
            from this program's course descriptions. {"The biggest:" if true_gap_count > 1 else "It is:"}</p>
            <div class="skill-chip-row">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_strengths(program_id, course_count)

    heading = f"Top {len(top)} Skills to Look For" if len(top) > 1 else "The Skill to Look For"
    st.markdown(f'<p class="section-eyebrow">{heading}</p>', unsafe_allow_html=True)
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        _skill_card(row, rank, course_count, scope_total_postings, key_prefix="top")

    rest = recs_df.iloc[TOP_SKILLS_SHOWN:]
    if not rest.empty:
        with st.expander(f"Show {len(rest)} more skills"):
            for rank, (_, row) in enumerate(rest.iterrows(), start=TOP_SKILLS_SHOWN + 1):
                _skill_card(row, rank, course_count, scope_total_postings, key_prefix="more")
    if true_gap_count > len(recs_df):
        st.caption(f"The list shows the {len(recs_df)} biggest of {true_gap_count} gaps found.")


def render_program_explorer():
    page_header("", "Skill Gaps", "Choose a program and a type of job to see which skills employers ask for that the program's courses do not mention.", art="gaps", pills=("Ranked by gap size", "Courses vs jobs"))

    programs_df = run_query(
        "SELECT p.program_id, p.university, p.program_name, p.tier, "
        "(SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses "
        "FROM programs p ORDER BY p.university"
    )
    programs_df["label"] = [program_label(u, p) for u, p in zip(programs_df["university"], programs_df["program_name"])]

    # Bound to session-state keys so the Home page can pre-select a program
    # and job type before jumping here (see utils/nav.py).
    if EXPLORER_PROGRAM_KEY not in st.session_state or st.session_state[EXPLORER_PROGRAM_KEY] not in list(programs_df["label"]):
        # First program with a full course set, so the default view has real results.
        st.session_state[EXPLORER_PROGRAM_KEY] = programs_df["label"].iloc[int((programs_df["n_courses"] >= 30).idxmax())]

    clusters_df = run_query(
        """
        SELECT cluster_id, role_label FROM role_clusters
        WHERE role_label NOT LIKE 'Mixed%' AND role_label NOT LIKE 'Near-duplicate%'
        ORDER BY role_label
        """
    )
    role_options = [OVERALL_MARKET_LABEL] + list(clusters_df["role_label"])
    if EXPLORER_ROLE_KEY not in st.session_state or st.session_state[EXPLORER_ROLE_KEY] not in role_options:
        st.session_state[EXPLORER_ROLE_KEY] = OVERALL_MARKET_LABEL

    sel_col1, sel_col2 = st.columns([3, 2])
    with sel_col1:
        selected_label = st.selectbox("Program", programs_df["label"], key=EXPLORER_PROGRAM_KEY)
    with sel_col2:
        selected_role_label = st.selectbox(
            "Type of job", role_options, key=EXPLORER_ROLE_KEY,
            help="Compare against all sampled job postings, or only postings for one kind of job.",
        )
    selected = programs_df[programs_df["label"] == selected_label].iloc[0]
    program_id = int(selected["program_id"])

    if selected_role_label == OVERALL_MARKET_LABEL:
        cluster_id = None
        scope_display_name = "all jobs"
        scope_total_postings = run_query("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'").iloc[0]["n"]
    else:
        cluster_id = int(clusters_df[clusters_df["role_label"] == selected_role_label]["cluster_id"].iloc[0])
        scope_display_name = selected_role_label
        scope_total_postings = run_query(
            "SELECT COUNT(*) AS n FROM posting_cluster_map WHERE cluster_id = ?", (cluster_id,)
        ).iloc[0]["n"]

    course_count = run_query("SELECT COUNT(*) AS n FROM courses WHERE program_id = ?", (program_id,)).iloc[0]["n"]
    # Delivery mode is a verifiable fact; the "top-ranked"/"mid-tier" part of
    # the tier field is an unsourced prestige label and is never shown.
    delivery_note = "Online  ·  " if "online" in str(selected["tier"]).lower() else ""
    st.caption(f"{delivery_note}{course_count} courses compared with {scope_total_postings} job postings ({scope_display_name})")

    if course_count < 30:
        st.info(
            f"**Only {course_count} courses were available for this program.** That is a sample, not the full catalog, "
            "so some skills may be missed. Read the results with extra care.",
            icon="⚠️",
        )

    rec_query = """
        SELECT r.skill_id, r.gap_value, r.trend_label, r.priority_score, r.priority_tier, r.rationale,
               g.program_coverage_rate, g.market_demand_rate, g.p_value, g.q_value, g.period, g.test_method
        FROM recommendations r
        JOIN gap_scores g ON g.program_id = r.program_id AND g.skill_id = r.skill_id AND g.cluster_id IS r.cluster_id
        WHERE r.program_id = ? AND r.cluster_id IS {}
        ORDER BY
            CASE r.priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
            r.priority_score DESC
    """
    if cluster_id is None:
        recs_df = run_query(rec_query.format("NULL"), (program_id,))
    else:
        recs_df = run_query(rec_query.format("?"), (program_id, cluster_id))
    skills_df = run_query("SELECT skill_id, canonical_name FROM skills")
    recs_df = recs_df.merge(skills_df, on="skill_id", how="left")

    # True count straight from gap_scores: recommendations is capped per
    # program and scope, so len(recs_df) undercounts programs with many gaps.
    gap_count_query = "SELECT COUNT(*) AS n FROM gap_scores WHERE program_id = ? AND cluster_id IS {}"
    if cluster_id is None:
        true_gap_count = int(run_query(gap_count_query.format("NULL"), (program_id,)).iloc[0]["n"])
    else:
        true_gap_count = int(run_query(gap_count_query.format("?"), (program_id, cluster_id)).iloc[0]["n"])

    if recs_df.empty:
        st.info(
            f"No single skill gap was strong enough to confirm for this program against {scope_display_name}. "
            "That can happen when a program has few courses or a job type has few postings. "
            "The chart below still shows what employers ask for and what the courses name."
        )

    if not recs_df.empty:
        _render_gap_list(recs_df, course_count, scope_display_name, scope_total_postings, true_gap_count, program_id)

    # ---- Chart: the full picture, not only the tested gaps ----
    picture = market_picture(program_id, cluster_id, course_count, scope_total_postings)
    st.markdown('<p class="section-eyebrow">What Employers Ask For vs What Courses Name</p>', unsafe_allow_html=True)
    st.caption("The 10 skills most requested in job postings, and how often this program's course descriptions name each one.")
    chart_df = picture.head(10).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=chart_df["canonical_name"], x=chart_df["coverage"], name="Named in courses", orientation="h", marker_color="#1F9D68")
    fig.add_bar(y=chart_df["canonical_name"], x=chart_df["demand"], name="Asked for in jobs", orientation="h", marker_color="#315CF5")
    fig.update_layout(barmode="group", xaxis_tickformat=".0%")
    apply_chart_theme(fig, height=max(340, len(chart_df) * 44))
    st.plotly_chart(fig, use_container_width=True)

    # ---- Downloads ----
    st.markdown('<p class="section-eyebrow">Take It With You</p>', unsafe_allow_html=True)
    report_title_suffix = "" if cluster_id is None else f" (target role: {scope_display_name})"
    dl_col1, dl_col2, _ = st.columns([1, 1, 2])
    base_name = safe_filename(f"{selected['university']}_{selected['program_name']}_{scope_display_name}_recommendations")
    with dl_col1:
        excel_bytes = build_excel_report(
            selected["university"], selected["program_name"] + report_title_suffix, course_count, recs_df,
            picture=picture, strengths=_strengths(program_id), scope_name=scope_display_name,
        )
        st.download_button(
            "Download Excel", data=excel_bytes, file_name=base_name + ".xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True,
        )
    with dl_col2:
        pdf_bytes = build_pdf_report(
            selected["university"], selected["program_name"] + report_title_suffix, course_count, recs_df,
            scope_display_name=scope_display_name, scope_total_postings=scope_total_postings,
            true_gap_count=true_gap_count, strengths=_strengths(program_id), picture=picture,
        )
        st.download_button(
            "Download PDF", data=pdf_bytes, file_name=base_name + ".pdf",
            mime="application/pdf", use_container_width=True,
        )
