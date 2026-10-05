"""
utils/nav.py: shared navigation labels and the session-state keys that
drive the sidebar's two-tier navigation (group, then page within group).

Why this exists as its own module: app.py owns the actual page-function
dispatch (it has to import every render_* function), but the Overview
page's "jump straight to X" action cards also need to reference the
exact same group/page label strings so clicking a card actually lands on
the right page. Keeping the label strings here as named constants --
imported by both app.py and sections/overview.py, means they can never
silently drift out of sync with each other (a typo in one file would
just be a broken nav link with no error), instead of hand-typing the
same literal strings in two different files.
"""

# Sidebar section (group) labels. Redesign pass: no emojis at all, a
# research-tool sidebar uses small-caps text labels (styled in app.py's
# CSS), not icons, to read as a serious analytics product rather than a
# student Streamlit app. "Explore" was renamed to "Market Intelligence"
# since it names WHAT you'll find there, not just an action.
GROUP_OVERVIEW = "Home"
GROUP_ANALYZE = "Check a Program"
GROUP_EXPLORE = "Explore the Data"
GROUP_PERSONALIZE = "Plan My Skills"
GROUP_METHODOLOGY = "Methodology"

# Page labels within a group (only listed here where the Overview page's
# action cards need to jump directly to them). No emojis at this level --
# the group-level icon above is enough context, and a flat list of
# emoji-prefixed pages under an already-iconed group read as cluttered.
PAGE_PROGRAM_EXPLORER = "Skill Gaps"
PAGE_COMPARE = "Compare Programs"
PAGE_HEATMAP = "Skills by Program"
PAGE_TRENDS = "Rising and Falling Skills"
PAGE_ROLE_GROUPS = "Job Families"
PAGE_COURSE_FINDER = "Course Finder"
PAGE_MATCH_JOB = "Match a Job"
PAGE_BUILD_PROFILE = "Which Jobs Fit Me"
PAGE_METHODOLOGY = "Methodology & Limitations"

# The st.session_state keys the sidebar's two radio widgets are bound to
# (via key=...). Setting these directly, then letting Streamlit's normal
# rerun-after-interaction cycle happen, is how a button on another page
# (like Overview's action cards) can jump the sidebar to a specific
# group+page without app.py and overview.py needing to call into each
# other directly.
NAV_GROUP_KEY = "nav_group_selection"
NAV_PAGE_KEY = "nav_page_selection"

# Program Explorer's own two dropdowns are ALSO bound to session-state keys
# (see sections/program_explorer.py), so the Overview page's "Start an
# analysis" form can pre-fill them before jumping there, same pattern as
# the nav keys above: set the state, let Streamlit's normal
# rerun-after-interaction cycle carry it into the widget on the next render.
EXPLORER_PROGRAM_KEY = "explorer_program_label"
EXPLORER_ROLE_KEY = "explorer_role_label"


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


def jump_to_program_explorer(program_label=None, role_label=None):
    """Callback for the Overview page's 'Start an analysis' form: jumps to
    Program Explorer, optionally pre-filling its program/role dropdowns so
    a visitor's homepage selection carries straight through instead of
    having to be re-picked on the destination page."""
    import streamlit as st

    jump_to(GROUP_ANALYZE, PAGE_PROGRAM_EXPLORER)
    if program_label is not None:
        st.session_state[EXPLORER_PROGRAM_KEY] = program_label
    if role_label is not None:
        st.session_state[EXPLORER_ROLE_KEY] = role_label


# Course Finder's skill filter and the profile tool's input/run flag are
# also session-state keys, so a result card can send a visitor straight to
# "courses that teach this skill", and the homepage can start a skill plan.
COURSE_FINDER_SKILLS_KEY = "course_finder_skills"
PROFILE_TEXT_KEY = "profile_text"
PROFILE_RUN_KEY = "profile_run"


def jump_to_course_finder(skill_name):
    """Callback: open Course Finder pre-filtered to one skill."""
    import streamlit as st

    jump_to(GROUP_EXPLORE, PAGE_COURSE_FINDER)
    st.session_state[COURSE_FINDER_SKILLS_KEY] = [skill_name]


MATCH_JOB_TEXT_KEY = "match_job_text"
MATCH_RUN_KEY = "match_run"


def start_job_match(job_text):
    """Callback: open Match a Job with the pasted posting already in place."""
    import streamlit as st

    jump_to(GROUP_PERSONALIZE, PAGE_MATCH_JOB)
    st.session_state[MATCH_JOB_TEXT_KEY] = job_text
    st.session_state[MATCH_RUN_KEY] = False


def start_skill_plan(text):
    """Callback: open the skill plan with text already entered and the
    analysis already running."""
    import streamlit as st

    jump_to(GROUP_PERSONALIZE, PAGE_BUILD_PROFILE)
    st.session_state[PROFILE_TEXT_KEY] = text
    st.session_state[PROFILE_RUN_KEY] = bool(text and text.strip())
