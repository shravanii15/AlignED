"""
utils/layout.py: shared layout helpers so every page has the same visual
rhythm instead of each page hand-rolling its own header style.

page_header() renders a large document-style title with a thin rule under
it (styled in app.py's CSS) and an optional one-line description.
"""

import streamlit as st


def page_header(icon, title, description=None):
    """Render a consistent page header. `icon` is optional (pass "" or
    None for a text-only title); description is an optional short line."""
    icon_html = f'<span class="page-header-icon">{icon}</span>' if icon else ""
    st.markdown(
        f"""
        <div class="page-header">
            {icon_html}<span class="page-header-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(f'<p class="page-header-desc">{description}</p>', unsafe_allow_html=True)
