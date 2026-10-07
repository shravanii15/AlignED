"""
ingest_adzuna.py: fetch, validate, deduplicate and load Adzuna postings.

    python scripts/ingest_adzuna.py                     # live pull (needs ADZUNA_APP_ID / ADZUNA_APP_KEY)
    python scripts/ingest_adzuna.py --from-file data/raw/adzuna/2026-10-07.json   # replay a snapshot

Exit codes: 0 ok, 2 fetch failed, 3 run completed but data quality degraded
(more than 30% of fetched postings rejected). A non-zero exit fails the
scheduled GitHub Action, which is the alert.

Loaded Adzuna postings are stored with source = 'adzuna'. The dashboard's
statistics use only the Kaggle historical sample, so loading new postings
never changes a published number.
"""

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest.adzuna_client import FetchError, fetch_jobs, save_snapshot  # noqa: E402
from ingest.loader import STATUS_DEGRADED, backfill_content_hashes, ensure_ingest_schema, ingest_postings, load_snapshot_file  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw", "adzuna")

EXIT_OK, EXIT_FETCH_FAILED, EXIT_DEGRADED = 0, 2, 3


def print_report(stats):
    print(f"Run {stats['run_id']}: {stats['status'].upper()}")
    print(f"  fetched            {stats['fetched']}")
    print(f"  rejected           {stats['rejected']}  {stats['reject_reasons'] or ''}")
    print(f"  duplicate ids      {stats['duplicate_ids']}")
    print(f"  duplicate content  {stats['duplicate_content']}")
    print(f"  warnings repaired  {stats['warnings']}")
    print(f"  inserted           {stats['inserted']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-file", help="replay a saved raw snapshot instead of calling the API")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--pages", type=int, default=2, help="pages of results per query")
    args = parser.parse_args(argv)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_ingest_schema(conn)
    backfill_content_hashes(conn)

    if args.from_file:
        stats = load_snapshot_file(conn, args.from_file)
    else:
        app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            print("Missing ADZUNA_APP_ID / ADZUNA_APP_KEY.", file=sys.stderr)
            return EXIT_FETCH_FAILED
        try:
            jobs = fetch_jobs(app_id, app_key, pages=args.pages)
        except FetchError as exc:
            print(f"Fetch failed: {exc}", file=sys.stderr)
            return EXIT_FETCH_FAILED
        path = save_snapshot(jobs, RAW_DIR)
        print(f"Saved raw snapshot: {path}")
        stats = ingest_postings(conn, jobs, snapshot_path=path)

    print_report(stats)
    return EXIT_DEGRADED if stats["status"] == STATUS_DEGRADED else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
