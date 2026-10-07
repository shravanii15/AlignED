"""scripts/ingest/quality.py: normalise, validate and fingerprint postings.

Pure functions with no I/O, so every rule is unit tested. A posting is a
plain dict with the columns of the `postings` table.

Rules, in order of severity:
  reject   the posting is unusable and is recorded in rejected_postings
           (no id, no title, description too short to extract skills from,
           unreadable or future date)
  repair   a field is wrong but the posting is still useful, so the field is
           blanked and a warning is counted (impossible salary range)
  dedupe   handled by the loader: the same id, or the same content under a
           different id (a repost), is skipped
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone

MIN_DESCRIPTION_CHARS = 100
MAX_FUTURE_DAYS = 1
MAX_SALARY = 2_000_000

REJECT_NO_ID = "missing_id"
REJECT_NO_TITLE = "missing_title"
REJECT_SHORT_DESCRIPTION = "description_too_short"
REJECT_BAD_DATE = "unreadable_or_future_date"
WARN_BAD_SALARY = "salary_blanked"


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_adzuna(job, source="adzuna"):
    """Map one raw Adzuna API result to a `postings` row dict."""
    company = (job.get("company") or {}).get("display_name")
    location = (job.get("location") or {}).get("display_name")
    return {
        "posting_id": _clean(job.get("id")),
        "source": source,
        "title": _clean(job.get("title")),
        "company": _clean(company) or None,
        "location": _clean(location) or None,
        "description": _clean(job.get("description")),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "posted_date": _clean(job.get("created")) or None,
    }


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # drop NaN


def validate_posting(posting, now=None):
    """Return (clean_posting, rejection_reason, warnings).

    `rejection_reason` is None when the posting is acceptable. The returned
    posting is a repaired copy, never the input object."""
    now = now or datetime.now(timezone.utc)
    p = dict(posting)
    warnings = []

    if not p.get("posting_id"):
        return p, REJECT_NO_ID, warnings
    if not p.get("title"):
        return p, REJECT_NO_TITLE, warnings
    if len(p.get("description") or "") < MIN_DESCRIPTION_CHARS:
        return p, REJECT_SHORT_DESCRIPTION, warnings

    posted = _parse_date(p.get("posted_date"))
    if posted is None:
        return p, REJECT_BAD_DATE, warnings
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    if posted > now + timedelta(days=MAX_FUTURE_DAYS):
        return p, REJECT_BAD_DATE, warnings

    lo, hi = _as_number(p.get("salary_min")), _as_number(p.get("salary_max"))
    bad = (
        (lo is not None and (lo < 0 or lo > MAX_SALARY))
        or (hi is not None and (hi < 0 or hi > MAX_SALARY))
        or (lo is not None and hi is not None and lo > hi)
    )
    if bad:
        lo = hi = None
        warnings.append(WARN_BAD_SALARY)
    p["salary_min"], p["salary_max"] = lo, hi
    return p, None, warnings


def content_hash(posting):
    """Fingerprint of what a posting says, independent of its id, so a repost
    under a new id is recognised. Title, company and the start of the
    description, lower-cased and whitespace-collapsed."""
    basis = "|".join(
        [
            _clean(posting.get("title")).lower(),
            _clean(posting.get("company")).lower(),
            _clean(posting.get("description")).lower()[:500],
        ]
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]
