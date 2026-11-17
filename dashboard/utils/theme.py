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
/* ================= Bold restyle: full-width navy bar, gradient hero, raised cards ================= */
:root { --navy: #0B1B3A; --navy-2: #16327A; --teal: #0EA5A4; --amber: #F59E0B; --edge: max(1rem, calc(50vw - 544px)); }
.stApp { background: #F6F8FC; overflow-x: hidden; }
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stMainBlockContainer"] { max-width: 1120px; padding: 0 1rem 3rem 1rem; }

/* top bar: full-bleed navy */
.st-key-topnav { background: var(--navy); width: 100vw; margin-left: calc(50% - 50vw); padding: 0.55rem var(--edge); border-bottom: none; margin-bottom: 0; }
.topbar-brand { color: #FFFFFF !important; font-size: 1.35rem !important; margin: 0 !important; }
.topbar-brand span { color: #8EA8FF; }
.st-key-topnav label[data-testid="stRadioOption"] { border-bottom: none !important; border-radius: 999px; padding: 0.4rem 1rem; transition: background 0.15s; }
.st-key-topnav label[data-testid="stRadioOption"] p { color: #B8C4E0 !important; font-weight: 600 !important; }
.st-key-topnav label[data-testid="stRadioOption"]:hover { background: rgba(255,255,255,0.08); }
.st-key-topnav label[data-testid="stRadioOption"]:hover p { color: #FFFFFF !important; }
.st-key-topnav label[data-testid="stRadioOption"][data-selected="true"] { background: rgba(255,255,255,0.16); }
.st-key-topnav label[data-testid="stRadioOption"][data-selected="true"] p { color: #FFFFFF !important; }
.st-key-topnav div[role="radiogroup"] { justify-content: flex-end; }

/* sub navigation: pills on a light band */
.st-key-subnav { background: #FFFFFF; width: 100vw; margin-left: calc(50% - 50vw); padding: 0.55rem var(--edge); border-bottom: 1px solid var(--border); margin-bottom: 0.4rem; }
.st-key-subnav label[data-testid="stRadioOption"] { border: 1px solid var(--border) !important; border-radius: 999px; padding: 0.28rem 0.9rem; background: #F8FAFC; }
.st-key-subnav label[data-testid="stRadioOption"] p { font-size: 0.85rem !important; color: #475569 !important; font-weight: 600 !important; }
.st-key-subnav label[data-testid="stRadioOption"]:hover { border-color: var(--accent) !important; }
.st-key-subnav label[data-testid="stRadioOption"][data-selected="true"] { background: var(--accent); border-color: var(--accent) !important; }
.st-key-subnav label[data-testid="stRadioOption"][data-selected="true"] p { color: #FFFFFF !important; }

/* page header banner */
.page-head { background: linear-gradient(120deg, var(--navy) 0%, var(--navy-2) 70%, #2F5BEA 130%); border-radius: 14px; padding: 1.5rem 1.8rem; margin: 1.1rem 0 1.4rem 0; }
.page-head-title { color: #FFFFFF !important; font-size: 1.7rem !important; }
.page-head-desc { color: #C9D5F2 !important; max-width: 760px; }

/* home hero: full-bleed gradient with key numbers */
.hero-band { background: radial-gradient(1200px 400px at 85% -10%, rgba(47,91,234,0.55), transparent 60%), linear-gradient(135deg, var(--navy) 0%, #12286B 100%); width: 100vw; margin-left: calc(50% - 50vw); padding: 3rem var(--edge) 2.4rem var(--edge); margin-bottom: 1.6rem; }
.hero-kicker { font-size: 0.78rem !important; font-weight: 700 !important; letter-spacing: 0.12em; text-transform: uppercase; color: #8EA8FF !important; margin: 0 0 0.8rem 0 !important; }
.hero-band h1 { color: #FFFFFF !important; font-size: 2.7rem !important; line-height: 1.12 !important; letter-spacing: -0.03em; font-weight: 800 !important; max-width: 760px; margin: 0 0 0.9rem 0 !important; padding: 0 !important; }
.hero-band h1 em { font-style: normal; color: #8EA8FF; }
.hero-sub { color: #C9D5F2 !important; font-size: 1.08rem !important; line-height: 1.6 !important; max-width: 680px; margin: 0 0 1.8rem 0 !important; }
.hero-kpis { display: flex; flex-wrap: wrap; gap: 0.9rem; }
.hero-kpi { background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14); border-radius: 12px; padding: 0.85rem 1.2rem; min-width: 150px; }
.hero-kpi-value { font-size: 1.9rem !important; font-weight: 800 !important; color: #FFFFFF !important; line-height: 1.1; }
.hero-kpi-label { font-size: 0.8rem !important; color: #A9B9E0 !important; margin-top: 0.15rem; }

/* raised cards */
div[data-testid="stVerticalBlockBorderWrapper"], .vcard, .stat-tile, .result-hero, .course-card { background: #FFFFFF !important; border: 1px solid #E5EAF3 !important; box-shadow: 0 1px 2px rgba(15,23,42,0.05), 0 4px 14px rgba(15,23,42,0.05) !important; border-radius: 14px !important; }
.vcard { border-top: 4px solid var(--accent) !important; }
.stat-tile { border-top: 3px solid var(--accent) !important; }
.stat-tile-value { color: var(--navy) !important; }
.section-eyebrow { color: var(--navy-2) !important; font-size: 0.8rem !important; margin-top: 2rem !important; }
.section-eyebrow::before { content: ""; display: inline-block; width: 18px; height: 3px; background: var(--accent); border-radius: 2px; margin-right: 0.55rem; vertical-align: middle; }

/* feature cards on home */
.st-key-feat_0, .st-key-feat_1, .st-key-feat_2, .st-key-feat_3 { border-top: 4px solid var(--accent); border-radius: 14px; }
.st-key-feat_1 { border-top-color: var(--teal); } .st-key-feat_2 { border-top-color: var(--amber); } .st-key-feat_3 { border-top-color: #7C3AED; }
.step-card { background: #FFFFFF; border: 1px solid #E5EAF3; border-radius: 14px; padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(15,23,42,0.05); height: 100%; }
.step-num { display: inline-flex; width: 1.7rem; height: 1.7rem; border-radius: 50%; background: var(--accent); color: #FFFFFF !important; font-weight: 700 !important; font-size: 0.85rem !important; align-items: center; justify-content: center; margin-bottom: 0.5rem; }
.step-title { font-weight: 700 !important; color: var(--navy) !important; font-size: 0.98rem !important; margin: 0 0 0.2rem 0 !important; }
.step-desc { color: var(--muted) !important; font-size: 0.85rem !important; line-height: 1.5 !important; margin: 0 !important; }
button[kind="primary"] { background: linear-gradient(135deg, #2F5BEA, #4F46E5) !important; border: none !important; box-shadow: 0 2px 8px rgba(47,91,234,0.3) !important; }
.site-footer { margin-top: 0.5rem; }

/* full-bleed fix: Streamlit sets widths on containers, so force them */
.st-key-topnav, .st-key-subnav { width: 100vw !important; max-width: 100vw !important; box-sizing: border-box; }
.topbar-link { color: #B8C4E0 !important; font-size: 0.88rem !important; font-weight: 600 !important; text-align: right; margin: 0 !important; white-space: nowrap; }
.topbar-link a { color: #FFFFFF !important; text-decoration: none; border: 1px solid rgba(255,255,255,0.3); border-radius: 999px; padding: 0.3rem 0.8rem; }
.topbar-link a:hover { background: rgba(255,255,255,0.12); }
.hero-finding { color: #FFFFFF !important; font-size: 1.02rem !important; background: rgba(255,255,255,0.08); border-left: 3px solid #8EA8FF; padding: 0.6rem 0.9rem; border-radius: 0 8px 8px 0; max-width: 680px; margin: 0 0 1.6rem 0 !important; line-height: 1.5 !important; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1.4rem; }
.hero-badges a, .hero-badges span { font-size: 0.8rem !important; font-weight: 600 !important; color: #DCE5FF !important; border: 1px solid rgba(255,255,255,0.22); border-radius: 999px; padding: 0.22rem 0.75rem; text-decoration: none; background: rgba(255,255,255,0.05); }
.hero-badges a:hover { background: rgba(255,255,255,0.16); color: #FFFFFF !important; }
.hero-badges .hb-label { border: none; background: none; color: #8EA8FF !important; padding-left: 0; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem !important; }
[class*="st-key-role_"] { border-top: 4px solid var(--accent); border-radius: 14px; }
.st-key-role_1 { border-top-color: var(--teal); } .st-key-role_2 { border-top-color: #7C3AED; } .st-key-role_3 { border-top-color: var(--amber); } .st-key-role_4 { border-top-color: #E11D48; }
.role-tag { font-size: 0.72rem !important; font-weight: 700 !important; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted) !important; margin: 0 0 0.2rem 0 !important; }
.topbar-brand { font-size: 1.9rem !important; letter-spacing: -0.03em; }
.about-name { font-size: 2.2rem !important; font-weight: 800 !important; color: var(--navy) !important; letter-spacing: -0.03em; margin: 0.4rem 0 0 0 !important; line-height: 1.1 !important; }
.about-role { color: var(--accent) !important; font-weight: 600 !important; margin: 0.3rem 0 1rem 0 !important; }
.about-story { font-size: 1.05rem !important; line-height: 1.7 !important; color: #334155 !important; max-width: 640px; }
button[role="tab"] { font-weight: 600 !important; }
[class*="st-key-role_"], [class*="st-key-feat_"] { height: 100%; }
div[data-testid="stColumn"]:has([class*="st-key-role_"]) > div, div[data-testid="stColumn"]:has([class*="st-key-feat_"]) > div { height: 100%; }
[class*="st-key-role_"] > div, [class*="st-key-feat_"] > div { height: 100%; }
[class*="st-key-role_"] .path-desc, [class*="st-key-feat_"] .path-desc { min-height: 5.6rem; }
.page-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.8rem; }
.page-pill { font-size: 0.74rem !important; font-weight: 600 !important; color: #DCE5FF !important; border: 1px solid rgba(255,255,255,0.25); border-radius: 999px; padding: 0.15rem 0.7rem; background: rgba(255,255,255,0.08); }
.stat-tile-row { margin: 0.2rem 0 1.2rem 0; }
.stat-tile:nth-child(1) { border-top-color: #2F5BEA !important; } .stat-tile:nth-child(2) { border-top-color: #B42318 !important; }
.stat-tile:nth-child(3) { border-top-color: #0EA5A4 !important; } .stat-tile:nth-child(4) { border-top-color: #F59E0B !important; } .stat-tile:nth-child(5) { border-top-color: #7C3AED !important; }
.result-hero { border-left: 6px solid #2F5BEA !important; background: linear-gradient(90deg, #EEF2FF 0%, #FFFFFF 60%) !important; }
.answer-banner { background: linear-gradient(120deg, #EEF2FF, #F8FAFF); border: 1px solid #DDE5FF; }
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: var(--accent) !important; }
/* larger titles */
.topbar-brand { font-size: 2.3rem !important; font-weight: 800 !important; line-height: 1.1 !important; }
.page-head-title { font-size: 2.4rem !important; letter-spacing: -0.03em; line-height: 1.15 !important; }
.page-head-desc { font-size: 1.08rem !important; }
.hero-band h1 { font-size: 3.4rem !important; }
.section-eyebrow { font-size: 0.9rem !important; }
.vcard-title, .path-title { font-size: 1.2rem !important; }
@media (max-width: 800px) { .hero-band h1 { font-size: 2.3rem !important; } .page-head-title { font-size: 1.8rem !important; } .topbar-brand { font-size: 1.7rem !important; } }
.hero-name { font-size: 5.2rem !important; font-weight: 800 !important; letter-spacing: -0.045em; line-height: 1 !important; color: #FFFFFF !important; margin: 0 0 0.9rem 0 !important; }
.hero-name span { color: #8EA8FF; }
.hero-band h1 { font-size: 2.3rem !important; max-width: 820px; }
@media (max-width: 800px) { .hero-name { font-size: 3.4rem !important; } .hero-band h1 { font-size: 1.7rem !important; } }
/* final title sizing: one AlignED name (top bar), the headline is the hero */
.topbar-brand { font-size: 2rem !important; }
.hero-band h1 { font-size: 3.1rem !important; max-width: 860px; }
@media (max-width: 800px) { .hero-band h1 { font-size: 2rem !important; } .topbar-brand { font-size: 1.6rem !important; } }
/* top bar: vertically centre the brand, GitHub link and tabs on one line */
.st-key-topnav div[data-testid="stHorizontalBlock"] { align-items: center !important; }
.st-key-topnav div[data-testid="stColumn"], .st-key-topnav div[data-testid="stColumn"] > div, .st-key-topnav div[data-testid="stMarkdownContainer"] { display: flex; align-items: center; margin: 0 !important; padding-top: 0; padding-bottom: 0; }
.topbar-brand { font-size: 2.3rem !important; line-height: 1 !important; margin: 0 !important; padding: 0 !important; display: block; }
.topbar-link { line-height: 1 !important; margin: 0 !important; }
.st-key-topnav div[data-testid="stElementContainer"] { margin: 0 !important; }
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
