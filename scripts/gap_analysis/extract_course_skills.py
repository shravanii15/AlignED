"""
extract_course_skills.py

What this script does, in plain terms:
Runs our fast, non-AI keyword matcher (the same logic proven out in
extract_baseline.py, reused here rather than copied) across every one of
the 1,378 real course descriptions in the database -- not just the small
104-item gold set -- and records which O*NET skills/knowledge/technologies
each course appears to cover. Results are written into the `extractions`
table, tagged method='baseline_keyword', so later steps (gap scoring) can
just query the database instead of re-parsing text.

Why the fast method here, not the local AI model:
We already proved (on the hand-labeled gold set) that the AI method is
somewhat more accurate. But running the AI model on 1,378 courses would
take hours on a laptop CPU. This is a deliberate, documented trade-off:
use the validated-but-slower method for accuracy proof, use the
fast-and-scalable method for full-corpus analysis. See the progress log
for the full reasoning.

This script is idempotent -- it clears out any previous 'course' +
'baseline_keyword' extractions before inserting fresh ones, so it can be
re-run safely any time the course data changes.
"""

import os
import sqlite3
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "extraction"))
from extract_baseline import build_combined_pattern, extract_terms_from_text_fast  # noqa: E402
from extract_common import load_vocabulary, normalize_term  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")


def main():
    print("Loading O*NET vocabulary...")
    vocabulary = load_vocabulary()
    term_lookup = {}
    for entry in vocabulary:
        key = normalize_term(entry["term"])
        if key not in term_lookup:
            term_lookup[key] = entry
    combined_pattern = build_combined_pattern([e["term"] for e in term_lookup.values()])
    print(f"  -> {len(term_lookup)} vocabulary terms loaded (compiled into one combined pattern).")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Map canonical_name -> skill_id, so we can insert extractions with a
    # real foreign key instead of a bare string.
    cur.execute("SELECT skill_id, canonical_name FROM skills")
    skill_id_by_name = {normalize_term(name): sid for sid, name in cur.fetchall()}

    cur.execute("SELECT course_id, course_name, description FROM courses")
    courses = cur.fetchall()
    print(f"\nExtracting skills for {len(courses)} courses...")

    cur.execute("DELETE FROM extractions WHERE source_type = 'course' AND method = 'baseline_keyword'")

    total_matches = 0
    courses_with_zero_matches = 0
    insert_rows = []
    for course_id, course_name, description in courses:
        text = f"{course_name or ''}. {description or ''}"
        found = extract_terms_from_text_fast(text, combined_pattern, term_lookup)
        if not found:
            courses_with_zero_matches += 1
        for entry in found:
            skill_id = skill_id_by_name.get(normalize_term(entry["term"]))
            if skill_id is None:
                continue  # shouldn't happen, but skip defensively
            insert_rows.append(("course", str(course_id), skill_id, 1.0, "baseline_keyword"))
        total_matches += len(found)

    cur.executemany(
        "INSERT INTO extractions (source_type, source_id, skill_id, confidence, method) VALUES (?, ?, ?, ?, ?)",
        insert_rows,
    )
    conn.commit()
    conn.close()

    avg = total_matches / len(courses) if courses else 0
    print(f"\nTotal skill matches across all courses: {total_matches}")
    print(f"Average matches per course: {avg:.1f}")
    print(f"Courses with zero matches: {courses_with_zero_matches} ({courses_with_zero_matches / len(courses) * 100:.1f}%)")
    print(f"\nSaved {len(insert_rows)} extraction rows to the extractions table.")
    print("Done.")


if __name__ == "__main__":
    main()
