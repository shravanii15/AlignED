"""utils/visuals.py: small reusable HTML/SVG visual components (progress
ring, stat tiles, mini bars) shared by the pages, so each page can show a
picture of the answer instead of only text. Styling is in app.py's CSS."""

import html

import streamlit as st

RING_RADIUS = 52
RING_CIRCUMFERENCE = 2 * 3.14159265 * RING_RADIUS


def ring_svg(fraction, center_text, caption="", color="#1F9D68", size=140):
    """Donut progress ring. `fraction` in 0..1."""
    fraction = max(0.0, min(1.0, fraction))
    dash = RING_CIRCUMFERENCE * fraction
    return (
        '<div class="ring-wrap">'
        f'<svg viewBox="0 0 140 140" width="{size}" height="{size}" aria-hidden="true">'
        f'<circle cx="70" cy="70" r="{RING_RADIUS}" fill="none" stroke="#E4E7EC" stroke-width="14"/>'
        f'<circle cx="70" cy="70" r="{RING_RADIUS}" fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.1f} {RING_CIRCUMFERENCE:.1f}" transform="rotate(-90 70 70)"/>'
        f'<text x="70" y="78" text-anchor="middle" font-size="30" font-weight="800" fill="#101828" font-family="inherit">{html.escape(center_text)}</text>'
        "</svg>"
        f'<div class="ring-caption">{html.escape(caption)}</div>'
        "</div>"
    )


def stat_tiles(tiles):
    """Row of big-number tiles. `tiles` is a list of (value, label) tuples."""
    cells = "".join(
        f'<div class="stat-tile"><div class="stat-tile-value">{html.escape(str(v))}</div>'
        f'<div class="stat-tile-label">{html.escape(l)}</div></div>'
        for v, l in tiles
    )
    st.markdown(f'<div class="stat-tile-row">{cells}</div>', unsafe_allow_html=True)


def mini_bar(fraction, color="#4C7DFF"):
    fraction = max(0.0, min(1.0, fraction))
    return (
        f'<div class="mini-track"><div class="mini-fill" style="width:{fraction*100:.0f}%;background:{color}"></div></div>'
    )
