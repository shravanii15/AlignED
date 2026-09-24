"""
utils/nav.py -- shared navigation labels and the session-state keys that
drive the sidebar's two-tier navigation (group, then page within group).

Why this exists as its own module: app.py owns the actual page-function
dispatch (it has to import every render_* function), but the Overview
page's "jump straight to X" action cards also need to reference the
exact same group/page label strings so clicking a card actually lands on
the right page. Keeping the label strings here as named constants --
imported by both app.py and sections/overview.py -- means they can never
silently drift out of sync with each other (a typo in one file would
just be a broken nav link with no error), instead of hand-typing the
same literal strings in two different files.
"""

# Sidebar section (group) labels
GROUP_OVERVIEW = "🏠  Overview"
GROUP_ANALYZE = "🎯  Analyze"
GROUP_EXPLORE = "🔍  Explore"
GROUP_PERSONALIZE = "👤  Personalize"
GROUP_METHODOLOGY = "📖  Methodology"

# Page labels within a group (only listed here where the Overview page's
# action cards need to jump directly to them)
PAGE_PROGRAM_EXPLORER = "📋  Program Explorer"
PAGE_COMPARE = "⚖️  Compare Programs"
PAGE_HEATMAP = "🗺️  Skill Coverage Heatmap"
PAGE_TRENDS = "📈  Skill Demand Trends"
PAGE_ROLE_GROUPS = "🧩  Role Groups"
PAGE_COURSE_FINDER = "🔎  Course Finder"
PAGE_BUILD_PROFILE = "🙋  Build Your Profile"
PAGE_METHODOLOGY = "🔍  Methodology & Limitations"

# The st.session_state keys the sidebar's two radio widgets are bound to
# (via key=...). Setting these directly, then letting Streamlit's normal
# rerun-after-interaction cycle happen, is how a button on another page
# (like Overview's action cards) can jump the sidebar to a specific
# group+page without app.py and overview.py needing to call into each
# other directly.
NAV_GROUP_KEY = "nav_group_selection"
NAV_PAGE_KEY = "nav_page_selection"


def jump_to(group_label, page_label=None):
    """Callback for an st.button(..., on_click=...): points the sidebar
    nav at a specific group (and, for multi-page groups, a specific page
    within it) on the next rerun. Streamlit always reruns the script
    after a button click and runs on_click callbacks first, so by the
    time app.py's sidebar radios are instantiated on that rerun, they'll
    read this new value from session_state and render already-selected."""
    import streamlit as st

    st.session_state[NAV_GROUP_KEY] = group_label
    if page_label is not None:
        st.session_state[NAV_PAGE_KEY] = page_label
