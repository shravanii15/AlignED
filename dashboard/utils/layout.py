"""
utils/layout.py -- shared layout helpers so every page has the same
visual rhythm instead of each page hand-rolling its own header style.

Before this, some pages used st.title() + a markdown paragraph, others
jumped straight into content with no framing at all -- inconsistent
enough that the 9 pages didn't feel like one product. page_header()
standardizes it.

Redesign pass: this used to render a filled colored box (icon in a blue
strip) -- replaced with a thin bottom rule and a large document-style
title, closer to a research paper section heading than app chrome. The
icon is kept (small, muted) for a little visual variety across pages
without dominating the layout.
"""

import streamlit as st


def page_header(icon, title, description=None):
    """Render a consistent page header: a large title with a small muted
    icon, a thin rule underneath, and an optional one-line description.
    Use at the top of every page's render_*() function in place of a
    bare st.title()."""
    st.markdown(
        f"""
        <div class="page-header">
            <span class="page-header-icon">{icon}</span>
            <span class="page-header-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(f'<p class="page-header-desc">{description}</p>', unsafe_allow_html=True)
