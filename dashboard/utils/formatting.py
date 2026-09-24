"""
utils/formatting.py -- small display/output formatting helpers shared
across dashboard pages.
"""

import re


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
