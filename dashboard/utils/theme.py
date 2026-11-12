"""utils/theme.py: the one stylesheet for the whole app.

Design rules, so every page feels like one product:
  - White background, one accent colour (blue), neutral greys; red and green only carry meaning (gap / covered).
  - Flat cards: a 1px border and a small radius. No shadows, gradients or coloured card edges.
  - Navigation is a slim top bar; there is no sidebar.
  - Type scale: page title 1.75rem, section label 0.78rem uppercase, body 0.95rem, captions 0.82rem.
  - Radio options are hidden-dot text tabs. The dot is matched by shape (an empty div in a text-free container),
    never by position, because Streamlit's markup changes between versions.
"""

import streamlit as st

THEME_CSS = """
<style>
:root {
    --bg: #FFFFFF;
    --soft: #F8FAFC;
    --text: #0F172A;
    --muted: #64748B;
    --border: #E2E8F0;
    --accent: #2F5BEA;
    --accent-soft: #EEF2FF;
    --gap: #B42318;
    --gap-soft: #FEF3F2;
    --ok: #067647;
    --ok-soft: #ECFDF3;
}

/* ---- Page frame ---- */
.stApp { background: var(--bg); }
html, body, [class*="css"] { color: var(--text); font-family: Inter, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
div[data-testid="stMainBlockContainer"] { max-width: 1120px; padding-top: 1.2rem; padding-bottom: 3rem; }
section[data-testid="stSidebar"], div[data-testid="collapsedControl"], button[data-testid="stExpandSidebarButton"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }
div[data-testid="stToolbar"], div[data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
h1, h2, h3 { letter-spacing: -0.01em; color: var(--text); }
hr { margin: 1.8rem 0 !important; border-color: var(--border) !important; }

/* ---- Top bar and navigation ---- */
.topbar-brand { font-size: 1.25rem !important; font-weight: 800 !important; color: var(--text) !important; letter-spacing: -0.02em; margin: 0.35rem 0 0 0 !important; white-space: nowrap; }
.topbar-brand span { color: var(--accent); }
.st-key-topnav { border-bottom: 1px solid var(--border); margin-bottom: 0.3rem; }
.st-key-topnav div[role="radiogroup"], .st-key-subnav div[role="radiogroup"] { gap: 0.15rem; flex-wrap: wrap; }
.st-key-topnav label[data-testid="stRadioOption"], .st-key-subnav label[data-testid="stRadioOption"] {
    background: transparent; border: none; border-radius: 0; padding: 0.55rem 0.85rem; margin: 0; cursor: pointer;
    border-bottom: 2px solid transparent;
}
.st-key-topnav label[data-testid="stRadioOption"] div:has(> div:empty):not(:has(p)),
.st-key-subnav label[data-testid="stRadioOption"] div:has(> div:empty):not(:has(p)) { display: none !important; }
.st-key-topnav label[data-testid="stRadioOption"] p { font-size: 0.95rem !important; font-weight: 600 !important; color: var(--muted) !important; }
.st-key-subnav label[data-testid="stRadioOption"] p { font-size: 0.86rem !important; font-weight: 500 !important; color: var(--muted) !important; }
.st-key-topnav label[data-testid="stRadioOption"]:hover p, .st-key-subnav label[data-testid="stRadioOption"]:hover p { color: var(--text) !important; }
.st-key-topnav label[data-testid="stRadioOption"][data-selected="true"], .st-key-subnav label[data-testid="stRadioOption"][data-selected="true"] { border-bottom-color: var(--accent); }
.st-key-topnav label[data-testid="stRadioOption"][data-selected="true"] p,
.st-key-subnav label[data-testid="stRadioOption"][data-selected="true"] p { color: var(--text) !important; font-weight: 700 !important; }
.st-key-subnav { margin-bottom: 0.6rem; }

/* ---- Page header ---- */
.page-head { margin: 1.2rem 0 1.4rem 0; }
.page-head-title { font-size: 1.75rem !important; font-weight: 800 !important; color: var(--text) !important; line-height: 1.2 !important; margin: 0 !important; letter-spacing: -0.02em; }
.page-head-desc { font-size: 0.98rem !important; color: var(--muted) !important; line-height: 1.55 !important; margin: 0.4rem 0 0 0 !important; max-width: 740px; }
.section-eyebrow { font-size: 0.78rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted) !important; margin: 1.6rem 0 0.7rem 0 !important; }

/* ---- Home masthead ---- */
.hero { padding: 2.2rem 0 1.2rem 0; }
.hero-wordmark { font-size: 3rem !important; font-weight: 800 !important; letter-spacing: -0.03em; line-height: 1.05 !important; color: var(--text) !important; margin: 0 0 0.6rem 0 !important; }
.hero-wordmark .wm-ed { color: var(--accent); }
.hero-headline { font-size: 1.5rem !important; font-weight: 700 !important; color: var(--text) !important; line-height: 1.25 !important; margin: 0 0 0.6rem 0 !important; max-width: 640px; letter-spacing: -0.015em; }
.hero-tagline { font-size: 1.02rem !important; color: var(--muted) !important; line-height: 1.6 !important; max-width: 640px; margin: 0 !important; }

/* ---- Cards (flat) ---- */
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px !important; border: 1px solid var(--border) !important; box-shadow: none !important; background: var(--bg) !important; }
.vcard, .stat-tile, .result-hero, .course-card, .step { background: var(--bg); border: 1px solid var(--border); border-radius: 10px; box-shadow: none; }
.vcard { padding: 1.1rem 1.25rem; height: 100%; }
.vcard-title { font-size: 1.05rem !important; font-weight: 700 !important; color: var(--text) !important; margin: 0 0 0.15rem 0 !important; }
.vcard-sub { font-size: 0.84rem !important; color: var(--muted) !important; margin: 0 0 0.7rem 0 !important; line-height: 1.5 !important; }
.vcard-row { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.45rem; font-size: 0.86rem; }
.vcard-row .vcard-name { width: 7rem; color: var(--text); font-weight: 600; flex: 0 0 auto; }
.vcard-row .mini-track { flex: 1; }
.vcard-row .vcard-val { width: 3.4rem; text-align: right; font-weight: 700; color: var(--text); }
.mini-track { height: 8px; background: #EEF2F6; border-radius: 999px; overflow: hidden; }
.mini-fill { height: 100%; border-radius: 999px; }
.arrow-chip { display: inline-block; font-weight: 700; font-size: 0.78rem; padding: 0.12rem 0.55rem; border-radius: 999px; }
.arrow-up { background: var(--ok-soft); color: var(--ok); }
.arrow-down { background: var(--gap-soft); color: var(--gap); }

.stat-tile-row { display: flex; flex-wrap: wrap; gap: 0.8rem; margin: 0 0 1rem 0; }
.stat-tile { flex: 1 1 150px; padding: 0.85rem 1.05rem; }
.stat-tile-value { font-size: 1.6rem !important; font-weight: 800 !important; color: var(--text) !important; line-height: 1.15; }
.stat-tile-label { font-size: 0.8rem !important; color: var(--muted) !important; margin-top: 0.15rem; }

.result-hero { display: flex; flex-wrap: wrap; align-items: center; gap: 1.4rem; padding: 1.2rem 1.5rem; margin-bottom: 1rem; }
.result-hero-text { flex: 1 1 300px; }
.result-hero-label { font-size: 0.74rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent) !important; margin: 0 !important; }
.result-hero-title { font-size: 1.4rem !important; font-weight: 700 !important; color: var(--text) !important; line-height: 1.3 !important; margin: 0.2rem 0 0.35rem !important; }
.result-hero-sub { font-size: 0.93rem !important; color: var(--muted) !important; margin: 0 !important; }
.ring-wrap { text-align: center; }
.ring-caption { font-size: 0.8rem !important; color: var(--muted) !important; margin-top: -0.2rem; }

.answer-banner { background: var(--accent-soft); border: 1px solid #DDE5FF; border-radius: 10px; padding: 1.1rem 1.3rem 0.5rem 1.3rem; margin: 0.8rem 0 1.4rem 0; }
.answer-banner-label { font-size: 0.74rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent) !important; margin-bottom: 0.3rem !important; }
.answer-banner-text { font-size: 1.08rem !important; font-weight: 600 !important; color: var(--text) !important; line-height: 1.45 !important; margin-bottom: 0.6rem !important; }
.answer-banner-sub { font-size: 0.9rem !important; color: var(--muted) !important; }

.skill-card-head { display: flex; align-items: center; gap: 0.7rem; margin-bottom: 0.1rem; }
.skill-rank { display: inline-flex; align-items: center; justify-content: center; width: 1.8rem; height: 1.8rem; border-radius: 50%; background: var(--text); color: #FFFFFF !important; font-size: 0.82rem !important; font-weight: 700 !important; flex-shrink: 0; }
.skill-card-name { font-size: 1.2rem !important; font-weight: 700 !important; color: var(--text) !important; }
.skill-card-meta { font-size: 0.84rem !important; color: var(--muted) !important; margin: 0 0 0.5rem 2.5rem !important; }

.skill-chip-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.4rem 0 0.9rem 0; }
.skill-chip { display: inline-block; padding: 0.25rem 0.7rem; border-radius: 999px; font-size: 0.82rem !important; font-weight: 600 !important; white-space: nowrap; }
.skill-chip-have { background: var(--ok-soft); color: var(--ok) !important; border: 1px solid #C8ECDA; }
.skill-chip-missing { background: var(--gap-soft); color: var(--gap) !important; border: 1px solid #F8D1CD; }

.gap-compare { margin: 0.6rem 0 0.3rem 0; }
.gap-compare-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
.gap-compare-label { width: 110px; font-size: 0.76rem !important; font-weight: 600 !important; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted) !important; flex-shrink: 0; white-space: nowrap; }
.gap-bar-track { flex: 1; background: #EEF2F6; border-radius: 999px; height: 10px; overflow: hidden; }
.gap-bar-fill { height: 100%; border-radius: 999px; }
.gap-bar-curriculum { background: #94A3B8; }
.gap-bar-market { background: var(--accent); }
.gap-bar-role { background: var(--accent); }
.gap-bar-value { width: 52px; text-align: right; font-size: 0.82rem !important; font-weight: 700 !important; color: var(--text) !important; flex-shrink: 0; }

.howitworks-strip { display: flex; align-items: center; flex-wrap: wrap; gap: 0.25rem; margin: 0.3rem 0 0.4rem 0; }
.howitworks-step { background: var(--soft); border: 1px solid var(--border); border-radius: 6px; padding: 0.4rem 0.75rem; font-size: 0.82rem !important; font-weight: 600 !important; color: var(--text) !important; white-space: nowrap; }
.howitworks-arrow { color: var(--muted) !important; font-size: 0.9rem !important; padding: 0 0.05rem; }

.course-card { padding: 0.9rem 1.1rem; margin-bottom: 0.7rem; }
.course-card-title { font-size: 1rem !important; font-weight: 700 !important; color: var(--text) !important; margin: 0 !important; }
.course-card-uni { font-size: 0.78rem !important; font-weight: 600 !important; color: var(--accent) !important; margin: 0.1rem 0 0.4rem !important; }
.course-card-desc { font-size: 0.86rem !important; color: var(--muted) !important; line-height: 1.5 !important; margin: 0 !important; }

.path-title { font-size: 1.15rem !important; font-weight: 700 !important; color: var(--text) !important; margin-bottom: 0.2rem !important; line-height: 1.25 !important; }
.path-desc { font-size: 0.9rem !important; color: var(--muted) !important; margin-bottom: 0.8rem !important; line-height: 1.5 !important; }
.ad-key { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 0.35rem; vertical-align: -1px; }
.ad-key-ok { background: #1F9D68; } .ad-key-warn { background: #F5A524; } .ad-key-no { background: #D94A4A; }

/* ---- Streamlit widgets ---- */
button[kind="primary"] { background: var(--accent) !important; border: 1px solid var(--accent) !important; border-radius: 8px !important; font-weight: 600 !important; box-shadow: none !important; }
button[kind="primary"]:hover { filter: brightness(1.07); }
button[kind="secondary"] { border-radius: 8px !important; border: 1px solid var(--border) !important; font-weight: 600 !important; background: var(--bg) !important; }
div[data-baseweb="select"] > div, div[data-baseweb="textarea"], div[data-baseweb="input"] { border-radius: 8px !important; }
div[data-testid="stExpander"] { border-radius: 8px; border-color: var(--border) !important; }
div[data-testid="stAlert"] { border-radius: 8px; }
div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
div[data-testid="stMetric"] { background: transparent; border: none; padding: 0; }

/* ---- Footer ---- */
.site-footer { color: var(--muted) !important; font-size: 0.82rem !important; line-height: 1.6 !important; }
.site-footer a { color: var(--accent); text-decoration: none; }
@media (max-width: 800px) { .stat-tile { flex: 1 1 42%; } .hero-wordmark { font-size: 2.3rem !important; } }
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
