"""
extract_posting_skills.py

What this script does, in plain terms:
This is the market-demand half of extract_course_skills.py. It runs the
same fast keyword matcher across the 1,660 real job postings we already
sampled and clustered by role, and records which O*NET skills each
posting mentions into the `extractions` table (source_type='posting').

One extra step this script has to do that the course version didn't:
cluster_postings.py deliberately didn't keep each posting's full
description text in posting_clusters.json (only title/company/cluster),
since it wasn't needed for clustering. So this script re-reads the
original Kaggle postings CSV once, matches rows back to the postings we
already sampled (by job_id), and:
  1. Fills in the full description text on the postings table (useful
     later for the dashboard, e.g. "show me the actual posting").
  2. Extracts skills from title + description for the extractions table.

A real, honest debugging note: the postings CSV's description field
contains genuine embedded newlines inside quoted text (real job postings
are multi-paragraph), so this is NOT a simple one-row-per-line file --
Python's csv module handles that correctly on its own, but only if it can
read the file quickly. Reading directly from the mounted project folder
was slow enough to time out, so this script copies the CSV to fast local
disk first, then parses it there. (For the record: the file itself turned
out to be about 124,000 real postings, not the ~3.3 million raw physical
lines a naive `wc -l` count suggested -- the difference is exactly those
embedded newlines splitting single logical rows across multiple physical
lines.)

This script is idempotent, same as its course counterpart.
"""

import csv
import os
import shutil
import sqlite3
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "extraction"))
from extract_baseline import build_combined_pattern, extract_terms_from_text_fast  # noqa: E402
from extract_common import load_vocabulary, normalize_term  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
POSTINGS_CSV = os.path.join(BASE_DIR, "data", "kaggle_backfill", "postings.csv")
LOCAL_COPY_PATH = "/tmp/aligned_postings_local_copy.csv"


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

    cur.execute("SELECT skill_id, canonical_name FROM skills")
    skill_id_by_name = {normalize_term(name): sid for sid, name in cur.fetchall()}

    cur.execute("SELECT posting_id FROM postings WHERE source = 'kaggle_sample'")
    sample_posting_ids = {row[0] for row in cur.fetchall()}
    # These were saved with a "kaggle_" prefix; build a lookup back to the
    # raw job_id so we can match rows in the CSV.
    job_id_to_posting_id = {pid.replace("kaggle_", "", 1): pid for pid in sample_posting_ids}
    print(f"\nLooking for {len(job_id_to_posting_id)} sampled postings in the Kaggle CSV...")

    if not os.path.exists(LOCAL_COPY_PATH):
        print(f"\nCopying CSV to fast local disk first ({POSTINGS_CSV})...")
        t0 = time.time()
        shutil.copyfile(POSTINGS_CSV, LOCAL_COPY_PATH)
        print(f"  -> copied in {time.time() - t0:.1f}s.")
    else:
        print("\nLocal copy already exists, reusing it.")

    csv.field_size_limit(10_000_000)
    found_count = 0
    description_updates = []
    all_matches = []  # (posting_id, [matched entries])

    t0 = time.time()
    with open(LOCAL_COPY_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = row.get("job_id")
            if job_id not in job_id_to_posting_id:
                continue
            posting_id = job_id_to_posting_id[job_id]
            title = row.get("title") or ""
            description = row.get("description") or ""
            text = f"{title}. {description}"
            found = extract_terms_from_text_fast(text, combined_pattern, term_lookup)
            all_matches.append((posting_id, found))
            description_updates.append((description, posting_id))
            found_count += 1
    print(f"  -> scanned full CSV in {time.time() - t0:.1f}s.")
    print(f"  -> matched {found_count} of {len(job_id_to_posting_id)} sampled postings back to the CSV.")

    print("\nUpdating postings.description for matched rows...")
    cur.executemany("UPDATE postings SET description = ? WHERE posting_id = ?", description_updates)

    print("Inserting extraction rows...")
    cur.execute("DELETE FROM extractions WHERE source_type = 'posting' AND method = 'baseline_keyword'")

    insert_rows = []
    total_matches = 0
    postings_with_zero_matches = 0
    for posting_id, found in all_matches:
        if not found:
            postings_with_zero_matches += 1
        for entry in found:
            skill_id = skill_id_by_name.get(normalize_term(entry["term"]))
            if skill_id is None:
                continue
            insert_rows.append(("posting", posting_id, skill_id, 1.0, "baseline_keyword"))
        total_matches += len(found)

    cur.executemany(
        "INSERT INTO extractions (source_type, source_id, skill_id, confidence, method) VALUES (?, ?, ?, ?, ?)",
        insert_rows,
    )
    conn.commit()
    conn.close()

    avg = total_matches / found_count if found_count else 0
    print(f"\nTotal skill matches across all sampled postings: {total_matches}")
    print(f"Average matches per posting: {avg:.1f}")
    if found_count:
        print(f"Postings with zero matches: {postings_with_zero_matches} ({postings_with_zero_matches / found_count * 100:.1f}%)")
    print(f"\nSaved {len(insert_rows)} extraction rows to the extractions table.")
    print("Done.")


if __name__ == "__main__":
    main()
