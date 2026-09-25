"""
utils/charts.py -- one shared Plotly visual theme applied to every chart
in the dashboard, instead of each page inventing its own margins, grid
style, and colors.

Why this exists: before this, charts used Plotly's default look
(borders, heavy gridlines, default font, inconsistent margins) on some
pages and ad-hoc tweaks on others, so the dashboard's charts didn't read
as one product. apply_chart_theme() applies one consistent, restrained
style -- subtle gridlines, no chart border, consistent font/margins --
matching the semantic color roles used elsewhere in the CSS (gap red,
market blue, coverage green).
"""

TEXT = "#101828"
TEXT_MUTED = "#667085"
BORDER = "#E4E7EC"
BRAND = "#315CF5"
GAP_RED = "#D94A4A"
MARKET_BLUE = "#4C7DFF"
COVERAGE_GREEN = "#1F9D68"

TIER_COLOR_MAP = {"high": GAP_RED, "medium": "#E08A3C", "low": COVERAGE_GREEN}


def apply_chart_theme(fig, height=None):
    """Apply the shared visual theme to a Plotly figure in place-ish
    (Plotly's update_layout returns the same figure) and return it, so
    call sites can chain it: `fig = apply_chart_theme(px.bar(...))`."""
    fig.update_layout(
        font=dict(family="Helvetica, Arial, sans-serif", color=TEXT, size=13),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, bordercolor=BORDER),
    )
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(showgrid=True, gridcolor=BORDER, gridwidth=1, zeroline=False, linecolor=BORDER)
    fig.update_yaxes(showgrid=False, zeroline=False, linecolor=BORDER)
    return fig
