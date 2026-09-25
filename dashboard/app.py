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

st.set_page_config(page_title="AlignED -- Curriculum vs. Job Market Gap Analysis", page_icon="📊", layout="wide")

# Design system rewrite (redesign pass): a research-instrument aesthetic
# -- generous whitespace, a restrained semantic color system, and text
# used as the primary visual language instead of icons/boxes/shadows.
# Color roles are deliberate, not decorative:
#   brand blue  = interactive / primary action
#   gap red     = a curriculum-market gap (bad news, the thing to fix)
#   market blue = job-market demand (the target)
#   coverage green = curriculum coverage / a strength
#   grey        = neutral / structural
st.markdown(
    """
    <style>
    :root {
        --bg: #F7F8FA;
        --surface: #FFFFFF;
        --surface-soft: #F1F3F6;
        --text: #101828;
        --text-muted: #667085;
        --navy: #0B1220;
        --navy-soft: #16213A;
        --brand: #315CF5;
        --brand-soft: #EAF0FF;
        --gap-red: #D94A4A;
        --gap-red-soft: #FBEAEA;
        --market-blue: #4C7DFF;
        --coverage-green: #1F9D68;
        --coverage-green-soft: #E7F7EF;
        --border: #E4E7EC;
    }

    /* App-wide background + typography baseline. */
    div[data-testid="stAppViewContainer"] { background: var(--bg); }
    div[data-testid="stMainBlockContainer"] { padding-top: 2.25rem; max-width: 1180px; }
    html, body, [class*="css"] { color: var(--text); }
    h1, h2, h3 { letter-spacing: -0.01em; }

    /* ---- Hero (Overview page): a real masthead, not another line of
       body text -- this is deliberately the single largest, boldest
       thing on the page so it reads unmistakably as the product's name,
       plus one short tagline. That's it -- no stacked kicker/title/
       subtitle paragraphs before the visual content starts. ---- */
    .hero-wordmark {
        font-size: 2.6rem;
        font-weight: 800;
        color: var(--text);
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 0.5rem;
    }
    .hero-tagline {
        font-size: 1.05rem;
        line-height: 1.55;
        color: var(--text-muted);
        max-width: 620px;
        margin-bottom: 0;
    }

    /* ---- Small-caps section eyebrow, used throughout ---- */
    .section-eyebrow {
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: var(--text-muted);
        margin: 0 0 0.9rem 0;
    }

    /* ---- Signal panel: the live example analysis on the homepage,
       and the per-skill gap display in Program Explorer. A direct
       curriculum-vs-market bar comparison, the core visual idea of the
       whole product. ---- */
    .signal-eyebrow { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.3rem; }
    .signal-title { font-size: 1.15rem; font-weight: 700; color: var(--text); margin-bottom: 1.1rem; }
    .signal-skill-name { font-size: 1.5rem; font-weight: 800; color: var(--text); margin-bottom: 0.9rem; }
    .signal-row { display: flex; align-items: center; gap: 0.9rem; margin-bottom: 0.7rem; }
    .signal-label { width: 96px; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted); flex-shrink: 0; }
    .signal-track { flex: 1; background: var(--surface-soft); border-radius: 4px; height: 20px; overflow: hidden; }
    .signal-fill { height: 100%; }
    .signal-fill-coverage { background: var(--coverage-green); }
    .signal-fill-market { background: var(--market-blue); }
    .signal-value { width: 64px; text-align: right; font-size: 0.95rem; font-weight: 700; color: var(--text); flex-shrink: 0; }
    .signal-gap-line { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); font-size: 1rem; }
    .signal-gap-value { color: var(--gap-red); font-weight: 800; }

    /* Program Explorer: curriculum-vs-market gap bars inside each
       recommendation card (smaller variant of the signal bars above). */
    .gap-compare { margin: 0.6rem 0 0.3rem 0; }
    .gap-compare-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
    .gap-compare-label { width: 84px; font-size: 0.78rem; font-weight: 600; letter-spacing: 0.03em; text-transform: uppercase; color: var(--text-muted); flex-shrink: 0; }
    .gap-bar-track { flex: 1; background: var(--surface-soft); border-radius: 4px; height: 12px; overflow: hidden; }
    .gap-bar-fill { height: 100%; }
    .gap-bar-curriculum { background: var(--coverage-green); }
    .gap-bar-market { background: var(--market-blue); }
    .gap-bar-role { background: var(--brand); }
    .gap-bar-value { width: 52px; text-align: right; font-size: 0.82rem; font-weight: 700; color: var(--text); flex-shrink: 0; }

    /* ---- Big research-metric numbers (Overview's "THE DATASET"). ---- */
    .stat-block { text-align: left; }
    .stat-number { font-size: 2.1rem; font-weight: 800; color: var(--text); line-height: 1.1; }
    .stat-label { font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-top: 0.3rem; }

    /* ---- Lightweight "what do you want to explore" list, replacing
       the old heavy action cards. ---- */
    .explore-item { padding: 1rem 0; border-top: 1px solid var(--border); }
    .explore-item:last-child { border-bottom: 1px solid var(--border); }
    .explore-item-title { font-size: 1.02rem; font-weight: 700; color: var(--text); }
    .explore-item-desc { font-size: 0.88rem; color: var(--text-muted); margin-top: 0.15rem; }

    /* ---- "How it works" step strip. ---- */
    .howitworks-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem; margin: 0.3rem 0 0.4rem 0; }
    .howitworks-step {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.4rem 0.75rem;
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--text);
        white-space: nowrap;
    }
    .howitworks-arrow { color: var(--text-muted); font-size: 0.9rem; padding: 0 0.05rem; }

    /* ---- Skill chips (Build Your Profile). ---- */
    .skill-chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0 0.9rem 0; }
    .skill-chip { display: inline-block; padding: 0.3rem 0.7rem; border-radius: 6px; font-size: 0.82rem; font-weight: 600; white-space: nowrap; }
    .skill-chip-have { background: var(--coverage-green-soft); color: #146643; border: 1px solid #C8ECDA; }
    .skill-chip-missing { background: var(--gap-red-soft); color: #A13333; border: 1px solid #F2CFCF; }

    /* ---- Metrics: flatten Streamlit's boxed default into plain
       research-style numbers (no card background/border). ---- */
    div[data-testid="stMetric"] { background: transparent; border: none; padding: 0; }
    div[data-testid="stMetricLabel"] p { font-size: 0.74rem !important; font-weight: 700 !important; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted) !important; }
    div[data-testid="stMetricValue"] { color: var(--text) !important; }
    div[data-testid="stExpander"] { border-radius: 6px; border-color: var(--border) !important; }

    /* ---- Sidebar: a slim, text-first research-tool nav, not a
       colored-pill menu. Selectors below target Streamlit's stable
       data-testid="stRadioOption" attribute and its known internal
       structure (verified against the live rendered DOM) rather than
       auto-generated class names, which change between Streamlit
       builds and would silently stop matching. ---- */
    section[data-testid="stSidebar"] { background: var(--navy); }
    section[data-testid="stSidebar"][aria-expanded="true"] { min-width: 250px; max-width: 250px; }
    section[data-testid="stSidebar"] * { color: #CBD3E1 !important; }
    .sidebar-logo { font-size: 1.25rem; font-weight: 800; color: #FFFFFF !important; letter-spacing: -0.01em; margin-bottom: 0; }
    .sidebar-tagline { font-size: 0.76rem; color: #7B87A3 !important; margin-bottom: 1.4rem; }

    /* Hide the circle/dot indicator Streamlit renders for each radio
       option -- it's the first child div inside the option's content
       wrapper. Text weight + a left accent bar (below) communicate
       selection instead. */
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child {
        display: none;
    }
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"] {
        padding: 0.4rem 0 0.4rem 0.75rem;
        margin-bottom: 0.05rem;
        border-left: 2px solid transparent;
        border-radius: 0;
        transition: border-color 0.12s ease, color 0.12s ease;
    }
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"] p {
        font-size: 0.88rem !important;
        font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover {
        border-left-color: #3D4A6B;
    }
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] {
        border-left-color: var(--brand);
    }
    section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    /* NOT position:fixed -- that took the footer out of the sidebar's
       own layout flow entirely, so its text wrapped at the *viewport's*
       width instead of the sidebar's ~250px width and spilled out over
       the main content area. Normal flow (just placed after the nav
       radios, with a top margin) keeps it correctly clipped to the
       sidebar's own box no matter how long the text is. */
    .sidebar-footer { margin-top: 2.5rem; font-size: 0.7rem; line-height: 1.6; color: #6B7690 !important; max-width: 100%; word-wrap: break-word; }
    .sidebar-footer b { color: #9AA5C0 !important; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }

    /* ---- Shared page header (utils/layout.py's page_header()): a
       thin bottom rule and large title instead of a filled colored
       box -- reads as a document heading, not a UI chrome element. ---- */
    .page-header { border-bottom: 1px solid var(--border); padding-bottom: 0.9rem; margin-bottom: 0.5rem; }
    .page-header-icon { font-size: 1rem; opacity: 0.55; margin-right: 0.4rem; }
    .page-header-title { font-size: 1.9rem; font-weight: 800; color: var(--text); }
    .page-header-desc { color: var(--text-muted); font-size: 0.95rem; margin: 0.5rem 0 1.3rem 0; line-height: 1.55; max-width: 760px; }

    /* ---- Cards: used selectively (the analysis command-center, a gap
       card, a signal panel) -- subtle border, no shadow-lift hover
       animation, small border-radius. ---- */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px !important;
        border-color: var(--border) !important;
    }

    div[data-testid="stAlert"] { border-radius: 6px; }
    div[data-testid="stDataFrame"] { border-radius: 6px; overflow: hidden; }
    button[kind="primary"] {
        background: var(--brand) !important;
        border-color: var(--brand) !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    hr { margin: 1.6rem 0 !important; border-color: var(--border) !important; }

    /* ---- Footer credit line (Overview page). ---- */
    .site-footer { color: var(--text-muted); font-size: 0.85rem; }
    .site-footer a { color: var(--brand); text-decoration: none; }
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

st.sidebar.markdown('<p class="sidebar-logo">AlignED</p>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-tagline">Curriculum &times; Labor Market Intelligence</p>', unsafe_allow_html=True)

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
    '<p class="sidebar-footer"><b>Analysis Snapshot</b><br>'
    '13 programs &middot; 1,378 courses &middot; 1,660 postings<br>'
    'Python &middot; SQL &middot; Streamlit</p>',
    unsafe_allow_html=True,
)
pages_in_group[page_selection]()
