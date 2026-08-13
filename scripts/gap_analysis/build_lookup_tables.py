"""
build_lookup_tables.py

What this script does, in plain terms:
Before we can compute skill gaps, the database needs three things it
doesn't have yet:
1. The `skills` table filled in with our real O*NET vocabulary (right now
   it's empty -- we've only ever used the vocabulary as JSON files).
2. The `postings` table filled in with the 1,660-posting market-demand
   sample from clustering, so it's queryable like any other real data,
   not just a JSON file on disk.
3. The `role_clusters` and `posting_cluster_map` tables filled in with the
   11 clusters from cluster_postings.py and which posting landed in which
   cluster, plus a plain-English role label for each cluster based on the
   hand sanity-check we already did (e.g. cluster 0 = "Cybersecurity").

Why this matters: the whole point of using a real relational database
(instead of just JSON files everywhere) is that later steps -- gap
scoring, and eventually the dashboard -- can ask real questions like
"which skills does Program X's coursework cover?" with a SQL query,
instead of every script re-parsing raw JSON by hand. This script is what
finally makes that possible.

This script is idempotent: it clears out and rebuilds these tables every
time it's run, the same pattern used by setup_database.py for
courses/programs.
"""

import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
TAXONOMY_DIR = os.path.join(BASE_DIR, "data", "taxonomy")
CLUSTERING_DIR = os.path.join(BASE_DIR, "data", "clustering")

SKILLS_PATH = os.path.join(TAXONOMY_DIR, "onet_computing_skills.json")
TECHNOLOGIES_PATH = os.path.join(TAXONOMY_DIR, "onet_computing_technologies.json")
POSTING_CLUSTERS_PATH = os.path.join(CLUSTERING_DIR, "posting_clusters.json")

# Plain-English role labels for each of the 11 clusters, based on the
# hand sanity-check we did on cluster_sanity_check.txt. Clusters 8 and 9
# are honestly labeled as weak/low-quality rather than pretending they're
# clean -- see the progress log for why.
CLUSTER_LABELS = {
    0: "Cybersecurity / Information Security",
    1: "Data Science / Data Engineering",
    2: "Software / Web Development",
    3: "Systems Administration",
    4: "Machine Learning / AI",
    5: "DevOps / Cloud Engineering",
    6: "Business Intelligence",
    7: "Network Engineering",
    8: "Mixed (weak cluster -- multiple roles blended together)",
    9: "Near-duplicate postings (data quality quirk, not a real role group)",
    10: "Database Administration",
}


def normalize_term(term):
    return " ".join(term.strip().lower().split())


def populate_skills(conn):
    """Load the O*NET vocabulary and insert one row per unique skill/
    knowledge/technology term into the `skills` table."""
    cur = conn.cursor()
    cur.execute("DELETE FROM skills")

    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        skills_and_knowledge = json.load(f)
    with open(TECHNOLOGIES_PATH, "r", encoding="utf-8") as f:
        technology_categories = json.load(f)

    seen = set()
    rows = []
    for entry in skills_and_knowledge:
        key = normalize_term(entry["name"])
        if key in seen:
            continue
        seen.add(key)
        rows.append((entry["name"], "ONET", entry["onet_category"]))

    for category in technology_categories:
        for example in category.get("examples", []):
            title = example["title"]
            key = normalize_term(title)
            if key in seen:
                continue
            seen.add(key)
            rows.append((title, "ONET", "technology"))

    cur.executemany(
        "INSERT INTO skills (canonical_name, taxonomy_source, category) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"  -> {len(rows)} skills inserted into the skills table.")


def populate_postings_and_clusters(conn):
    """Load the 1,660-posting clustering sample and:
    - insert each posting into `postings` (source='kaggle_sample')
    - insert the 11 clusters into `role_clusters`
    - link every posting to its cluster in `posting_cluster_map`
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM posting_cluster_map")
    cur.execute("DELETE FROM role_clusters")
    cur.execute("DELETE FROM postings WHERE source = 'kaggle_sample'")

    with open(POSTING_CLUSTERS_PATH, "r", encoding="utf-8") as f:
        postings = json.load(f)

    # Figure out which cluster ids are actually present (should be 0-10),
    # and the silhouette score, which cluster_sanity_check.txt tells us
    # was 0.0816 for this run.
    cluster_ids = sorted({p["cluster_id"] for p in postings})
    cluster_rows = [
        (cid, CLUSTER_LABELS.get(cid, f"Cluster {cid}"), "kmeans_silhouette", 0.0816)
        for cid in cluster_ids
    ]
    cur.executemany(
        "INSERT INTO role_clusters (cluster_id, role_label, method, silhouette_score) VALUES (?, ?, ?, ?)",
        cluster_rows,
    )

    posting_rows = []
    map_rows = []
    for p in postings:
        # Prefix so these can never collide with real Adzuna posting ids.
        posting_id = f"kaggle_{p['job_id']}"
        posting_rows.append(
            (
                posting_id,
                "kaggle_sample",
                p.get("title"),
                p.get("company"),
                None,  # location not carried through clustering step
                None,  # full description not kept in posting_clusters.json
                None,
                None,
                None,
            )
        )
        map_rows.append((posting_id, p["cluster_id"]))

    cur.executemany(
        """INSERT INTO postings
           (posting_id, source, title, company, location, description, salary_min, salary_max, posted_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        posting_rows,
    )
    cur.executemany(
        "INSERT INTO posting_cluster_map (posting_id, cluster_id) VALUES (?, ?)",
        map_rows,
    )
    conn.commit()
    print(f"  -> {len(cluster_rows)} role clusters inserted.")
    print(f"  -> {len(posting_rows)} postings inserted (source='kaggle_sample').")
    print(f"  -> {len(map_rows)} posting-to-cluster links inserted.")


def main():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    print("\nPopulating skills table from O*NET vocabulary...")
    populate_skills(conn)

    print("\nPopulating postings, role_clusters, and posting_cluster_map...")
    populate_postings_and_clusters(conn)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
