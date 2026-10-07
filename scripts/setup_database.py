"""
setup_database.py

What this script does, in plain terms:
1. Creates the actual database file (aligned.db) using the blueprint
   in schema.sql - this is a one-time "build the empty filing cabinet"
   step.
2. Loads in the real data we've already collected (the Georgia Tech
   courses and the sample Adzuna job postings) so we can immediately
   see the database working with real information, not empty tables.
"""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db_utils import atomic_replace, foreign_key_violations  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../AlignED
DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Build into a temporary file and only swap it into place once it is
# complete and passes PRAGMA foreign_key_check. A failed rebuild therefore
# never destroys the working database, and there is nothing to DELETE
# (the old approach deleted courses and programs in place, which fails with
# a FOREIGN KEY error once gap_scores/recommendations reference them).
BUILD_PATH = DB_PATH + ".new"
if os.path.exists(BUILD_PATH):
    os.remove(BUILD_PATH)
print(f"Building database at: {BUILD_PATH} (will replace {DB_PATH} when complete)")
conn = sqlite3.connect(BUILD_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

# Step 1: build the empty tables from the schema file.
with open(SCHEMA_PATH) as f:
    cur.executescript(f.read())
print("Tables created.\n")

# Step 2: load each scraped program + its real courses.
# The database is built fresh, so there is nothing to clear first. Running
# this script again rebuilds from the source files every time.

# Every program we've successfully scraped so far. As we scrape more
# of the 15, we just add a line here - nothing else needs to change.
SCRAPED_PROGRAMS = [
    {
        "university": "Georgia Tech",
        "program_name": "MS Analytics (OMS Analytics)",
        "tier": "top-ranked, online",
        "url": "https://pe.gatech.edu/degrees/analytics/curriculum",
        "file": "sample_gatech_analytics_courses.json",
    },
    {
        "university": "Georgia Tech",
        "program_name": "MS Cybersecurity (OMS Cybersecurity)",
        "tier": "top-ranked, online",
        "url": "https://pe.gatech.edu/degrees/cybersecurity/curriculum",
        "file": "sample_gatech_cybersecurity_courses.json",
    },
    {
        "university": "Georgia Tech",
        "program_name": "MS Computer Science (main CS catalog)",
        "tier": "top-ranked",
        "url": "https://catalog.gatech.edu/coursesaz/cs/",
        "file": "sample_gatech_maincatalog_cs_courses.json",
    },
    {
        "university": "Arizona State University",
        "program_name": "Online Master of Computer Science (MCS)",
        "tier": "online",
        "url": "https://asuonline.asu.edu/online-degree-programs/graduate/computer-science-mcs/",
        "file": "sample_asu_mcs_courses.json",
    },
    {
        "university": "University of Illinois Urbana-Champaign",
        "program_name": "MS Computer Science / MCS-DS (CS course catalog)",
        "tier": "top-ranked",
        "url": "https://catalog.illinois.edu/courses-of-instruction/cs/",
        "file": "sample_uiuc_cs_courses.json",
    },
    {
        "university": "Northeastern University",
        "program_name": "MS Computer Science (Align / CS catalog)",
        "tier": "mid-tier",
        "url": "https://catalog.northeastern.edu/course-descriptions/cs/",
        "file": "sample_northeastern_cs_courses.json",
    },
    {
        "university": "Boston University",
        "program_name": "MS Computer Science (graduate CS courses)",
        "tier": "top-ranked",
        "url": "https://www.bu.edu/academics/grs/courses/computer-science/",
        "file": "sample_bu_cs_courses.json",
    },
    {
        "university": "University of Wisconsin-Madison",
        "program_name": "MS Computer Sciences / MS Data Science (elective pool)",
        "tier": "top-ranked",
        "url": "https://guide.wisc.edu/courses/comp_sci/",
        "file": "sample_wisconsin_cs_courses.json",
    },
    {
        "university": "University of Maryland",
        "program_name": "MS Computer Science (CMSC catalog)",
        "tier": "top-ranked",
        "url": "https://academiccatalog.umd.edu/graduate/courses/cmsc/",
        "file": "sample_umd_cmsc_courses.json",
    },
    {
        "university": "University of Maryland",
        "program_name": "Cybersecurity (ENPM catalog)",
        "tier": "top-ranked",
        "url": "https://academiccatalog.umd.edu/graduate/courses/enpm/",
        "file": "sample_umd_enpm_courses.json",
    },
    {
        "university": "Penn State World Campus",
        "program_name": "MS Data Analytics (DAAN)",
        "tier": "online",
        "url": "https://bulletins.psu.edu/university-course-descriptions/graduate/daan/",
        "file": "sample_psu_daan_courses.json",
    },
    {
        "university": "University of Washington",
        "program_name": "MSCS / MS Data Science (CSE catalog)",
        "tier": "top-ranked",
        "url": "https://www.washington.edu/students/crscat/cse.html",
        "file": "sample_uw_cse_courses.json",
    },
    {
        "university": "University of Michigan",
        "program_name": "MS Computer Science and Engineering (EECS catalog)",
        "tier": "top-ranked",
        "url": "https://bulletin.engin.umich.edu/courses/eecs/",
        "file": "sample_umich_eecs_courses.json",
    },
]

total_courses = 0
for prog in SCRAPED_PROGRAMS:
    cur.execute(
        "INSERT INTO programs (university, program_name, tier, url) VALUES (?, ?, ?, ?)",
        (prog["university"], prog["program_name"], prog["tier"], prog["url"])
    )
    program_id = cur.lastrowid

    with open(os.path.join(DATA_DIR, prog["file"])) as f:
        courses = json.load(f)

    for c in courses:
        cur.execute(
            "INSERT INTO courses (program_id, course_code, course_name, description) VALUES (?, ?, ?, ?)",
            (program_id, c["course_code"], c["course_name"], c["description"])
        )
    total_courses += len(courses)
    print(f"Loaded {prog['university']} - {prog['program_name']}: {len(courses)} courses")

print(f"\nLoaded {len(SCRAPED_PROGRAMS)} programs and {total_courses} real courses total.")

# Step 3: load Adzuna postings through the same validated, de-duplicating
# loader the daily ingestion job uses (scripts/ingest/). The legacy sample
# file is replayed first, then every raw snapshot in data/raw/adzuna/.
# Running this twice therefore loads each posting exactly once.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import glob  # noqa: E402

from ingest.loader import backfill_content_hashes, ensure_ingest_schema, load_snapshot_file  # noqa: E402

ensure_ingest_schema(conn)
snapshot_files = [os.path.join(DATA_DIR, "sample_adzuna_pull.json")] + sorted(glob.glob(os.path.join(DATA_DIR, "raw", "adzuna", "*.json")))
for snapshot in snapshot_files:
    if os.path.exists(snapshot):
        result = load_snapshot_file(conn, snapshot)
        print(f"Replayed {os.path.relpath(snapshot, BASE_DIR)}: inserted {result['inserted']}, rejected {result['rejected']}, duplicates {result['duplicate_ids'] + result['duplicate_content']}")
backfill_content_hashes(conn)

conn.commit()

# Step 4: prove it worked by asking the database a couple of real questions.
print("\n--- Checking the database actually works ---")
cur.execute("SELECT COUNT(*) FROM courses")
print("Total courses stored:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM postings")
print("Total postings stored:", cur.fetchone()[0])

cur.execute("SELECT course_code, course_name FROM courses LIMIT 3")
print("\nSample courses pulled back out of the database:")
for row in cur.fetchall():
    print(" -", row[0], "-", row[1])

violations = foreign_key_violations(conn)
conn.close()
if violations:
    os.remove(BUILD_PATH)
    raise SystemExit(f"Rebuild aborted, foreign key violations in the new database: {violations[:3]}")
atomic_replace(BUILD_PATH, DB_PATH)
print("\nDatabase built and verified successfully.")
print("NOTE: this is a fresh database. Re-run the later stages (build_lookup_tables, extraction, gap scoring, recommendations) to repopulate it.")
