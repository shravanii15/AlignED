"""
rebuild_all.py: one entry point for rebuilding AlignED's analysis layers.

Two modes, because not every input can live in a git repository:

  python scripts/rebuild_all.py            (default: --derived-only)
      Recomputes the DERIVED tables, gap_scores and recommendations, from
      the raw tables already in database/aligned.db (courses, postings,
      skills, extractions, role clusters, skill trends). Needs nothing
      outside the repository. Works on a temporary copy, runs the
      integrity checks in validate_database.py, and only replaces the real
      database if every check passes.

  python scripts/rebuild_all.py --full
      Rebuilds the database from raw sources, stage by stage. Needs inputs
      that are NOT in the repository (see README, "Reproducing the
      database"): the Kaggle LinkedIn postings CSV, a local Ollama model for
      the benchmark stages, and API keys. Each stage's required files are
      checked first so a missing input fails with a clear message instead of
      halfway through.

Environment: ALIGNED_DB_PATH overrides the database location (used by tests).
"""

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")

sys.path.insert(0, SCRIPTS_DIR)
from db_utils import atomic_replace  # noqa: E402
from validate_database import validate_database  # noqa: E402

DERIVED_STAGES = [
    ("Gap scoring", os.path.join("gap_analysis", "compute_gap_scores.py")),
    ("Recommendations", os.path.join("gap_analysis", "generate_recommendations.py")),
]

# (stage name, script, files that must exist before it can run)
FULL_STAGES = [
    ("Load programs and courses (fresh database)", "setup_database.py", ["data/sample_gatech_analytics_courses.json", "data/sample_adzuna_pull.json"]),
    ("Load skills, postings, role clusters", os.path.join("gap_analysis", "build_lookup_tables.py"),
     ["data/taxonomy/onet_computing_skills.json", "data/taxonomy/onet_computing_technologies.json", "data/clustering/posting_clusters.json"]),
    ("Extract course skills (keyword baseline)", os.path.join("gap_analysis", "extract_course_skills.py"), []),
    ("Extract posting skills (keyword baseline)", os.path.join("gap_analysis", "extract_posting_skills.py"), ["data/kaggle_backfill/postings.csv"]),
    ("Extract posting trends", os.path.join("gap_analysis", "extract_posting_trends.py"), ["data/kaggle_backfill/postings.csv"]),
    ("Skill trends", os.path.join("gap_analysis", "compute_skill_trends.py"), []),
    ("Gap scoring", os.path.join("gap_analysis", "compute_gap_scores.py"), []),
    ("Recommendations", os.path.join("gap_analysis", "generate_recommendations.py"), []),
]


def run_script(relative_path, env):
    print(f"\n=== {relative_path} ===")
    subprocess.run([sys.executable, os.path.join(SCRIPTS_DIR, relative_path)], check=True, env=env, cwd=BASE_DIR)


def check_inputs(stage_name, required):
    missing = [p for p in required if not os.path.exists(os.path.join(BASE_DIR, p))]
    if missing:
        raise SystemExit(f"Cannot run '{stage_name}', missing required input(s): {missing}. See README, 'Reproducing the database'.")


def rebuild_derived(db_path=DB_PATH):
    """Recompute gap_scores and recommendations on a temporary copy of the
    database, validate it, then atomically replace db_path. Returns the
    list of validation problems (empty on success, in which case the
    replacement happened)."""
    tmp_dir = tempfile.mkdtemp(prefix="aligned_rebuild_")
    work_path = os.path.join(tmp_dir, "aligned.db")
    try:
        shutil.copyfile(db_path, work_path)
        env = {**os.environ, "ALIGNED_DB_PATH": work_path}
        for stage_name, script in DERIVED_STAGES:
            print(f"\n--- {stage_name} ---")
            run_script(script, env)
        conn = sqlite3.connect(work_path)
        conn.execute("PRAGMA foreign_keys = ON")
        problems = validate_database(conn)
        conn.close()
        if problems:
            return problems
        staged = db_path + ".rebuilt"
        shutil.copyfile(work_path, staged)  # same filesystem as db_path, so the replace below is atomic
        atomic_replace(staged, db_path)
        return []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def rebuild_full():
    for stage_name, script, required in FULL_STAGES:
        check_inputs(stage_name, required)
    env = {**os.environ, "ALIGNED_DB_PATH": DB_PATH}
    for stage_name, script, _ in FULL_STAGES:
        print(f"\n--- {stage_name} ---")
        run_script(script, env)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    problems = validate_database(conn)
    conn.close()
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--derived-only", action="store_true", help="recompute gap_scores and recommendations from the existing database (default)")
    mode.add_argument("--full", action="store_true", help="rebuild everything from raw sources (needs external inputs)")
    args = parser.parse_args()

    problems = rebuild_full() if args.full else rebuild_derived()
    if problems:
        print("\nValidation FAILED, the existing database was left unchanged:" if not args.full else "\nValidation FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\nRebuild complete, all integrity checks passed.")


if __name__ == "__main__":
    main()
