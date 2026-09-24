"""
app.py -- AlignED dashboard (entry point)

What this file does, in plain terms:
This is the front-facing part of the project -- the part a recruiter,
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
frontend code, no JavaScript, and no build step -- ideal for a data
science/analytics portfolio piece where the point is showing real
analysis, not demonstrating web development. It can also be published
for free to a public URL (Streamlit Community Cloud), so this dashboard
can be linked directly from a resume or LinkedIn profile.

How to run this locally:
    pip install -r requirements.txt
    streamlit run app.py
Then open the local URL it prints (usually http://localhost:8501).

Page structure (see the sidebar -- grouped into 3 workflows, not one
flat list, so a visitor knows where to start):
- Overview: project summary and headline numbers
- Analyze: Program Explorer (pick a program AND a target role, see
  ranked, explained skill-gap recommendations for that combination) and
  Compare Programs (side-by-side, overall-market view)
- Explore: Skill Coverage Heatmap, Skill Demand Trends, Role Groups, and
  Course Finder -- supporting views over the underlying data
- Personalize: Build Your Profile -- paste your own background, get a
  personalized skill-gap + role-match report
- Methodology: the "how this was built, and where it's genuinely
  limited" page -- the kind of thing an interviewer would ask about
  directly, answered up front instead of hidden.
"""

import streamlit as st

from sections.clusters import render_clusters
from sections.compare import render_compare
from sections.course_finder import render_course_finder
from sections.heatmap import render_heatmap
from sections.methodology import render_methodology
from sections.overview import render_overview
from sections.profile import render_profile_builder
from sections.program_explorer import render_program_explorer
from sections.trends import render_trends
from utils.nav import (
    GROUP_ANALYZE, GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_OVERVIEW, GROUP_PERSONALIZE,
    NAV_GROUP_KEY, NAV_PAGE_KEY,
    PAGE_BUILD_PROFILE, PAGE_COMPARE, PAGE_COURSE_FINDER, PAGE_HEATMAP,
    PAGE_METHODOLOGY, PAGE_PROGRAM_EXPLORER, PAGE_ROLE_GROUPS, PAGE_TRENDS,
)

st.set_page_config(page_title="AlignED -- Curriculum vs. Job Market Gap Analysis", page_icon="🎓", layout="wide")

# A small block of custom CSS, layered on top of the theme in
# .streamlit/config.toml, purely for visual polish -- none of this
# touches how data is queried or computed, only how it's displayed.
st.markdown(
    """
    <style>
    .aligned-banner {
        background: linear-gradient(90deg, #1E3A8A 0%, #2563EB 60%, #3B82F6 100%);
        padding: 2rem 2rem 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .aligned-banner h1 { color: white; margin-bottom: 0.25rem; }
    .aligned-banner p { color: #DBEAFE; font-size: 1.05rem; margin-bottom: 0; }
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 0.75rem 1rem 0.5rem 1rem;
    }
    div[data-testid="stExpander"] { border-radius: 8px; }

    /* Sidebar redesign: a dark, branded panel instead of the plain
       default white sidebar with bare-looking radio buttons. */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    }
    section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
    .sidebar-logo {
        font-size: 1.6rem;
        font-weight: 800;
        color: #FFFFFF !important;
        margin-bottom: 0;
    }
    .sidebar-tagline {
        font-size: 0.8rem;
        color: #94A3B8 !important;
        margin-bottom: 1.2rem;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.4rem;
        transition: background-color 0.15s ease;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: rgba(59,130,246,0.18);
    }
    .sidebar-footer {
        position: fixed;
        bottom: 1rem;
        font-size: 0.72rem;
        color: #64748B !important;
    }

    /* Shared page header (utils/layout.py's page_header()) -- every page
       except Overview uses this instead of a bare st.title(), so the 9
       pages share one visual rhythm instead of each inventing its own. */
    .page-header {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.9rem 1.2rem;
        background: #F1F5F9;
        border-left: 4px solid #2563EB;
        border-radius: 8px;
        margin-bottom: 0.6rem;
    }
    .page-header-icon { font-size: 1.6rem; line-height: 1; }
    .page-header-title { font-size: 1.5rem; font-weight: 700; color: #0F172A; }
    .page-header-desc {
        color: #475569;
        font-size: 0.95rem;
        margin: 0.3rem 0 1.1rem 0.2rem;
        line-height: 1.5;
    }

    /* Overview page: "what do you want to do?" section label + the 3
       action cards underneath it. */
    .section-eyebrow {
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        color: #64748B;
        margin: 0.4rem 0 0.9rem 0;
    }
    .action-card-icon { font-size: 1.9rem; margin-bottom: 0.3rem; }
    .action-card-title { font-size: 1.15rem; font-weight: 700; color: #0F172A; margin-bottom: 0.35rem; }
    .action-card-desc { color: #475569; font-size: 0.88rem; line-height: 1.5; min-height: 4.5rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
        transform: translateY(-2px);
    }

    /* General polish: consistent rounded corners on alerts/tables and a
       slightly more deliberate primary-button style than Streamlit's
       flat default. */
    div[data-testid="stAlert"] { border-radius: 8px; }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
    button[kind="primary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    hr { margin: 1.4rem 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Grouped into 3 workflows instead of one flat 9-item list, so a visitor
# knows where to start instead of facing a wall of equally-weighted
# pages. Overview and Methodology stand alone (landing page, and the
# "how honest is this" page respectively); everything else groups under
# what the visitor is trying to DO: analyze a program, explore the
# underlying data, or get something personalized to them. Group/page
# label strings come from utils.nav so the Overview page's action cards
# can jump straight to a specific group+page via the same session-state
# keys these radios are bound to (key=NAV_GROUP_KEY / key=NAV_PAGE_KEY).
NAV_GROUPS = {
    GROUP_OVERVIEW: {"Overview": render_overview},
    GROUP_ANALYZE: {
        PAGE_PROGRAM_EXPLORER: render_program_explorer,
        PAGE_COMPARE: render_compare,
    },
    GROUP_EXPLORE: {
        PAGE_HEATMAP: render_heatmap,
        PAGE_TRENDS: render_trends,
        PAGE_ROLE_GROUPS: render_clusters,
        PAGE_COURSE_FINDER: render_course_finder,
    },
    GROUP_PERSONALIZE: {
        PAGE_BUILD_PROFILE: render_profile_builder,
    },
    GROUP_METHODOLOGY: {PAGE_METHODOLOGY: render_methodology},
}

st.sidebar.markdown('<p class="sidebar-logo">🎓 AlignED</p>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-tagline">Curriculum vs. job market gap analysis</p>', unsafe_allow_html=True)

group_selection = st.sidebar.radio("Section", list(NAV_GROUPS.keys()), key=NAV_GROUP_KEY, label_visibility="collapsed")
pages_in_group = NAV_GROUPS[group_selection]

if len(pages_in_group) > 1:
    # Guard: the page previously selected might belong to a DIFFERENT
    # group (e.g. a homepage card jump, or the visitor just switched
    # groups manually) -- Streamlit's radio widget errors if its bound
    # session-state value isn't among its current options, so fall back
    # to this group's first page instead of crashing.
    if st.session_state.get(NAV_PAGE_KEY) not in pages_in_group:
        st.session_state[NAV_PAGE_KEY] = next(iter(pages_in_group))
    page_selection = st.sidebar.radio("Page", list(pages_in_group.keys()), key=NAV_PAGE_KEY, label_visibility="collapsed")
else:
    page_selection = next(iter(pages_in_group))

st.sidebar.markdown(
    '<p class="sidebar-footer">Data refreshed via database queries<br>'
    '13 programs · 1,378 courses · 1,660 postings<br>'
    'Built with Python, SQLite &amp; Streamlit</p>',
    unsafe_allow_html=True,
)
pages_in_group[page_selection]()
