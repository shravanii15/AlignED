"""
health_report.py: a data-health report built by replaying every saved Adzuna snapshot through the ingestion rules.

    python scripts/health_report.py        # writes data/health/ingestion_report.json

For each daily snapshot it records how many postings were fetched, how many were rejected and why, how many were
repeats (same id, or same content under a new id), and how many were new, plus running totals. It uses the same
validation and fingerprint functions as the live loader, in memory, so it can be regenerated at any time from the
committed raw snapshots (the raw layer). The dashboard's Data Health page reads this file.
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts", "ingest"))

from quality import content_hash, normalize_adzuna, validate_posting  # noqa: E402

SNAPSHOT_DIR = os.path.join(BASE_DIR, "data", "raw", "adzuna")
OUT_PATH = os.path.join(BASE_DIR, "data", "health", "ingestion_report.json")
DEGRADED_REJECT_RATE = 0.30  # same threshold the live job uses to fail a run


def build_report(snapshot_dir=SNAPSHOT_DIR, now=None):
    seen_ids, seen_hashes = set(), set()
    rows, total_unique = [], 0
    for path in sorted(glob.glob(os.path.join(snapshot_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            jobs = json.load(f)
        row = {"snapshot": os.path.splitext(os.path.basename(path))[0], "fetched": len(jobs), "rejected": 0, "reject_reasons": {},
               "duplicate_ids": 0, "duplicate_content": 0, "new": 0}
        for raw in jobs:
            posting, reason, _ = validate_posting(normalize_adzuna(raw), now=now)
            if reason:
                row["rejected"] += 1
                row["reject_reasons"][reason] = row["reject_reasons"].get(reason, 0) + 1
                continue
            if posting["posting_id"] in seen_ids:
                row["duplicate_ids"] += 1
                continue
            h = content_hash(posting)
            if h in seen_hashes:
                row["duplicate_content"] += 1
                continue
            seen_ids.add(posting["posting_id"])
            seen_hashes.add(h)
            row["new"] += 1
        total_unique += row["new"]
        row["unique_total"] = total_unique
        row["reject_rate"] = row["rejected"] / row["fetched"] if row["fetched"] else 0.0
        row["status"] = "degraded" if row["reject_rate"] > DEGRADED_REJECT_RATE else "ok"
        rows.append(row)
    reasons = {}
    for r in rows:
        for k, v in r["reject_reasons"].items():
            reasons[k] = reasons.get(k, 0) + v
    fetched = sum(r["fetched"] for r in rows)
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "snapshots": len(rows), "first_snapshot": rows[0]["snapshot"] if rows else None, "last_snapshot": rows[-1]["snapshot"] if rows else None,
        "fetched": fetched, "rejected": sum(r["rejected"] for r in rows), "duplicate_ids": sum(r["duplicate_ids"] for r in rows),
        "duplicate_content": sum(r["duplicate_content"] for r in rows), "unique_valid": total_unique,
        "degraded_runs": sum(1 for r in rows if r["status"] == "degraded"), "reject_reasons": reasons, "per_snapshot": rows,
    }


def main(argv=None):
    report = build_report()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(f"{report['snapshots']} snapshots ({report['first_snapshot']} to {report['last_snapshot']}): {report['fetched']} fetched, "
          f"{report['rejected']} rejected, {report['duplicate_ids']} repeat ids, {report['duplicate_content']} repeat content, "
          f"{report['unique_valid']} unique valid; {report['degraded_runs']} degraded run(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
