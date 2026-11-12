"""services/own_program.py: run AlignED's gap analysis on a course list the visitor provides.

Same method as the pipeline: skills are found with the keyword matcher, each skill's share of the visitor's courses
is compared with its share of the 1,660 sampled job postings using the same z-test or Fisher's exact test, and
Benjamini-Hochberg correction is applied across the tested skills. Nothing is stored."""

import csv
import io

from services.stats import benjamini_hochberg, compare_proportions
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.text import extract_user_skills

MAX_COURSES = 400
MAX_CHARS_PER_COURSE = 5000
MAX_FILE_BYTES = 2 * 1024 * 1024
MIN_MARKET_MENTIONS = 10   # same threshold as scripts/gap_analysis/compute_gap_scores.py
SIGNIFICANCE = 0.05
SMALL_CORPUS = 30          # below this the Skill Gaps page also warns that a small corpus can miss skills

_DESC_NAMES = ("description", "course_description", "desc", "text", "summary", "syllabus")
_TITLE_NAMES = ("course_name", "title", "name", "course")


class CourseInputError(ValueError):
    """The provided text or file cannot be read as a course list. The message is safe to show to the visitor."""


def parse_pasted(text):
    """Courses separated by blank lines; if there are none, one course per non-empty line."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        raise CourseInputError("Paste at least one course description.")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) == 1:
        blocks = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return _clean(blocks)


def parse_csv(data):
    if len(data) > MAX_FILE_BYTES:
        raise CourseInputError("That file is larger than 2 MB. Split it or paste fewer courses.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CourseInputError("Save the file as UTF-8 CSV and try again.") from None
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or not rows[0]:
        raise CourseInputError("The CSV has no rows. It needs a header row and one row per course.")
    cols = {c.lower().strip(): c for c in rows[0] if c}
    desc = next((cols[n] for n in _DESC_NAMES if n in cols), None)
    if desc is None:  # fall back to the column with the longest text
        desc = max(rows[0], key=lambda c: sum(len(r.get(c) or "") for r in rows[:50]))
    title = next((cols[n] for n in _TITLE_NAMES if n in cols and cols[n] != desc), None)
    texts = [f"{(r.get(title) or '').strip()}. {(r.get(desc) or '').strip()}" if title else (r.get(desc) or "").strip() for r in rows]
    return _clean(texts)


def _clean(texts):
    texts = [t[:MAX_CHARS_PER_COURSE] for t in texts if t and t.strip(" .")]
    if not texts:
        raise CourseInputError("No course text was found.")
    if len(texts) > MAX_COURSES:
        raise CourseInputError(f"That is {len(texts)} courses. The limit is {MAX_COURSES}.")
    return texts


def analyze(course_texts, tracked_df, market_counts, total_postings):
    """Gaps for the given courses. `tracked_df` has skill_id and canonical_name; `market_counts` maps skill_id to the
    number of sampled postings that mention it. Returns a list of dicts for ALL tested skills, sorted by gap size,
    with `significant` set for positive gaps with q < 0.05."""
    n = len(course_texts)
    covered = {}
    for text in course_texts:
        for sid in extract_user_skills(text, tracked_df):
            covered[sid] = covered.get(sid, 0) + 1
    names = dict(zip(tracked_df["skill_id"], tracked_df["canonical_name"]))
    tested = [sid for sid, cnt in market_counts.items()
              if cnt >= MIN_MARKET_MENTIONS and sid in names and names[sid].strip().lower() not in AMBIGUOUS_GENERIC_TERMS]
    rows = []
    for sid in tested:
        x1, x2 = covered.get(sid, 0), market_counts[sid]
        p, method = compare_proportions(x1, n, x2, total_postings)
        rows.append({"skill": names[sid], "your_courses": x1, "your_rate": x1 / n, "market_rate": x2 / total_postings,
                     "gap": x2 / total_postings - x1 / n, "p_value": p, "test": method})
    for row, q in zip(rows, benjamini_hochberg([r["p_value"] for r in rows])):
        row["q_value"] = q
        row["significant"] = bool(row["gap"] > 0 and q < SIGNIFICANCE)
    rows.sort(key=lambda r: -r["gap"])
    return rows
