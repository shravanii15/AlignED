"""
extract_posting_trends.py

What this script does, in plain terms:
Everything so far (course coverage, market demand, gap scores) has treated
"the job market" as one single snapshot in time. This script adds the
missing time dimension: for every one of the ~124,000 real historical job
postings (not just the 1,660-posting sample used for gap scoring), it
records which week the posting was listed and which in-demand skills it
mentions, so the next script (compute_skill_trends.py) can answer "is
demand for this skill going up or down?" instead of just "how much demand
is there right now?"

Scope decisions made on purpose, and why:
- We only search for the ~70 named-technology / meaningfully-specific
  skills already identified as relevant during gap scoring (Python,
  Docker, Kubernetes, etc.) -- not the full ~1,600-term vocabulary. This
  keeps each document's scan fast (searching for 70 terms instead of
  1,600 is roughly 20x faster) and keeps the story focused: we already
  know these are the skills worth tracking.
- This script is checkpointed and resumable, the same pattern used for
  the local AI extraction pipeline in Week 2: scanning all ~124,000
  postings takes longer than a single run comfortably allows in this
  environment, so it saves progress to a checkpoint file and can simply
  be re-run to pick up where it left off, with no repeated work and no
  risk of losing progress partway through.
- The historical dataset only spans about 4.5 months (Dec 2023-Apr 2024).
  That's honestly a short window for "forecasting" in the textbook sense
  -- it's better described as early trend detection than a mature
  time-series forecast. This is a known, stated limitation, not an
  oversight; the live daily Adzuna pipeline (built in Week 1) keeps
  extending this window every single day going forward.
"""

import csv
import json
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "extraction"))
from extract_baseline import build_combined_pattern, extract_terms_from_text_fast  # noqa: E402
from extract_common import normalize_term  # noqa: E402

import sqlite3  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
LOCAL_COPY_PATH = "/tmp/aligned_postings_local_copy.csv"
POSTINGS_CSV = os.path.join(BASE_DIR, "data", "kaggle_backfill", "postings.csv")
CHECKPOINT_PATH = os.path.join(BASE_DIR, "data", "gap_analysis", "trend_extraction_checkpoint.json")

# Only track skills already shown to have meaningful market signal during
# gap scoring (>= 10 mentions in the sample), minus the generic ambiguous
# terms excluded there too, for the same reasons.
MIN_MARKET_MENTIONS = 10
AMBIGUOUS_GENERIC_TERMS = {
    "design", "science", "writing", "monitoring", "programming",
    "troubleshooting", "mathematics", "coordination", "instructing",
    "repairing",
}

# Leave a safety margin before this environment's per-command time limit
# so we always get a chance to save a clean checkpoint before being cut
# off mid-row.
TIME_BUDGET_SECONDS = 150


def week_bucket(epoch_millis):
    """Convert a raw epoch-milliseconds timestamp into a 'YYYY-Www' week
    label, e.g. '2024-W03'. Weekly (not monthly) buckets give us more data
    points to work with across the dataset's ~4.5 month span."""
    import datetime
    dt = datetime.datetime.utcfromtimestamp(float(epoch_millis) / 1000)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_job_ids": [], "week_totals": {}, "skill_week_counts": {}, "done": False}


def save_checkpoint(state):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main():
    start_time = time.time()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.skill_id, s.canonical_name FROM skills s
        JOIN (
            SELECT skill_id, COUNT(DISTINCT source_id) c FROM extractions
            WHERE source_type = 'posting' AND method = 'baseline_keyword'
            GROUP BY skill_id HAVING c >= ?
        ) t ON s.skill_id = t.skill_id
        """,
        (MIN_MARKET_MENTIONS,),
    )
    relevant_skills = [(sid, name) for sid, name in cur.fetchall() if name.strip().lower() not in AMBIGUOUS_GENERIC_TERMS]
    conn.close()
    print(f"Tracking {len(relevant_skills)} relevant skills across the full posting history.")

    term_lookup = {normalize_term(name): {"term": name, "skill_id": sid} for sid, name in relevant_skills}
    combined_pattern = build_combined_pattern([name for _, name in relevant_skills])

    if not os.path.exists(LOCAL_COPY_PATH):
        print(f"Copying CSV to fast local disk ({POSTINGS_CSV})...")
        import shutil
        shutil.copyfile(POSTINGS_CSV, LOCAL_COPY_PATH)

    state = load_checkpoint()
    already_processed = set(state["processed_job_ids"])
    print(f"Resuming: {len(already_processed)} postings already processed in a previous run.")

    csv.field_size_limit(10_000_000)
    newly_processed = 0
    with open(LOCAL_COPY_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = row.get("job_id")
            if job_id is None or job_id in already_processed:
                continue

            if time.time() - start_time > TIME_BUDGET_SECONDS:
                print(f"\nTime budget reached ({TIME_BUDGET_SECONDS}s). Saving checkpoint and stopping early.")
                # Important: processed_job_ids must be updated here too, not
                # just at the very end -- otherwise a resumed run would have
                # no record of which postings were already counted, and
                # would double-count them into week_totals/skill_week_counts
                # on the next run. (Caught this exact bug during testing.)
                state["processed_job_ids"] = list(already_processed)
                save_checkpoint(state)
                print(f"Processed {newly_processed} new postings this run ({len(already_processed)} total).")
                print("Re-run this script to continue from here.")
                return

            date_raw = row.get("original_listed_time") or row.get("listed_time")
            if not date_raw:
                already_processed.add(job_id)
                continue
            try:
                week = week_bucket(date_raw)
            except (ValueError, OSError):
                already_processed.add(job_id)
                continue

            text = f"{row.get('title', '')}. {row.get('description', '')}"
            found = extract_terms_from_text_fast(text, combined_pattern, term_lookup)

            state["week_totals"][week] = state["week_totals"].get(week, 0) + 1
            for entry in found:
                skill_id = str(entry["skill_id"])
                bucket = state["skill_week_counts"].setdefault(skill_id, {})
                bucket[week] = bucket.get(week, 0) + 1

            already_processed.add(job_id)
            newly_processed += 1

    state["processed_job_ids"] = list(already_processed)
    state["done"] = True
    save_checkpoint(state)
    print(f"\nAll postings processed. {newly_processed} new this run, {len(already_processed)} total.")
    print(f"Weeks covered: {sorted(state['week_totals'].keys())}")
    print("Done. Next: run compute_skill_trends.py")


if __name__ == "__main__":
    main()
