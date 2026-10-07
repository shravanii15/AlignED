"""
utils/formatting.py: small display/output formatting helpers shared
across dashboard pages.
"""

import re


PROGRAM_LABEL_SEPARATOR = " · "


def program_label(university, program_name):
    """The one place a program's display label is built. Used by every
    page that shows or matches a program by its label (including the
    Overview -> Program Explorer pre-fill), so the strings can never
    drift apart."""
    return f"{university}{PROGRAM_LABEL_SEPARATOR}{program_name}"


def evidence_strength(q_value):
    """Plain-language label for how strong the statistical evidence for a
    gap is. Every gap shown on the dashboard already passed the
    FDR-corrected significance bar (q < 0.05); this just grades how far
    below that bar it sits, so non-technical readers get a word instead
    of a decimal."""
    if q_value is None:
        return "Not available"
    if q_value < 0.001:
        return "Very strong"
    if q_value < 0.01:
        return "Strong"
    return "Moderate"


def format_posting_details(row):
    """Plain-text detail line for a job posting (location, salary,
    posted date), or None when the posting has none of them."""
    details = []
    if row.get("location"):
        details.append(str(row["location"]))
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if lo or hi:
        details.append(f"${lo:,.0f} to ${hi:,.0f}" if lo and hi else f"${(lo or hi):,.0f}")
    if row.get("posted_date"):
        details.append(str(row["posted_date"]))
    return "  ·  ".join(details) if details else None


def safe_filename(text):
    """Turn an arbitrary label (program name, role label, etc.) into a
    string safe to use as a filename on any OS.

    Bug this fixes: download filenames were previously built with just
    `.replace(" ", "_")`, which leaves characters like "/" untouched --
    role labels such as "Data Science / Data Engineering" produced a
    literal "/" in the filename, which isn't a valid filename character
    on Windows and silently gets treated as a path separator on
    Mac/Linux, breaking the download. This strips anything that isn't a
    letter, digit, dot, underscore, or hyphen, collapsing runs of
    stripped characters into a single underscore.
    """
    if text is None:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text))
    return cleaned.strip("_")


NAMED_WELL_AT = 0.05  # a skill counts as "named" when 5% or more of a program's courses name it


def status_for(coverage):
    """Plain label for how often a program's course descriptions name a skill."""
    if coverage <= 0:
        return "Not named"
    if coverage < NAMED_WELL_AT:
        return "Rarely named"
    return "Named"
