"""
utils/constants.py -- shared display/analysis constants used across
multiple dashboard pages.

Pulling these into one module (rather than repeating them per page)
means a color or threshold only needs to change in one place, and it
mirrors the same "named, documented constant" pattern used in the
pipeline scripts (see scripts/gap_analysis/compute_gap_scores.py).
"""

# Priority-tier colors, used consistently across Program Explorer,
# Compare Programs, and the PDF/Excel exports so "high" always means the
# same shade everywhere in the product.
TIER_HEX = {"high": "#DC2626", "medium": "#D97706", "low": "#16A34A"}
TIER_RGB = {"high": (220, 38, 38), "medium": (217, 119, 6), "low": (22, 163, 74)}
TIER_FILL_HEX = {"high": "FCA5A5", "medium": "FCD34D", "low": "86EFAC"}

# How many of a role cluster's most in-demand skills count toward the
# "Build Your Profile" match score.
TOP_SKILLS_PER_CLUSTER = 15

# Real, honest limitation of keyword matching: a handful of official
# skill/knowledge category names are single, very common English words
# (e.g. "Design", "Science"). A plain keyword scanner can't tell these
# apart from unrelated everyday text (e.g. "design your career" vs. the
# actual skill), so they're excluded from analysis everywhere in the
# project -- gap scoring, trend detection, and here in the personal
# profile matcher -- to avoid noisy false positives. See
# scripts/gap_analysis/compute_gap_scores.py for the original version of
# this same exclusion list and the full reasoning.
AMBIGUOUS_GENERIC_TERMS = {
    "design", "science", "writing", "monitoring", "programming",
    "troubleshooting", "mathematics", "coordination", "instructing",
    "repairing", "speaking", "route", "ada",
}
