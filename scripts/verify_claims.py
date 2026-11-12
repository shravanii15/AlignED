"""
verify_claims.py: regenerate every headline number from the database and the saved result files, and compare
it with the value quoted in the README and docs. Exit code 1 if any quoted number no longer matches.

    python scripts/verify_claims.py

Each row says where the number came from, so every published metric is traceable to a stored artifact.
(The number of passing tests is not checked here: it comes from `pytest`, see the CI badge.)
"""

import json
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")


def _json(*parts):
    with open(os.path.join(BASE_DIR, *parts), encoding="utf-8") as f:
        return json.load(f)


def collect(db_path=DB_PATH):
    """List of (claim, quoted value, computed value, source)."""
    conn = sqlite3.connect(db_path)
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    held = _json("data", "heldout", "heldout_results.json")
    robust = _json("data", "robustness", "cluster_robust_gaps.json")["summary"]
    rows = [
        ("Programs", 13, q("SELECT COUNT(*) FROM programs"), "database: programs"),
        ("Course descriptions", 1378, q("SELECT COUNT(*) FROM courses"), "database: courses"),
        ("Job postings used in statistics", 1660, q("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'"), "database: postings (kaggle_sample)"),
        ("O*NET skills", 1597, q("SELECT COUNT(*) FROM skills"), "database: skills"),
        ("Significant gaps, overall-market scope", 170, q("SELECT COUNT(*) FROM gap_scores WHERE cluster_id IS NULL"), "database: gap_scores"),
        ("Recommendations, all scopes", 724, q("SELECT COUNT(*) FROM recommendations"), "database: recommendations"),
        ("Recommendations, overall-market scope", 69, q("SELECT COUNT(*) FROM recommendations WHERE cluster_id IS NULL"), "database: recommendations"),
        ("Gaps tested with Fisher's exact test", 19, q("SELECT COUNT(*) FROM gap_scores WHERE cluster_id IS NULL AND test_method = 'fisher_exact'"), "database: gap_scores.test_method"),
        ("Skills with raw p < 0.05 trend", 9, q("SELECT COUNT(*) FROM skill_trends WHERE p_value < 0.05"), "database: skill_trends"),
        ("Skills with a confirmed trend (q < 0.05)", 0, q("SELECT COUNT(*) FROM skill_trends WHERE q_value < 0.05"), "database: skill_trends"),
        ("Skills tested for trends", 67, q("SELECT COUNT(*) FROM skill_trends"), "database: skill_trends"),
        ("Held-out items", 50, held["num_items"], "data/heldout/heldout_results.json"),
        ("Held-out keyword F1", 0.311, round(held["baseline"]["f1"], 3), "data/heldout/heldout_results.json"),
        ("Held-out LLM F1", 0.198, round(held["llm"]["f1"], 3), "data/heldout/heldout_results.json"),
        ("Gaps still significant after employer-cluster adjustment", 166, robust["still_significant"], "data/robustness/cluster_robust_gaps.json"),
    ]
    conn.close()
    return rows


def main(argv=None):
    rows = collect()
    bad = 0
    print(f"{'Claim':58} {'Quoted':>8} {'Computed':>9}  Source")
    for claim, quoted, computed, source in rows:
        ok = quoted == computed
        bad += not ok
        print(f"{claim:58} {quoted:>8} {computed:>9}  {source}  {'OK' if ok else '<-- MISMATCH'}")
    print(f"\n{len(rows) - bad} of {len(rows)} quoted numbers match.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
