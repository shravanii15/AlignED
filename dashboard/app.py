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

Page structure (see the sidebar):
- Overview: project summary and headline numbers
- Build Your Profile: personalized skill-gap + role-match report
- Program Explorer: pick any of the 13 programs and see its ranked,
  explained skill-gap recommendations
- Course Finder, Compare Programs, Skill Coverage Heatmap, Skill Demand
  Trends, Role Clusters: supporting exploration views
- Methodology & Honest Limitations: the "how this was built, and where
  it's genuinely limited" page -- the kind of thing an interviewer would
  ask about directly, answered up front instead of hidden.
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
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = {
    "🏠  Overview": render_overview,
    "🙋  Build Your Profile": render_profile_builder,
    "📋  Program Explorer": render_program_explorer,
    "🔎  Course Finder": render_course_finder,
    "⚖️  Compare Programs": render_compare,
    "🗺️  Skill Coverage Heatmap": render_heatmap,
    "📈  Skill Demand Trends": render_trends,
    "🧩  Role Clusters": render_clusters,
    "🔍  Methodology & Limitations": render_methodology,
}

st.sidebar.markdown('<p class="sidebar-logo">🎓 AlignED</p>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-tagline">Curriculum vs. job market gap analysis</p>', unsafe_allow_html=True)
selection = st.sidebar.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
st.sidebar.markdown(
    '<p class="sidebar-footer">Data refreshed via database queries<br>'
    '13 programs · 1,378 courses · 1,660+ postings<br>'
    'Built with Python, SQLite &amp; Streamlit</p>',
    unsafe_allow_html=True,
)
PAGES[selection]()
