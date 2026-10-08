"""
Prefect flows that orchestrate AlignED's data pipeline.

    python scripts/orchestration/flows.py daily                 # fetch, validate, load, check, rebuild
    python scripts/orchestration/flows.py daily --from-file data/raw/adzuna/2026-10-07.json
    python scripts/orchestration/flows.py backfill              # replay every saved raw snapshot, oldest first
    python scripts/orchestration/flows.py weekly                # weekly market pulse from saved snapshots
    python scripts/orchestration/flows.py serve                 # run the daily flow on a schedule (06:00 UTC)

What the orchestration adds on top of the plain scripts:
  - Retries: a failed fetch (network, rate limit) is retried with a delay.
    A data-quality failure is NOT retried, because pulling the same bad data again will not fix it.
  - Ordering and gating: the derived tables are rebuilt only after the load and the
    integrity check succeed.
  - Backfill: replaying raw snapshots is safe to repeat because loading is idempotent.
  - Alerts: any failed run triggers `notify_failure`, which logs and, when ALERT_WEBHOOK_URL
    is set, posts a short message (Slack-compatible).
  - A run report: each run publishes a markdown summary artifact.
"""

import argparse
import glob
import os
import sqlite3
import sys

import requests
from prefect import flow, get_run_logger, task
from prefect.artifacts import create_markdown_artifact

SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)

import ingest_adzuna  # noqa: E402
import market_pulse  # noqa: E402
from rebuild_all import rebuild_derived  # noqa: E402
from validate_database import validate_database  # noqa: E402

DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw", "adzuna")

FETCH_RETRIES = 3
FETCH_RETRY_DELAY_SECONDS = 60


class FetchFailed(RuntimeError):
    """The postings could not be fetched. Worth retrying."""


class DataQualityDegraded(RuntimeError):
    """The data was fetched but too much of it was rejected. Retrying will not help."""


class IntegrityCheckFailed(RuntimeError):
    """The database failed its integrity checks."""


def _retry_only_fetch_failures(task_obj, task_run, state):
    """Retry condition: only a failed fetch is retried, never a data-quality failure."""
    try:
        state.result()
    except FetchFailed:
        return True
    except Exception:
        return False
    return False


def notify_failure(flow_obj, flow_run, state):
    """Failure hook: log the failure and post to a webhook if one is configured."""
    message = f"AlignED pipeline run '{flow_run.name}' ended in state {state.name}."
    get_run_logger().error(message)
    url = os.getenv("ALERT_WEBHOOK_URL")
    if url:
        try:
            requests.post(url, json={"text": message}, timeout=10)
        except requests.RequestException as exc:
            get_run_logger().warning(f"Could not send the alert: {exc}")


@task(retries=FETCH_RETRIES, retry_delay_seconds=FETCH_RETRY_DELAY_SECONDS, retry_condition_fn=_retry_only_fetch_failures)
def ingest_task(db_path, from_file=None, pages=2):
    """Fetch (or replay), validate, de-duplicate and load postings. Returns the exit code."""
    argv = ["--db", db_path, "--pages", str(pages)]
    if from_file:
        argv += ["--from-file", from_file]
    code = ingest_adzuna.main(argv)
    if code == ingest_adzuna.EXIT_FETCH_FAILED:
        raise FetchFailed("Adzuna fetch failed")
    if code == ingest_adzuna.EXIT_DEGRADED:
        raise DataQualityDegraded("More than 30% of fetched postings were rejected")
    return code


@task
def integrity_task(db_path):
    """Run the database integrity checks. Raises if any fail."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        problems = validate_database(conn)
    finally:
        conn.close()
    if problems:
        raise IntegrityCheckFailed("; ".join(problems))
    return len(problems)


@task
def rebuild_task(db_path):
    """Recompute gap_scores and recommendations on a copy, validate, then swap in atomically."""
    problems = rebuild_derived(db_path)
    if problems:
        raise IntegrityCheckFailed("Rebuild validation failed: " + "; ".join(problems))
    return True


@task
def market_pulse_task(db_path, snapshot_dir, out_path):
    """Recompute the weekly market-pulse file from the saved snapshots. Raises if too little data."""
    pulse = market_pulse.compute_market_pulse(db_path, snapshot_dir)
    if pulse is None:
        raise ValueError(f"Fewer than {market_pulse.MIN_POSTINGS_TO_PUBLISH} recent postings: nothing published")
    market_pulse.write_market_pulse(pulse, out_path)
    return pulse


def _counts(db_path):
    conn = sqlite3.connect(db_path)
    try:
        postings = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0]
    finally:
        conn.close()
    return postings, runs


def _publish_report(title, lines):
    create_markdown_artifact(key="aligned-run-report", markdown=f"# {title}\n\n" + "\n".join(f"- {line}" for line in lines))


@flow(name="aligned-daily", on_failure=[notify_failure])
def daily_flow(db_path=DB_PATH, from_file=None, pages=2, rebuild=True):
    """Ingest, check integrity, then (optionally) rebuild the derived tables."""
    log = get_run_logger()
    before, _ = _counts(db_path)
    ingest_task(db_path, from_file=from_file, pages=pages)
    integrity_task(db_path)
    if rebuild:
        rebuild_task(db_path)
    after, runs = _counts(db_path)
    log.info(f"Postings {before} -> {after}; ingestion runs logged: {runs}")
    _publish_report("AlignED daily run", [f"Postings before: {before}", f"Postings after: {after}", f"New rows: {after - before}",
                                           f"Derived tables rebuilt: {'yes' if rebuild else 'skipped'}"])
    return {"before": before, "after": after, "runs": runs}


@flow(name="aligned-backfill", on_failure=[notify_failure])
def backfill_flow(db_path=DB_PATH, snapshot_dir=RAW_DIR):
    """Replay every raw snapshot, oldest first. Safe to repeat: loading is idempotent."""
    files = sorted(glob.glob(os.path.join(snapshot_dir, "*.json")))
    if not files:
        raise FileNotFoundError(f"No snapshots found in {snapshot_dir}")
    before, _ = _counts(db_path)
    for path in files:
        ingest_task(db_path, from_file=path)
    integrity_task(db_path)
    after, _ = _counts(db_path)
    _publish_report("AlignED backfill", [f"Snapshots replayed: {len(files)}", f"Postings before: {before}", f"Postings after: {after}"])
    return {"snapshots": len(files), "before": before, "after": after}


@flow(name="aligned-weekly-refresh", on_failure=[notify_failure])
def weekly_refresh_flow(db_path=DB_PATH, snapshot_dir=RAW_DIR, out_path=market_pulse.OUT_PATH):
    """Weekly: compare recent postings with the fixed sample and publish the market-pulse file.

    Gap scores, recommendations and trends are NOT touched: they stay tied to the fixed sample."""
    pulse = market_pulse_task(db_path, snapshot_dir, out_path)
    confirmed = sum(r["shift_confirmed"] for r in pulse["skills"])
    _publish_report("AlignED weekly refresh", [f"Recent postings: {pulse['recent_postings']}", f"Snapshots used: {pulse['snapshots_used']}",
                                               f"Skills compared: {len(pulse['skills'])}", f"Confirmed differences: {confirmed}"])
    return {"recent_postings": pulse["recent_postings"], "skills": len(pulse["skills"]), "confirmed": confirmed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["daily", "backfill", "weekly", "serve"])
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--from-file")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--no-rebuild", action="store_true")
    parser.add_argument("--cron", default="0 6 * * *", help="schedule for `serve` (default 06:00 UTC daily)")
    args = parser.parse_args(argv)

    if args.command == "daily":
        daily_flow(db_path=args.db, from_file=args.from_file, pages=args.pages, rebuild=not args.no_rebuild)
    elif args.command == "backfill":
        backfill_flow(db_path=args.db)
    elif args.command == "weekly":
        weekly_refresh_flow(db_path=args.db)
    else:
        daily_flow.serve(name="aligned-daily-schedule", cron=args.cron, parameters={"db_path": args.db, "pages": args.pages})


if __name__ == "__main__":
    main()
