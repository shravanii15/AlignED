"""
market_pulse.py: the weekly refresh of "what employers ask for right now".

    python scripts/market_pulse.py            # reads data/raw/adzuna/*.json, writes data/market_pulse/latest.json

What it does, in plain terms:
  1. Replays every saved daily Adzuna snapshot in memory (same validation and
     de-duplication as the daily ingestion) so each posting is counted once.
  2. Finds O*NET skills in each posting with the same keyword method used for
     the main analysis (the method that won the held-out test).
  3. Compares each skill's share of recent postings with its share of the fixed
     1,660-posting historical sample, with the same significance test and
     Benjamini-Hochberg correction used for gaps.
  4. Writes one small JSON file that the dashboard displays, with a "last
     updated" date.

What it deliberately does NOT do: change gap_scores, recommendations or trends.
Those stay tied to the fixed sample so published numbers never move silently.
Because the output is derived only from committed raw snapshots plus the
committed database, it can be regenerated at any time (no 9 MB binary is
committed every week).
"""

import argparse
import glob
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
for sub in ("", "ingest", "extraction", "gap_analysis"):
    sys.path.insert(0, os.path.join(SCRIPTS_DIR, sub))

from compute_gap_scores import AMBIGUOUS_GENERIC_TERMS, apply_fdr_correction, compare_proportions  # noqa: E402
from extract_baseline import build_combined_pattern, extract_terms_from_text_fast  # noqa: E402
from extract_common import load_vocabulary, normalize_term  # noqa: E402
from quality import content_hash, normalize_adzuna, validate_posting  # noqa: E402

DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
SNAPSHOT_DIR = os.path.join(BASE_DIR, "data", "raw", "adzuna")
OUT_PATH = os.path.join(BASE_DIR, "data", "market_pulse", "latest.json")

TEXT_WINDOW_CHARS = 500        # Adzuna returns only the first ~500 characters of a description
MIN_POSTINGS_TO_PUBLISH = 100  # below this, rates are too noisy to show
MIN_RECENT_MENTIONS = 5        # ignore skills seen in fewer than 5 recent postings
SIGNIFICANCE = 0.05
SCHEMA_VERSION = 1


def load_recent_postings(snapshot_dir=SNAPSHOT_DIR, now=None):
    """Valid, de-duplicated postings from every raw snapshot. Returns (postings, snapshot_names)."""
    files = sorted(glob.glob(os.path.join(snapshot_dir, "*.json")))
    seen_ids, seen_hashes, postings = set(), set(), []
    for path in files:
        with open(path, encoding="utf-8") as f:
            jobs = json.load(f)
        for raw in jobs:
            posting, reason, _ = validate_posting(normalize_adzuna(raw), now=now)
            if reason or posting["posting_id"] in seen_ids:
                continue
            h = content_hash(posting)
            if h in seen_hashes:
                continue
            seen_ids.add(posting["posting_id"])
            seen_hashes.add(h)
            postings.append(posting)
    return postings, [os.path.basename(p) for p in files]


def _skill_counts(postings, term_lookup, pattern):
    counts = {}
    for p in postings:
        found = extract_terms_from_text_fast(f"{p['title']}. {p['description'][:TEXT_WINDOW_CHARS]}", pattern, term_lookup)
        for key in {normalize_term(e["term"]) for e in found}:
            counts[key] = counts.get(key, 0) + 1
    return counts


def historical_baseline(conn, term_lookup, pattern):
    """(number of sample postings, {normalized skill: postings mentioning it}), measured like-for-like.

    Adzuna's API returns only the first ~500 characters of each description, while the historical
    sample has the full text (median about 3,500). Comparing them directly would make every skill look
    like it collapsed. So the historical sample is re-scanned on the same first-500-characters window.
    """
    rows = conn.execute("SELECT title, description FROM postings WHERE source = 'kaggle_sample'").fetchall()
    sample = [{"title": t or "", "description": (d or "")[:TEXT_WINDOW_CHARS]} for t, d in rows]
    return len(sample), _skill_counts(sample, term_lookup, pattern)


def compute_market_pulse(db_path=DB_PATH, snapshot_dir=SNAPSHOT_DIR, now=None):
    """Build the market-pulse dictionary. Returns None when there are too few recent postings."""
    postings, snapshots = load_recent_postings(snapshot_dir, now=now)
    if len(postings) < MIN_POSTINGS_TO_PUBLISH:
        return None

    vocabulary = load_vocabulary()
    term_lookup = {}
    for entry in vocabulary:
        term_lookup.setdefault(normalize_term(entry["term"]), entry)
    pattern = build_combined_pattern([e["term"] for e in term_lookup.values()])
    recent_counts = _skill_counts(postings, term_lookup, pattern)

    conn = sqlite3.connect(db_path)
    try:
        hist_total, hist_counts = historical_baseline(conn, term_lookup, pattern)
    finally:
        conn.close()

    n_recent = len(postings)
    rows = []
    for key, x_recent in recent_counts.items():
        if x_recent < MIN_RECENT_MENTIONS or key in AMBIGUOUS_GENERIC_TERMS:
            continue
        x_hist = hist_counts.get(key, 0)
        _, p_value, method = compare_proportions(x_hist, hist_total, x_recent, n_recent)
        rows.append({
            "skill": term_lookup[key]["term"],
            "recent_count": x_recent,
            "recent_rate": x_recent / n_recent,
            "historical_count": x_hist,
            "historical_rate": x_hist / hist_total if hist_total else 0.0,
            "p_value": p_value,
            "test": method,
        })
    for row, q in zip(rows, apply_fdr_correction([r["p_value"] for r in rows])):
        row["q_value"] = float(q)
        row["difference"] = row["recent_rate"] - row["historical_rate"]
        row["shift_confirmed"] = bool(q < SIGNIFICANCE)
    rows.sort(key=lambda r: r["recent_rate"], reverse=True)

    dates = sorted(p["posted_date"][:10] for p in postings if p["posted_date"])
    refreshed = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return {
        "schema_version": SCHEMA_VERSION,
        "refreshed_at": refreshed,
        "recent_postings": n_recent,
        "snapshots_used": len(snapshots),
        "posted_from": dates[0] if dates else None,
        "posted_to": dates[-1] if dates else None,
        "historical_postings": hist_total,
        "method": "baseline_keyword",
        "text_window_chars": TEXT_WINDOW_CHARS,
        "skills": rows,
    }


def write_market_pulse(pulse, out_path=OUT_PATH):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pulse, f, indent=1)
    os.replace(tmp, out_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--snapshots", default=SNAPSHOT_DIR)
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args(argv)
    pulse = compute_market_pulse(args.db, args.snapshots)
    if pulse is None:
        print(f"Fewer than {MIN_POSTINGS_TO_PUBLISH} recent postings: nothing published (previous file kept).")
        return 1
    write_market_pulse(pulse, args.out)
    confirmed = sum(r["shift_confirmed"] for r in pulse["skills"])
    print(f"Market pulse: {pulse['recent_postings']} recent postings from {pulse['snapshots_used']} snapshots, "
          f"{len(pulse['skills'])} skills compared, {confirmed} confirmed shifts -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
