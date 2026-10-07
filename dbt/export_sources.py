"""
Export the SQLite tables dbt reads into CSV files (dbt/data/).

    python dbt/export_sources.py [path/to/aligned.db]

Why an export step: dbt reads the analytics layer with DuckDB, and DuckDB's SQLite reader is an
optional extension that has to be downloaded at run time. Exporting plain CSV keeps the dbt run
offline and reproducible (CI, Docker, a laptop without internet). Only the columns dbt needs are
exported, and no posting text leaves the database.
"""

import csv
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE, "database", "aligned.db")
OUT_DIR = os.path.join(BASE, "dbt", "data")

TABLES = {
    "programs": "SELECT program_id, university, program_name, tier FROM programs",
    "courses": "SELECT course_id, program_id FROM courses",
    "skills": "SELECT skill_id, canonical_name, taxonomy_source, category FROM skills",
    "role_clusters": "SELECT cluster_id, role_label FROM role_clusters",
    "gap_scores": ("SELECT gap_id, program_id, skill_id, cluster_id, program_coverage_rate, market_demand_rate, gap_value, "
                   "p_value, q_value, test_method FROM gap_scores"),
    "recommendations": ("SELECT recommendation_id, program_id, skill_id, cluster_id, gap_value, trend_label, priority_score, "
                        "priority_tier FROM recommendations"),
}


def export(db_path=DEFAULT_DB, out_dir=OUT_DIR):
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    counts = {}
    try:
        for name, sql in TABLES.items():
            cur = conn.execute(sql)
            with open(os.path.join(out_dir, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([d[0] for d in cur.description])
                n = 0
                for row in cur:
                    writer.writerow(["" if v is None else v for v in row])
                    n += 1
            counts[name] = n
    finally:
        conn.close()
    return counts


if __name__ == "__main__":
    for table, n in export(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB).items():
        print(f"{table}: {n} rows")
