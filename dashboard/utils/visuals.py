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


_PLANK = {  # status -> (fill, stroke, text color, dash, caption)
    "ok": ("#1F9D68", "#4ADE9A", "#FFFFFF", "", "taught"),
    "warn": ("#F5A524", "#FFD27A", "#3B2A00", "", "rare"),
    "no": ("rgba(217,74,74,0.12)", "#FF7A7A", "#FFB4B4", "5 4", "missing"),
}


def bridge_svg(items):
    """Suspension-bridge illustration: the degree on the left, the job on
    the right, and one plank per skill. A solid green plank means courses
    teach the skill; a dashed red plank is a missing board in the bridge.
    `items` is a list of (skill_name, status) with status in ok/warn/no."""
    n = len(items)
    plank_w, gap = 78, 6
    deck_w = n * plank_w + (n - 1) * gap
    left_w = right_w = 112
    width = left_w + deck_w + right_w + 24
    x0 = left_w + 12            # deck start
    deck_y = 198
    planks, hangers = [], []
    for i, (name, status) in enumerate(items):
        fill, stroke, txt, dash, _ = _PLANK[status]
        x = x0 + i * (plank_w + gap)
        planks.append(
            f'<rect x="{x}" y="{deck_y}" width="{plank_w}" height="34" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="2"'
            + (f' stroke-dasharray="{dash}"' if dash else "")
            + "/>"
            f'<text x="{x + plank_w/2}" y="{deck_y + 21}" text-anchor="middle" font-size="12" font-weight="700" fill="{txt}">{html.escape(name)}</text>'
        )
        hx = x + plank_w / 2
        t = (hx - x0 + plank_w / 2) / deck_w
        cable_y = 70 + 4 * 84 * (t - 0.5) ** 2 * 1.0  # parabola, lowest in the middle
        hangers.append(f'<line x1="{hx}" y1="{cable_y:.1f}" x2="{hx}" y2="{deck_y}" stroke="#7C8DB5" stroke-width="2" opacity="0.7"/>')
    xl_top, xr_top = left_w - 10, x0 + deck_w + 22  # towers mirror each other, 10px onto each cliff
    cable = (
        f'<path d="M {xl_top} 70 Q {(xl_top + xr_top)/2} 160 {xr_top} 70" fill="none" stroke="#A9B8E0" stroke-width="3.5" stroke-linecap="round"/>'
    )
    # cable parabola for hangers must match the quadratic: recompute hanger tops on that curve
    hangers = []
    for i in range(n):
        hx = x0 + i * (plank_w + gap) + plank_w / 2
        t = (hx - xl_top) / (xr_top - xl_top)
        y = (1 - t) ** 2 * 70 + 2 * (1 - t) * t * 160 + t ** 2 * 70
        hangers.append(f'<line x1="{hx:.1f}" y1="{y:.1f}" x2="{hx:.1f}" y2="{deck_y}" stroke="#7C8DB5" stroke-width="2" opacity="0.75"/>')
    cap = (  # graduation cap
        '<g transform="translate(34 178)"><path d="M20 0 L40 9 L20 18 L0 9 Z" fill="#FFFFFF"/>'
        '<path d="M9 14 v9 q11 8 22 0 v-9 l-11 5 z" fill="#CBD5F5"/><line x1="40" y1="9" x2="40" y2="22" stroke="#FFFFFF" stroke-width="2"/></g>'
    )
    bx = xr_top + 24
    briefcase = (
        f'<g transform="translate({bx} 162)"><rect x="0" y="8" width="40" height="28" rx="5" fill="#FFFFFF"/>'
        '<path d="M13 8 v-4 a3 3 0 0 1 3 -3 h8 a3 3 0 0 1 3 3 v4" fill="none" stroke="#CBD5F5" stroke-width="3"/>'
        '<rect x="0" y="19" width="40" height="3" fill="#CBD5F5"/></g>'
    )
    return (
        f'<svg class="bridge-svg" viewBox="0 0 {width} 300" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-label="A bridge from your degree to a job, with one plank per skill" font-family="Helvetica, Arial, sans-serif">'
        # cliffs
        f'<path d="M0 214 L0 300 L{left_w} 300 L{left_w} 214 Q{left_w - 20} 206 {left_w - 40} 206 L0 206 Z" fill="#26325A"/>'
        f'<rect x="0" y="206" width="{left_w}" height="10" rx="4" fill="#3A4A7D"/>'
        f'<path d="M{width - right_w} 214 L{width - right_w} 300 L{width} 300 L{width} 206 L{width - right_w + 40} 206 Q{width - right_w + 20} 206 {width - right_w} 214 Z" fill="#26325A"/>'
        f'<rect x="{width - right_w}" y="206" width="{right_w}" height="10" rx="4" fill="#3A4A7D"/>'
        # towers
        f'<rect x="{xl_top - 4}" y="66" width="8" height="144" rx="3" fill="#A9B8E0"/>'
        f'<rect x="{xr_top - 4}" y="66" width="8" height="144" rx="3" fill="#A9B8E0"/>'
        + cable + "".join(hangers) + "".join(planks) + cap + briefcase +
        f'<text x="{left_w/2}" y="272" text-anchor="middle" font-size="11" font-weight="700" fill="#AEBBE6" letter-spacing="1">YOUR DEGREE</text>'
        f'<text x="{width - right_w/2}" y="272" text-anchor="middle" font-size="11" font-weight="700" fill="#AEBBE6" letter-spacing="1">THE JOB</text>'
        "</svg>"
    )
