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
    location = clean_text(row.get("location"))
    if location:
        details.append(location)
    lo, hi = _number_or_none(row.get("salary_min")), _number_or_none(row.get("salary_max"))
    if lo and hi and round(lo) != round(hi):
        details.append(f"${lo:,.0f} to ${hi:,.0f}")
    elif lo or hi:
        details.append(f"${(lo or hi):,.0f}")
    posted = clean_text(row.get("posted_date"))
    if posted:
        details.append(posted[:10])
    return "  ·  ".join(details) if details else None


_MISSING_TEXT = {"", "nan", "none", "null", "nat", "n/a"}


def clean_text(value):
    """Return a display string, or None when the value is missing.

    Database NULLs become None or NaN once they pass through pandas, and
    NaN is truthy, so a plain `if value:` check lets "nan" reach the
    screen. This is the one place that decides what counts as missing."""
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _MISSING_TEXT else text


def _number_or_none(value):
    """A positive float, or None for NULL, NaN, text or zero."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number > 0 else None


def posting_headline(row):
    """'Title, Company' with missing parts left out (never 'nan'/'None')."""
    title = clean_text(row.get("title")) or "Untitled posting"
    company = clean_text(row.get("company"))
    return f"{title}, {company}" if company else title


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
