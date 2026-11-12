"""
app.py: AlignED dashboard (entry point)

What this file does, in plain terms:
This is the front-facing part of the project, the part a recruiter,
hiring manager, or curious visitor would actually click through, rather
than reading raw JSON files or console output. It's a Streamlit app,
meaning it's a Python program that turns into a real interactive web
page: dropdowns, tables, and charts, all reading live from the same
SQLite database every other script in this project has been building up
(programs, courses, job postings, skills, gap scores, demand trends, and
final recommendations).

Why this file is small:
Every earlier version of this dashboard lived entirely in this one file
(1,100+ lines). That's a real code-smell for a portfolio project --
nobody wants to review a single 1,100-line file. This file now only
does three things: apply the page config/CSS, wire up the sidebar
navigation, and dispatch to the page a visitor picked. Every actual page
lives in its own module under dashboard/sections/, and shared logic
(database access, PDF/Excel report building, text-matching helpers,
constants) lives under dashboard/services/ and dashboard/utils/ so it
isn't duplicated across pages.

    dashboard/
        app.py               <- you are here: page config, CSS, nav, dispatch
        sections/            <- one module per page (renamed from the more
                                common "pages/" to avoid colliding with
                                Streamlit's own automatic multi-page-app
                                detection, since this app deliberately uses
                                a custom sidebar radio nav instead)
            overview.py
            profile.py
            program_explorer.py
            course_finder.py
            compare.py
            heatmap.py
            trends.py
            clusters.py
            methodology.py
        services/
            database.py       <- shared SQLite connection + cached query helper
            reports_excel.py  <- Program Explorer's Excel export
            reports_pdf.py    <- Program Explorer + Build Your Profile PDF exports
        utils/
            constants.py      <- shared colors, thresholds, excluded-terms list
            text.py            <- keyword-matching helpers (profile builder)

Why Streamlit for this project:
Streamlit turns a plain Python script into a web app with no separate
frontend code, no JavaScript, and no build step, ideal for a data
science/analytics portfolio piece where the point is showing real
analysis, not demonstrating web development. It can also be published
for free to a public URL (Streamlit Community Cloud), so this dashboard
can be linked directly from a resume or LinkedIn profile.

How to run this locally:
    pip install -r requirements.txt
    streamlit run app.py
Then open the local URL it prints (usually http://localhost:8501).

Page structure (see the sidebar, grouped into 3 workflows, not one
flat list, so a visitor knows where to start):
- Overview: project summary and headline numbers
- Analyze: Program Explorer (pick a program AND a target role, see
  ranked, explained skill-gap recommendations for that combination) and
  Compare Programs (side-by-side, overall-market view)
- Job Market: Skills by Program, Rising and Falling Skills, Job Families, and
  Course Finder, supporting views over the underlying data
- Personalize: Build Your Profile, paste your own background, get a
  personalized skill-gap + role-match report
- Methodology: the "how this was built, and where it's genuinely
  limited" page, the kind of thing an interviewer would ask about
  directly, answered up front instead of hidden.
"""

import streamlit as st

from services.database import run_query
from services.market_pulse import load_market_pulse, refreshed_date
from utils.theme import inject_theme
from sections.clusters import render_clusters
from sections.compare import render_compare
from sections.course_finder import render_course_finder
from sections.findings import render_findings
from sections.heatmap import render_heatmap
from sections.methodology import render_methodology
from sections.match_job import render_match_job
from sections.overview import render_overview
from sections.about import render_about
from sections.data_health import render_data_health
from sections.model_eval import render_model_eval
from sections.own_program import render_own_program
from sections.profile import render_profile_builder
from sections.program_explorer import render_program_explorer
from sections.trends import render_trends
from utils.nav import (
    GROUP_ABOUT, GROUP_ANALYZE, GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_OVERVIEW, GROUP_PERSONALIZE,
    NAV_GROUP_KEY, NAV_PAGE_KEY,
    PAGE_BUILD_PROFILE, PAGE_COMPARE, PAGE_MATCH_JOB, PAGE_COURSE_FINDER, PAGE_HEATMAP,
    PAGE_ABOUT, PAGE_BYO, PAGE_DATA_HEALTH, PAGE_MODEL_EVAL,
    PAGE_FINDINGS, PAGE_METHODOLOGY, PAGE_OVERVIEW, PAGE_PROGRAM_EXPLORER, PAGE_ROLE_GROUPS, PAGE_TRENDS,
)

st.set_page_config(page_title="AlignED: Curriculum vs. Job Market Gap Analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# Design system rewrite (redesign pass): a research-instrument aesthetic
#generous whitespace, a restrained semantic color system, and text
# used as the primary visual language instead of icons/boxes/shadows.
# Color roles are deliberate, not decorative:
#   brand blue  = interactive / primary action
#   gap red     = a curriculum-market gap (bad news, the thing to fix)
#   market blue = job-market demand (the target)
#   coverage green = curriculum coverage / a strength
#   grey        = neutral / structural
inject_theme()

# Five areas, each answering one question a visitor arrives with:
#   Overview  what is this and what did it find?     Explore   look at the data
#   Match     what does this mean for me?            Evidence  how do I know it is right?
#   About     who built it, why, and what would I do next?
# Label strings come from utils.nav so in-page buttons can jump to a specific page through the same
# session-state keys the two nav radios are bound to.
NAV_GROUPS = {
    GROUP_OVERVIEW: {PAGE_OVERVIEW: render_overview, PAGE_FINDINGS: render_findings},
    GROUP_EXPLORE: {
        PAGE_PROGRAM_EXPLORER: render_program_explorer,
        PAGE_COMPARE: render_compare,
        PAGE_HEATMAP: render_heatmap,
        PAGE_TRENDS: render_trends,
        PAGE_ROLE_GROUPS: render_clusters,
        PAGE_COURSE_FINDER: render_course_finder,
    },
    GROUP_PERSONALIZE: {
        PAGE_MATCH_JOB: render_match_job,
        PAGE_BUILD_PROFILE: render_profile_builder,
        PAGE_BYO: render_own_program,
    },
    GROUP_METHODOLOGY: {PAGE_METHODOLOGY: render_methodology, PAGE_MODEL_EVAL: render_model_eval, PAGE_DATA_HEALTH: render_data_health},
    GROUP_ABOUT: {PAGE_ABOUT: render_about},
}

with st.container(key="topnav"):
    brand_col, nav_col = st.columns([1, 5], vertical_alignment="center")
    brand_col.markdown('<p class="topbar-brand">Align<span>ED</span></p>', unsafe_allow_html=True)
    with nav_col:
        group_selection = st.radio("Section", list(NAV_GROUPS.keys()), key=NAV_GROUP_KEY, horizontal=True, label_visibility="collapsed")
pages_in_group = NAV_GROUPS[group_selection]

if len(pages_in_group) > 1:
    # The page remembered from another group may not exist here (a homepage button jumped, or the
    # visitor switched groups); a radio errors if its bound value is not among its options.
    if st.session_state.get(NAV_PAGE_KEY) not in pages_in_group:
        st.session_state[NAV_PAGE_KEY] = next(iter(pages_in_group))
    with st.container(key="subnav"):
        page_selection = st.radio("Page", list(pages_in_group.keys()), key=NAV_PAGE_KEY, horizontal=True, label_visibility="collapsed")
else:
    page_selection = next(iter(pages_in_group))


def _posting_counts():
    """(postings used in the statistics, newer live-feed postings stored but not used). Falls back to the
    published figure if the query cannot run, so the footer can never break the page."""
    try:
        rows = run_query("SELECT source = 'kaggle_sample' AS used, COUNT(*) AS n FROM postings GROUP BY used")
        used = int(rows.loc[rows["used"] == 1, "n"].sum())
        extra = int(rows.loc[rows["used"] == 0, "n"].sum())
        return (used or 1660), extra
    except Exception:
        return 1660, 0


pages_in_group[page_selection]()

_used_postings, _extra_postings = _posting_counts()
_feed_note = f" &middot; {_extra_postings:,} newer postings from the daily feed are stored but not used in any statistic" if _extra_postings else ""
_pulse_date = refreshed_date(load_market_pulse())
_pulse_note = f" &middot; Market pulse last updated {_pulse_date}" if _pulse_date else ""
st.markdown("---")
st.markdown(
    f'<p class="site-footer">13 programs &middot; 1,378 courses &middot; {_used_postings:,} job postings used in the statistics'
    f"{_feed_note}{_pulse_note}<br>Built by Shravani Kulkarni &middot; MS Data Science &middot; "
    '<a href="https://github.com/shravanii15/AlignED" target="_blank">GitHub ↗</a></p>',
    unsafe_allow_html=True,
)
