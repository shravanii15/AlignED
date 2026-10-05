"""
utils/text.py: keyword-matching helpers shared by the dashboard.

Same normalization/combined-regex technique used in
scripts/extraction/extract_baseline.py, deliberately duplicated here
(not imported from scripts/) so the dashboard stays deployable on its
own, Streamlit Community Cloud only runs the dashboard/ folder, so a
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
    build_combined_pattern(), one compiled regex covering every term,
    scanned in a single pass instead of once per term."""
    terms_sorted = sorted(terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in terms_sorted]
    pattern = r"(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")(?![A-Za-z0-9_])"
    return re.compile(pattern, re.IGNORECASE)


SHORT_TERM_MAX_LEN = 2


def extract_user_skills(user_text, tracked_df):
    """Match free text (a resume, a skills list, or a job posting) against
    the tracked skill vocabulary, returning the set of matched skill_ids.

    Very short skill names ("R", "Go", "C") are matched case-sensitively,
    exactly as written in the vocabulary. Case-insensitively they would
    match ordinary words ("go to market", "r" in a typo) and add skills
    nobody mentioned. Longer names stay case-insensitive."""
    long_lookup, short_lookup = {}, {}
    for sid, name in zip(tracked_df["skill_id"], tracked_df["canonical_name"]):
        if len(str(name).strip()) <= SHORT_TERM_MAX_LEN:
            short_lookup[str(name).strip()] = sid
        else:
            long_lookup[normalize_term(name)] = sid

    matched = set()
    if long_lookup:
        pattern = build_combined_pattern(list(long_lookup.keys()))
        for m in pattern.finditer(user_text):
            sid = long_lookup.get(normalize_term(m.group(0)))
            if sid is not None:
                matched.add(sid)
    for name, sid in short_lookup.items():
        if re.search(r"(?<![A-Za-z0-9_+#])" + re.escape(name) + r"(?![A-Za-z0-9_+#])", user_text):
            matched.add(sid)
    return matched
