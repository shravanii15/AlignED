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

from sections.clusters import render_clusters
from sections.compare import render_compare
from sections.course_finder import render_course_finder
from sections.heatmap import render_heatmap
from sections.methodology import render_methodology
from sections.match_job import render_match_job
from sections.overview import render_overview
from sections.profile import render_profile_builder
from sections.program_explorer import render_program_explorer
from sections.trends import render_trends
from utils.nav import (
    GROUP_ANALYZE, GROUP_EXPLORE, GROUP_METHODOLOGY, GROUP_OVERVIEW, GROUP_PERSONALIZE,
    NAV_GROUP_KEY, NAV_PAGE_KEY,
    PAGE_BUILD_PROFILE, PAGE_COMPARE, PAGE_MATCH_JOB, PAGE_COURSE_FINDER, PAGE_HEATMAP,
    PAGE_METHODOLOGY, PAGE_PROGRAM_EXPLORER, PAGE_ROLE_GROUPS, PAGE_TRENDS,
)

st.set_page_config(page_title="AlignED: Curriculum vs. Job Market Gap Analysis", page_icon="📊", layout="wide")

# Design system rewrite (redesign pass): a research-instrument aesthetic
#generous whitespace, a restrained semantic color system, and text
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
       body text, this is deliberately the single largest, boldest
       thing on the page so it reads unmistakably as the product's name,
       plus one short tagline. That's it, no stacked kicker/title/
       subtitle paragraphs before the visual content starts. ---- */
    .hero-wordmark {
        font-size: 2.6rem !important;
        font-weight: 800 !important;
        color: var(--text) !important;
        letter-spacing: -0.02em;
        line-height: 1.1 !important;
        margin-bottom: 0.5rem;
    }
    .hero-tagline {
        font-size: 1.05rem !important;
        line-height: 1.55 !important;
        color: var(--text-muted) !important;
        max-width: 620px;
        margin-bottom: 0;
    }


    /* ---- Home hero panel ---- */
    .hero-panel {
        display: flex; flex-wrap: wrap; gap: 2rem; align-items: center; justify-content: space-between;
        background: linear-gradient(135deg, #0B1220 0%, #16213A 100%);
        border-radius: 20px; padding: 2.2rem 2.4rem;
    }
    .hero-left { flex: 1 1 340px; }
    .hero-panel .hero-wordmark { color: #FFFFFF !important; font-size: 3rem !important; }
    .hero-panel .hero-tagline { color: #C7D2FE !important; font-size: 1.15rem !important; max-width: 480px; }
    .hero-pills { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.2rem; }
    .hero-pills span {
        background: #315CF5; color: #FFFFFF; font-size: 0.85rem; font-weight: 600;
        padding: 0.35rem 0.9rem; border-radius: 999px;
    }
    .hero-card {
        flex: 0 1 380px; background: #FFFFFF; border-radius: 14px; padding: 1.3rem 1.5rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .hero-card p { margin: 0 !important; }
    .hero-card-eyebrow { font-size: 0.7rem !important; font-weight: 700 !important; letter-spacing: 0.1em; text-transform: uppercase; color: #667085 !important; }
    .hero-card-skill { font-size: 1.9rem !important; font-weight: 800 !important; color: #101828 !important; margin: 0.2rem 0 0.8rem !important; }
    .hero-card-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.55rem; font-size: 0.85rem; color: #667085; }
    .hero-card-row span { width: 5.2rem; }
    .hero-card-row b { width: 2.6rem; text-align: right; color: #101828; }
    .hero-card-track { flex: 1; height: 12px; background: #F1F3F6; border-radius: 999px; overflow: hidden; }
    .hero-card-fill { height: 100%; border-radius: 999px; }
    .hero-card-fill-c { background: #1F9D68; }
    .hero-card-fill-m { background: #4C7DFF; }
    .hero-card-gap {
        display: inline-block; margin-top: 0.5rem !important; background: #FBEAEA; color: #D94A4A !important;
        font-weight: 700 !important; font-size: 0.95rem !important; padding: 0.25rem 0.8rem; border-radius: 999px;
    }
    .hero-card-src { font-size: 0.75rem !important; color: #98A2B3 !important; margin-top: 0.6rem !important; }

    /* ---- Small-caps section eyebrow, used throughout ---- */
    .section-eyebrow {
        font-size: 0.74rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: var(--text-muted) !important;
        margin: 0 0 0.9rem 0;
    }

    /* ---- Signal panel: the live example analysis on the homepage,
       and the per-skill gap display in Program Explorer. A direct
       curriculum-vs-market bar comparison, the core visual idea of the
       whole product. ---- */
    .signal-eyebrow { font-size: 0.72rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted) !important; margin-bottom: 0.3rem; }
    .signal-title { font-size: 1.15rem !important; font-weight: 700 !important; color: var(--text) !important; margin-bottom: 1.1rem; }
    .signal-skill-name { font-size: 1.5rem !important; font-weight: 800 !important; color: var(--text) !important; margin-bottom: 0.9rem; }
    .signal-row { display: flex; align-items: center; gap: 0.9rem; margin-bottom: 0.7rem; }
    .signal-label { width: 96px; font-size: 0.8rem !important; font-weight: 600 !important; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted) !important; flex-shrink: 0; }
    .signal-track { flex: 1; background: var(--surface-soft); border-radius: 4px; height: 20px; overflow: hidden; }
    .signal-fill { height: 100%; }
    .signal-fill-coverage { background: var(--coverage-green); }
    .signal-fill-market { background: var(--market-blue); }
    .signal-value { width: 64px; text-align: right; font-size: 0.95rem !important; font-weight: 700 !important; color: var(--text) !important; flex-shrink: 0; }
    .signal-gap-line { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border); font-size: 1rem !important; }
    .signal-gap-value { color: var(--gap-red) !important; font-weight: 800 !important; }

    /* Program Explorer: curriculum-vs-market gap bars inside each
       recommendation card (smaller variant of the signal bars above). */
    .gap-compare { margin: 0.6rem 0 0.3rem 0; }
    .gap-compare-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
    .gap-compare-label { width: 84px; font-size: 0.78rem !important; font-weight: 600 !important; letter-spacing: 0.03em; text-transform: uppercase; color: var(--text-muted) !important; flex-shrink: 0; }
    .gap-bar-track { flex: 1; background: var(--surface-soft); border-radius: 4px; height: 12px; overflow: hidden; }
    .gap-bar-fill { height: 100%; }
    .gap-bar-curriculum { background: var(--coverage-green); }
    .gap-bar-market { background: var(--market-blue); }
    .gap-bar-role { background: var(--brand); }
    .gap-bar-value { width: 52px; text-align: right; font-size: 0.82rem !important; font-weight: 700 !important; color: var(--text) !important; flex-shrink: 0; }

    /* Compare Programs: one skill + gap per row inside each program card. */
    .compare-row { display: flex; justify-content: space-between; align-items: baseline; padding: 0.35rem 0; border-top: 1px solid var(--border); }
    .compare-skill { font-size: 0.92rem !important; font-weight: 600 !important; color: var(--text) !important; }
    .compare-gap { font-size: 0.9rem !important; font-weight: 800 !important; }

    /* ---- Big research-metric numbers (Overview's "THE DATASET"). ---- */
    .stat-block { text-align: left; }
    .stat-number { font-size: 2.1rem !important; font-weight: 800 !important; color: var(--text) !important; line-height: 1.1 !important; }
    .stat-label { font-size: 0.74rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted) !important; margin-top: 0.3rem; }

    /* ---- Lightweight "what do you want to explore" list, replacing
       the old heavy action cards. ---- */
    .explore-item { padding: 1rem 0; border-top: 1px solid var(--border); }
    .explore-item:last-child { border-bottom: 1px solid var(--border); }
    .explore-item-title { font-size: 1.02rem !important; font-weight: 700 !important; color: var(--text) !important; }
    .explore-item-desc { font-size: 0.88rem !important; color: var(--text-muted) !important; margin-top: 0.15rem; }

    /* ---- "How it works" step strip. ---- */
    .howitworks-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem; margin: 0.3rem 0 0.4rem 0; }
    .howitworks-step {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.4rem 0.75rem;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: var(--text) !important;
        white-space: nowrap;
    }
    .howitworks-arrow { color: var(--text-muted) !important; font-size: 0.9rem !important; padding: 0 0.05rem; }

    /* ---- Skill chips (Build Your Profile). ---- */
    .skill-chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0 0.9rem 0; }
    .skill-chip { display: inline-block; padding: 0.3rem 0.7rem; border-radius: 6px; font-size: 0.82rem !important; font-weight: 600 !important; white-space: nowrap; }
    .skill-chip-have { background: var(--coverage-green-soft); color: #146643 !important; border: 1px solid #C8ECDA; }
    .skill-chip-missing { background: var(--gap-red-soft); color: #A13333 !important; border: 1px solid #F2CFCF; }

    /* ---- Home: the two path cards ---- */
    .path-title { font-size: 1.25rem !important; font-weight: 800 !important; color: var(--text) !important; margin-bottom: 0.2rem; line-height: 1.25 !important; }
    .path-desc { font-size: 0.92rem !important; color: var(--text-muted) !important; margin-bottom: 0.8rem; line-height: 1.5 !important; }

    /* ---- Skill Gaps: the short-answer banner and ranked skill cards ---- */
    .answer-banner { background: var(--brand-soft); border: 1px solid #D5E0FF; border-radius: 10px; padding: 1.1rem 1.3rem 0.6rem 1.3rem; margin: 0.8rem 0 1.6rem 0; }
    .answer-banner-label { font-size: 0.72rem !important; font-weight: 700 !important; letter-spacing: 0.1em; text-transform: uppercase; color: var(--brand) !important; margin-bottom: 0.3rem; }
    .answer-banner-text { font-size: 1.1rem !important; font-weight: 600 !important; color: var(--text) !important; line-height: 1.45 !important; margin-bottom: 0.6rem; }
    .skill-card-head { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.1rem; }
    .skill-rank { display: inline-flex; align-items: center; justify-content: center; width: 1.7rem; height: 1.7rem; border-radius: 50%; background: var(--navy); color: #FFFFFF !important; font-size: 0.8rem !important; font-weight: 700 !important; flex-shrink: 0; }
    .skill-card-name { font-size: 1.25rem !important; font-weight: 800 !important; color: var(--text) !important; }
    .answer-banner-sub { font-size: 0.9rem !important; color: var(--text-muted) !important; margin: 0.5rem 0 0.4rem 0; }
    .skill-card-meta { font-size: 0.82rem !important; color: var(--text-muted) !important; margin: 0 0 0.5rem 2.4rem; }

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
    .sidebar-logo { font-size: 1.25rem !important; font-weight: 800 !important; color: #FFFFFF !important; letter-spacing: -0.01em; margin-bottom: 0; }
    .sidebar-tagline { font-size: 0.76rem !important; color: #7B87A3 !important; margin-bottom: 1.4rem; }

    /* Hide the circle/dot indicator Streamlit renders for each radio
       option, it's the first child div inside the option's content
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
    /* NOT position:fixed, that took the footer out of the sidebar's
       own layout flow entirely, so its text wrapped at the *viewport's*
       width instead of the sidebar's ~250px width and spilled out over
       the main content area. Normal flow (just placed after the nav
       radios, with a top margin) keeps it correctly clipped to the
       sidebar's own box no matter how long the text is. */
    .sidebar-footer { margin-top: 2.5rem; font-size: 0.7rem !important; line-height: 1.6 !important; color: #6B7690 !important; max-width: 100%; word-wrap: break-word; }
    .sidebar-footer b { color: #9AA5C0 !important; font-size: 0.68rem !important; font-weight: 700 !important; letter-spacing: 0.06em; text-transform: uppercase; }

    /* ---- Shared page header (utils/layout.py's page_header()): a
       thin bottom rule and large title instead of a filled colored
       box, reads as a document heading, not a UI chrome element. ---- */


    /* ---- Visual components: ring, stat tiles, cards ---- */
    .ring-wrap { text-align: center; }
    .ring-caption { font-size: 0.8rem !important; color: var(--text-muted) !important; margin-top: -0.2rem; }
    .stat-tile-row { display: flex; flex-wrap: wrap; gap: 0.9rem; margin: 0 0 1.2rem 0; }
    .stat-tile { flex: 1 1 150px; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 0.9rem 1.1rem; border-top: 4px solid var(--brand); }
    .stat-tile-value { font-size: 1.7rem !important; font-weight: 800 !important; color: var(--text) !important; line-height: 1.15; }
    .stat-tile-label { font-size: 0.8rem !important; color: var(--text-muted) !important; margin-top: 0.15rem; }
    .mini-track { height: 8px; background: #F1F3F6; border-radius: 999px; overflow: hidden; }
    .mini-fill { height: 100%; border-radius: 999px; }
    .result-hero { display: flex; flex-wrap: wrap; align-items: center; gap: 1.6rem; background: var(--surface); border: 1px solid var(--border); border-radius: 18px; padding: 1.4rem 1.8rem; margin-bottom: 1rem; }
    .result-hero-text { flex: 1 1 300px; }
    .result-hero-label { font-size: 0.72rem !important; font-weight: 700 !important; letter-spacing: 0.1em; text-transform: uppercase; color: var(--brand) !important; margin: 0 !important; }
    .result-hero-title { font-size: 1.6rem !important; font-weight: 800 !important; color: var(--text) !important; line-height: 1.25 !important; margin: 0.2rem 0 0.4rem !important; }
    .result-hero-sub { font-size: 0.95rem !important; color: var(--text-muted) !important; margin: 0 !important; }
    .vcard { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 1.1rem 1.2rem; height: 100%; }
    .vcard-accent { border-top: 5px solid var(--brand); }
    .vcard-title { font-size: 1.1rem !important; font-weight: 800 !important; color: var(--text) !important; margin: 0 0 0.15rem 0 !important; line-height: 1.3 !important; }
    .vcard-sub { font-size: 0.8rem !important; color: var(--text-muted) !important; margin: 0 0 0.7rem 0 !important; }
    .vcard-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.45rem; font-size: 0.85rem; }
    .vcard-row .vcard-name { width: 7.2rem; color: var(--text); font-weight: 600; flex: 0 0 auto; }
    .vcard-row .mini-track { flex: 1; }
    .vcard-row .vcard-val { width: 3.2rem; text-align: right; font-weight: 700; color: var(--text); }
    .arrow-chip { display: inline-block; font-weight: 800; font-size: 0.8rem; padding: 0.15rem 0.6rem; border-radius: 999px; }
    .arrow-up { background: var(--coverage-green-soft); color: var(--coverage-green); }
    .arrow-down { background: var(--gap-red-soft); color: var(--gap-red); }
    .course-card { background: var(--surface); border: 1px solid var(--border); border-left: 5px solid var(--brand); border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.7rem; }
    .course-card-title { font-size: 1rem !important; font-weight: 700 !important; color: var(--text) !important; margin: 0 !important; }
    .course-card-uni { font-size: 0.78rem !important; font-weight: 600 !important; color: var(--brand) !important; margin: 0.1rem 0 0.4rem !important; }
    .course-card-desc { font-size: 0.85rem !important; color: var(--text-muted) !important; line-height: 1.5 !important; margin: 0 !important; }


    /* ---- Home: three-step "how it helps" strip ---- */
    .steps-strip { display: flex; flex-wrap: wrap; gap: 1rem; margin-top: 1rem; }
    .step { flex: 1 1 220px; display: flex; gap: 0.8rem; align-items: flex-start; background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 0.9rem 1.1rem; font-size: 0.85rem; color: var(--text-muted); line-height: 1.45; }
    .step b { color: var(--text); font-size: 0.92rem; }
    .step-num { flex: 0 0 auto; width: 1.9rem; height: 1.9rem; border-radius: 50%; background: var(--brand); color: #FFFFFF; font-weight: 800; display: flex; align-items: center; justify-content: center; font-size: 0.95rem; }


    .hero-panel .hero-wordmark { font-size: 2.4rem !important; font-weight: 800 !important; letter-spacing: -0.02em; text-transform: none; color: #FFFFFF !important; margin-bottom: 0.7rem !important; }
    .hero-wordmark .wm-ed { color: #7AA2FF; }
    .hero-headline { font-size: 2.5rem !important; font-weight: 800 !important; color: #FFFFFF !important; line-height: 1.15 !important; letter-spacing: -0.02em; margin: 0 0 0.9rem 0 !important; max-width: 520px; }
    .hero-card-sub { font-size: 0.82rem !important; color: #667085 !important; margin: 0.1rem 0 0.6rem !important; }
    .ex-legend { display: flex; gap: 1rem; font-size: 0.75rem; color: #667085; margin-bottom: 0.6rem; }
    .ex-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 0.35rem; }
    .ex-dot-m { background: #4C7DFF; } .ex-dot-c { background: #1F9D68; }
    .ex-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.55rem; }
    .ex-skill { width: 5.6rem; font-weight: 700; font-size: 0.9rem; color: #101828; flex: 0 0 auto; }
    .ex-bars { flex: 1; }
    .ex-bar { display: flex; align-items: center; gap: 0.5rem; height: 12px; margin: 2px 0; }
    .ex-bar b { font-size: 0.7rem; color: #101828; width: 2.6rem; flex: 0 0 auto; }
    .ex-track { flex: 1; height: 9px; background: #F1F3F6; border-radius: 999px; overflow: hidden; }
    .ex-fill { height: 100%; border-radius: 999px; }
    .ex-fill-m { background: #4C7DFF; } .ex-fill-c { background: #1F9D68; }

    /* ---- Page banner (every inner page) ---- */
    .page-banner {
        display: flex; align-items: center; justify-content: space-between; gap: 1.5rem;
        border-radius: 18px; padding: 1.6rem 2rem; margin-bottom: 1.4rem;
    }
    .page-banner-text { flex: 1 1 auto; min-width: 0; }
    .page-banner-title { font-size: 2rem !important; font-weight: 800 !important; color: #FFFFFF !important; line-height: 1.15 !important; margin: 0 !important; letter-spacing: -0.01em; }
    .page-banner-desc { font-size: 1rem !important; color: #DBE4FF !important; line-height: 1.55 !important; margin: 0.55rem 0 0 0 !important; max-width: 640px; }
    .page-banner-pills { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.9rem; }
    .page-banner-pills:empty { display: none; }
    .page-banner-pills span { background: rgba(255,255,255,0.16); color: #FFFFFF; font-size: 0.8rem; font-weight: 600; padding: 0.28rem 0.8rem; border-radius: 999px; }
    .page-banner-art { flex: 0 0 150px; width: 150px; height: auto; }
    @media (max-width: 700px) { .page-banner-art { display: none; } .page-banner { padding: 1.3rem 1.2rem; } }

    .page-header { border-bottom: 1px solid var(--border); padding-bottom: 0.9rem; margin-bottom: 0.5rem; }
    .page-header-icon { font-size: 1rem !important; opacity: 0.55; margin-right: 0.4rem; }
    .page-header-title { font-size: 1.9rem !important; font-weight: 800 !important; color: var(--text) !important; }
    .page-header-desc { color: var(--text-muted) !important; font-size: 0.95rem !important; margin: 0.5rem 0 1.3rem 0; line-height: 1.55 !important; max-width: 760px; }

    /* ---- Page tabs (sub-pages of a section), shown above the page. ---- */
    div[data-testid="stMainBlockContainer"] div[role="radiogroup"] { gap: 0.4rem; }
    div[data-testid="stMainBlockContainer"] label[data-testid="stRadioOption"] {
        background: var(--surface); border: 1px solid var(--border); border-radius: 999px;
        padding: 0.3rem 0.95rem; margin-right: 0;
    }
    div[data-testid="stMainBlockContainer"] label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
    div[data-testid="stMainBlockContainer"] label[data-testid="stRadioOption"][data-selected="true"] { background: var(--navy); border-color: var(--navy); }
    div[data-testid="stMainBlockContainer"] label[data-testid="stRadioOption"][data-selected="true"] p { color: #FFFFFF !important; font-weight: 700 !important; }
    div[data-testid="stMainBlockContainer"] label[data-testid="stRadioOption"] p { font-size: 0.88rem !important; font-weight: 600 !important; }

    /* ---- Cards: used selectively (the analysis command-center, a gap
       card, a signal panel), subtle border, no shadow-lift hover
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
    .site-footer { color: var(--text-muted) !important; font-size: 0.85rem !important; }
    .site-footer a { color: var(--brand); text-decoration: none; }

    /* ======== Unified visual system (loaded last so it wins) ========
       One look for every page: rich gradient bars, card shadows with a
       colored top edge, navy answer panels, bold section markers. */
    :root {
        --grad-blue: linear-gradient(90deg, #7AA2FF 0%, #315CF5 100%);
        --grad-green: linear-gradient(90deg, #4ADE9A 0%, #1F9D68 100%);
        --grad-red: linear-gradient(90deg, #FF8A8A 0%, #D94A4A 100%);
        --grad-navy: linear-gradient(135deg, #0B1220 0%, #1E3A8A 100%);
        --shadow-card: 0 6px 18px rgba(16, 24, 40, 0.07);
    }
    .stApp { background: linear-gradient(180deg, #EEF2FF 0%, #F7F8FA 280px) !important; }

    /* Bars: thicker, rounded, gradient, on a visible track */
    .signal-track { height: 18px !important; border-radius: 999px !important; background: #E3E8F4 !important; }
    .gap-bar-track { height: 16px !important; border-radius: 999px !important; background: #E3E8F4 !important; }
    .signal-fill, .gap-bar-fill, .mini-fill { border-radius: 999px !important; }
    .signal-fill-coverage, .gap-bar-curriculum { background: var(--grad-green) !important; }
    .signal-fill-market, .gap-bar-market { background: var(--grad-blue) !important; }
    .gap-bar-role { background: var(--grad-blue) !important; }
    .mini-track { height: 12px !important; background: #E3E8F4 !important; }
    .signal-value, .gap-bar-value { font-weight: 800 !important; }
    .signal-label { color: #475467 !important; }

    /* Cards */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px !important;
        border: 1px solid #DCE3F2 !important;
        border-top: 4px solid var(--brand) !important;
        background: #FFFFFF !important;
        box-shadow: var(--shadow-card) !important;
    }
    .vcard, .stat-tile, .result-hero, .course-card, .step { box-shadow: var(--shadow-card) !important; border-color: #DCE3F2 !important; }
    .vcard-accent { border-top-width: 5px !important; }
    .result-hero { border-left: 6px solid var(--brand) !important; }
    .stat-tile-row .stat-tile:nth-child(1) { border-top-color: #315CF5; }
    .stat-tile-row .stat-tile:nth-child(2) { border-top-color: #D94A4A; }
    .stat-tile-row .stat-tile:nth-child(3) { border-top-color: #1F9D68; }
    .stat-tile-row .stat-tile:nth-child(4) { border-top-color: #F5A524; }
    .stat-tile-value { color: #0B1220 !important; font-size: 1.9rem !important; }

    /* Answer panel: same navy gradient as the hero banners */
    .answer-banner { background: var(--grad-navy) !important; border: none !important; border-radius: 16px !important; padding: 1.3rem 1.6rem 0.8rem 1.6rem !important; box-shadow: var(--shadow-card); }
    .answer-banner-label { color: #8FA8FF !important; }
    .answer-banner-text { color: #FFFFFF !important; font-size: 1.25rem !important; }
    .answer-banner-sub { color: #C7D2FE !important; }
    .answer-banner .signal-track { background: rgba(255,255,255,0.22) !important; }
    .answer-banner .skill-chip-missing { background: #FFFFFF; color: #B42318 !important; border-color: #FFFFFF; }

    /* Rank badges, chips, section markers */
    .skill-rank { background: var(--grad-blue) !important; width: 2rem !important; height: 2rem !important; font-size: 0.9rem !important; box-shadow: 0 3px 8px rgba(49,92,245,0.35); }
    .skill-chip { font-weight: 700 !important; border-radius: 999px !important; padding: 0.32rem 0.85rem !important; }
    .skill-chip-have { background: #D8F5E6 !important; border-color: #A9E4C5 !important; color: #0E5E3D !important; }
    .skill-chip-missing { background: #FDE2E2 !important; border-color: #F7BDBD !important; color: #A8261F !important; }
    .section-eyebrow { color: #1D2939 !important; font-size: 0.82rem !important; display: flex; align-items: center; gap: 0.55rem; }
    .section-eyebrow::before { content: ""; width: 5px; height: 1.05rem; border-radius: 3px; background: var(--grad-blue); display: inline-block; }

    /* Buttons */
    button[kind="primary"] { background: linear-gradient(135deg, #4C7DFF 0%, #315CF5 100%) !important; border: none !important; border-radius: 10px !important; box-shadow: 0 4px 12px rgba(49,92,245,0.35) !important; }
    button[kind="primary"]:hover { filter: brightness(1.08); }
    button[kind="secondary"] { border-radius: 10px !important; border-color: #C9D3EE !important; font-weight: 600 !important; }
    button[kind="secondary"]:hover { border-color: var(--brand) !important; color: var(--brand) !important; }
    div[data-testid="stDataFrame"] { border: 1px solid #DCE3F2; border-radius: 12px; box-shadow: var(--shadow-card); }
    div[data-testid="stAlert"] { border-radius: 12px !important; }
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
        PAGE_MATCH_JOB: render_match_job,
        PAGE_BUILD_PROFILE: render_profile_builder,
    },
    GROUP_METHODOLOGY: {PAGE_METHODOLOGY: render_methodology},
}

st.sidebar.markdown('<p class="sidebar-logo">Align<span style="color:#7AA2FF;">ED</span></p>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="sidebar-tagline">Does your program teach what employers ask for?</p>', unsafe_allow_html=True)

group_selection = st.sidebar.radio("Section", list(NAV_GROUPS.keys()), key=NAV_GROUP_KEY, label_visibility="collapsed")
pages_in_group = NAV_GROUPS[group_selection]

if len(pages_in_group) > 1:
    # Guard: the page previously selected might belong to a DIFFERENT
    # group (e.g. a homepage card jump, or the visitor just switched
    # groups manually), Streamlit's radio widget errors if its bound
    # session-state value isn't among its current options, so fall back
    # to this group's first page instead of crashing.
    if st.session_state.get(NAV_PAGE_KEY) not in pages_in_group:
        st.session_state[NAV_PAGE_KEY] = next(iter(pages_in_group))
    # Sub-pages are tabs at the top of the content area, not a second list
    # in the sidebar: a second radio there rendered underneath
    # "Methodology" and read as if it belonged to that section.
    page_selection = st.radio("Page", list(pages_in_group.keys()), key=NAV_PAGE_KEY, horizontal=True, label_visibility="collapsed")
else:
    page_selection = next(iter(pages_in_group))

st.sidebar.markdown(
    '<p class="sidebar-footer"><b>Based on</b><br>'
    '13 programs &middot; 1,378 courses &middot; 1,660 job postings</p>',
    unsafe_allow_html=True,
)
pages_in_group[page_selection]()
