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

    # Everyday names people actually type ("Excel", "Power BI", "AWS") that
    # the official skill names spell out longer. Only applied when the
    # official skill is in the tracked vocabulary, so it can never invent one.
    by_name = {normalize_term(n): sid for sid, n in zip(tracked_df["skill_id"], tracked_df["canonical_name"])}
    for alias, official in SKILL_ALIASES.items():
        sid = by_name.get(normalize_term(official))
        if sid is not None and sid not in matched and _contains_term(user_text, alias):
            matched.add(sid)
    return matched


# everyday name -> official skill name used in the database
SKILL_ALIASES = {
    "excel": "Microsoft Excel",
    "ms excel": "Microsoft Excel",
    "power bi": "Microsoft Power BI",
    "powerbi": "Microsoft Power BI",
    "spark": "Apache Spark",
    "airflow": "Apache Airflow",
    "kafka": "Apache Kafka",
    "java": "Oracle Java",
    "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "terraform": "IBM Terraform",
    "looker": "Google Looker Analytics",
    "jupyter": "Jupyter Notebook",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "mongo": "MongoDB",
    "mssql": "Microsoft SQL Server",
    "sql server": "Microsoft SQL Server",
    "aws": "Amazon Web Services AWS software",
    "amazon web services": "Amazon Web Services AWS software",
    "azure": "Microsoft Azure software",
    "sql": "Structured query language SQL",
    "html": "Hypertext markup language HTML",
    "css": "Cascading style sheets CSS",
    "golang": "Go",
}


def _contains_term(text, term):
    return re.search(r"(?<![A-Za-z0-9_])" + re.escape(term) + r"(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


def unrecognized_items(user_text, tracked_df, limit=8):
    """Items from a comma/line separated skills list that matched nothing.

    Lets the page say "we did not recognize X" instead of staying silent,
    so a visitor who types a skill we do not track is never left guessing.
    Long free text (a resume paragraph) is skipped: only short list items
    are judged."""
    items = [p.strip(" \t-•*·") for p in re.split(r"[,;\n•·|]+", user_text or "")]
    out = []
    for item in items:
        if not item or len(item.split()) > 4 or len(item) > 40:
            continue
        if not extract_user_skills(item, tracked_df) and item.lower() not in {i.lower() for i in out}:
            out.append(item)
    return out[:limit]
