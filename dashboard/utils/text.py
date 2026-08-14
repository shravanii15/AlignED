"""
utils/text.py -- keyword-matching helpers shared by the dashboard.

Same normalization/combined-regex technique used in
scripts/extraction/extract_baseline.py, deliberately duplicated here
(not imported from scripts/) so the dashboard stays deployable on its
own -- Streamlit Community Cloud only runs the dashboard/ folder, so a
cross-folder import back into scripts/ would break that deployment.
"""

import re

from utils.constants import AMBIGUOUS_GENERIC_TERMS  # noqa: F401  (re-exported for callers that filter with it)


def normalize_term(term):
    """Same normalization rule used throughout the extraction pipeline
    (lowercase + collapse whitespace)."""
    if term is None:
        return ""
    return " ".join(str(term).strip().lower().split())


def build_combined_pattern(terms):
    """Same technique as scripts/extraction/extract_baseline.py's
    build_combined_pattern() -- one compiled regex covering every term,
    scanned in a single pass instead of once per term."""
    terms_sorted = sorted(terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in terms_sorted]
    pattern = r"(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")(?![A-Za-z0-9_])"
    return re.compile(pattern, re.IGNORECASE)


def extract_user_skills(user_text, tracked_df):
    """Match a free-text paste (resume/skills list) against the tracked
    skill vocabulary, returning the set of matched skill_ids."""
    term_lookup = {normalize_term(name): sid for sid, name in zip(tracked_df["skill_id"], tracked_df["canonical_name"])}
    pattern = build_combined_pattern(list(term_lookup.keys()))
    matched = set()
    for m in pattern.finditer(user_text.lower()):
        sid = term_lookup.get(normalize_term(m.group(0)))
        if sid is not None:
            matched.add(sid)
    return matched
