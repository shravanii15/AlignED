"""
utils/layout.py: shared layout helpers so every page has the same visual
rhythm instead of each page hand-rolling its own header style.

page_header() renders a banner with a title, a one-line description,
optional highlight pills and a small illustration chosen by name
(`art`). The banner styling lives in app.py's CSS (.page-banner*).
"""

import streamlit as st

# Small, original SVG illustrations. Each is drawn on a 160x120 canvas in
# light colors so it reads on the dark banner background.
_ART = {
    "gaps": (  # two bar pairs: courses (green) vs postings (blue)
        '<rect x="14" y="70" width="18" height="34" rx="4" fill="#1F9D68"/><rect x="36" y="22" width="18" height="82" rx="4" fill="#4C7DFF"/>'
        '<rect x="70" y="92" width="18" height="12" rx="4" fill="#1F9D68"/><rect x="92" y="40" width="18" height="64" rx="4" fill="#4C7DFF"/>'
        '<rect x="126" y="86" width="18" height="18" rx="4" fill="#1F9D68"/><rect x="148" y="56" width="10" height="48" rx="4" fill="#4C7DFF"/>'
        '<line x1="8" y1="106" x2="158" y2="106" stroke="#94A3B8" stroke-width="2"/>'
    ),
    "compare": (  # two cards side by side
        '<rect x="12" y="20" width="62" height="84" rx="10" fill="#FFFFFF" opacity="0.95"/><rect x="86" y="20" width="62" height="84" rx="10" fill="#FFFFFF" opacity="0.95"/>'
        '<rect x="22" y="34" width="42" height="8" rx="4" fill="#4C7DFF"/><rect x="22" y="52" width="30" height="8" rx="4" fill="#D94A4A"/><rect x="22" y="70" width="36" height="8" rx="4" fill="#1F9D68"/>'
        '<rect x="96" y="34" width="30" height="8" rx="4" fill="#4C7DFF"/><rect x="96" y="52" width="42" height="8" rx="4" fill="#D94A4A"/><rect x="96" y="70" width="22" height="8" rx="4" fill="#1F9D68"/>'
    ),
    "grid": (  # heatmap
        "".join(
            f'<rect x="{14 + c * 30}" y="{14 + r * 26}" width="26" height="22" rx="5" fill="#4C7DFF" opacity="{o}"/>'
            for r, row in enumerate([(0.15, 0.9, 0.3, 0.1, 0.5), (0.7, 0.2, 0.1, 0.8, 0.25), (0.1, 0.45, 0.95, 0.3, 0.12), (0.6, 0.1, 0.35, 0.15, 0.85)])
            for c, o in enumerate(row)
        )
    ),
    "trend": (  # rising and falling lines
        '<polyline points="10,98 44,80 78,86 112,48 150,22" fill="none" stroke="#1F9D68" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="10,34 44,48 78,44 112,78 150,100" fill="none" stroke="#D94A4A" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="150" cy="22" r="7" fill="#1F9D68"/><circle cx="150" cy="100" r="7" fill="#D94A4A"/>'
    ),
    "families": (  # clustered bubbles
        '<circle cx="46" cy="42" r="26" fill="#4C7DFF" opacity="0.9"/><circle cx="74" cy="64" r="16" fill="#4C7DFF" opacity="0.6"/>'
        '<circle cx="112" cy="36" r="20" fill="#1F9D68" opacity="0.9"/><circle cx="130" cy="64" r="12" fill="#1F9D68" opacity="0.6"/>'
        '<circle cx="92" cy="94" r="18" fill="#F5B94C" opacity="0.9"/><circle cx="52" cy="96" r="10" fill="#F5B94C" opacity="0.6"/>'
    ),
    "search": (  # magnifier over lines
        '<rect x="12" y="24" width="84" height="10" rx="5" fill="#FFFFFF" opacity="0.5"/><rect x="12" y="46" width="64" height="10" rx="5" fill="#FFFFFF" opacity="0.5"/>'
        '<rect x="12" y="68" width="76" height="10" rx="5" fill="#FFFFFF" opacity="0.5"/>'
        '<circle cx="106" cy="62" r="26" fill="none" stroke="#FFFFFF" stroke-width="8"/><line x1="126" y1="84" x2="150" y2="108" stroke="#FFFFFF" stroke-width="9" stroke-linecap="round"/>'
    ),
    "match": (  # checklist
        '<rect x="22" y="10" width="116" height="100" rx="12" fill="#FFFFFF" opacity="0.95"/>'
        '<path d="M36 36l8 8 14-16" fill="none" stroke="#1F9D68" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><rect x="68" y="32" width="56" height="8" rx="4" fill="#CBD5E1"/>'
        '<path d="M36 66l8 8 14-16" fill="none" stroke="#1F9D68" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><rect x="68" y="62" width="44" height="8" rx="4" fill="#CBD5E1"/>'
        '<circle cx="46" cy="92" r="9" fill="none" stroke="#D94A4A" stroke-width="5"/><rect x="68" y="88" width="52" height="8" rx="4" fill="#CBD5E1"/>'
    ),
    "fit": (  # target
        '<circle cx="80" cy="60" r="48" fill="none" stroke="#FFFFFF" stroke-width="6" opacity="0.5"/><circle cx="80" cy="60" r="30" fill="none" stroke="#FFFFFF" stroke-width="6" opacity="0.75"/>'
        '<circle cx="80" cy="60" r="12" fill="#4C7DFF"/><line x1="80" y1="60" x2="134" y2="14" stroke="#F5B94C" stroke-width="6" stroke-linecap="round"/><circle cx="134" cy="14" r="7" fill="#F5B94C"/>'
    ),
    "method": (  # layered stack
        '<path d="M80 14l62 28-62 28-62-28z" fill="#4C7DFF"/><path d="M18 62l62 28 62-28" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linejoin="round" opacity="0.85"/>'
        '<path d="M18 84l62 28 62-28" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linejoin="round" opacity="0.55"/>'
    ),
}

# Banner gradient per art, so each page has its own accent while the set stays cohesive.
_GRADIENT = {
    "gaps": ("#0B1220", "#1E3A8A"),
    "compare": ("#0B1220", "#4338CA"),
    "grid": ("#0B1220", "#155E75"),
    "trend": ("#0B1220", "#166534"),
    "families": ("#0B1220", "#6D28D9"),
    "search": ("#0B1220", "#9A3412"),
    "match": ("#0B1220", "#0F766E"),
    "fit": ("#0B1220", "#1D4ED8"),
    "method": ("#0B1220", "#334155"),
}


def page_header(icon, title, description=None, art=None, pills=()):
    """Render a page banner. `icon` is kept for backward compatibility and
    ignored; `art` is a key of _ART; `pills` is a short list of strings."""
    start, end = _GRADIENT.get(art, ("#0B1220", "#16213A"))
    svg = (
        f'<svg class="page-banner-art" viewBox="0 0 160 120" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{_ART[art]}</svg>'
        if art in _ART else ""
    )
    pill_html = "".join(f"<span>{p}</span>" for p in pills)
    desc_html = f'<p class="page-banner-desc">{description}</p>' if description else ""
    st.markdown(
        f"""
        <div class="page-banner" style="background: linear-gradient(135deg, {start} 0%, {end} 100%);">
            <div class="page-banner-text">
                <p class="page-banner-title">{title}</p>
                {desc_html}
                <div class="page-banner-pills">{pill_html}</div>
            </div>
            {svg}
        </div>
        """,
        unsafe_allow_html=True,
    )
