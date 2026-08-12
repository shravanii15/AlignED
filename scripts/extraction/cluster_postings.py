"""
cluster_postings.py

What this script does, in plain terms:
So far, when we compare a program's curriculum against "the job market,"
we've only been able to compare it against one company's individual job
posting at a time. That's not quite right -- a program's curriculum
should really be compared against what "Data Scientist" roles need IN
GENERAL, not against one specific listing from one specific company. This
script is what makes that possible: it groups thousands of real job
postings into clusters of postings that are really describing the SAME
underlying role, based on what the posting actually says (not just its
job title, which can be inconsistent or misleading across companies).

How it works, step by step:
1. Pull a large, varied sample of real job postings from our historical
   Kaggle dataset, spread across many different tech role categories
   (software engineering, data science, cybersecurity, DevOps, etc.) so
   the clustering has real variety to work with.
2. Turn each posting's title + description into an embedding -- the same
   kind of "meaning as numbers" technique renormalize.py already uses,
   via the free, local sentence-transformers library.
3. Run k-means clustering over those embeddings. Since we don't know in
   advance how many "real roles" exist in our data, we try a range of
   cluster counts (k) and use each one's silhouette score -- a standard
   metric for "how well-separated and internally consistent are these
   clusters" -- to pick the best k automatically, rather than guessing.
4. Save the results: which posting landed in which cluster, plus a
   labeled sample from each cluster so a human (you!) can sanity-check
   whether the postings grouped together actually look like the same
   role. This sanity check is a required, explicit step in the project
   plan -- an algorithm saying "these are all the same role" is only
   useful if a human spot-check agrees.

Requires: pip install scikit-learn
(sentence-transformers should already be installed from renormalize.py)
"""

import csv
import json
import os
import random

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
POSTINGS_CSV = os.path.join(BASE_DIR, "data", "kaggle_backfill", "postings.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "clustering")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# The same role-category keywords used earlier when sampling the gold-set,
# reused here so our clustering sample covers the same breadth of
# computing/tech roles the rest of the project is built around.
CATEGORIES = [
    "software engineer", "data scientist", "data engineer", "machine learning",
    "cybersecurity", "information security", "devops", "cloud engineer",
    "database administrator", "systems administrator", "web developer",
    "network engineer", "business intelligence",
]
PER_CATEGORY_TARGET = 150  # -> up to ~1,950 postings total, a real sample size for clustering

RANDOM_SEED = 42

# We try cluster counts across this range and let silhouette score pick
# the winner, rather than assuming we know the "right" number of roles in
# advance -- 13 category keywords doesn't mean exactly 13 real clusters,
# since roles legitimately overlap or split further (e.g. "cloud
# engineer" and "DevOps" postings often blend together).
K_RANGE = range(6, 21)


def load_postings_sample():
    """Stream through the (very large, ~3.3M row) Kaggle postings CSV and
    pull a manageable, category-balanced sample, the same way the gold-set
    sampling script did earlier. We stream rather than load the whole
    file into memory, since it's roughly 500MB."""
    random.seed(RANDOM_SEED)
    csv.field_size_limit(10_000_000)

    buckets = {cat: [] for cat in CATEGORIES}
    with open(POSTINGS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("title") or "").lower()
            desc = row.get("description") or ""
            if len(desc) < 150:
                continue
            for cat in CATEGORIES:
                if cat in title and len(buckets[cat]) < PER_CATEGORY_TARGET * 3:
                    buckets[cat].append(row)
                    break

    sample = []
    for cat, rows in buckets.items():
        random.shuffle(rows)
        picked = rows[:PER_CATEGORY_TARGET]
        print(f"  {cat}: {len(rows)} candidates found, using {len(picked)}")
        for r in picked:
            sample.append(
                {
                    "job_id": r.get("job_id"),
                    "title": r.get("title"),
                    "company": r.get("company_name"),
                    "category_keyword": cat,
                    # Embed title + a trimmed slice of the description --
                    # the title carries a lot of signal on its own, and
                    # trimming keeps embedding fast across ~2,000 postings.
                    "embedding_text": f"{r.get('title', '')}. {(r.get('description') or '')[:600]}",
                }
            )
    return sample


def pick_best_k(embeddings):
    """Try each candidate cluster count in K_RANGE, score it with
    silhouette score, and return the k that scored best -- this is how we
    let the data decide how many real role-clusters exist, instead of
    guessing a number ourselves."""
    print("\nTrying different cluster counts (k) to find the best fit...")
    best_k = None
    best_score = -1.0
    best_labels = None

    for k in K_RANGE:
        kmeans = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10)
        labels = kmeans.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels)
        print(f"  k={k}: silhouette score = {score:.4f}")
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels

    print(f"\nBest k = {best_k} (silhouette score {best_score:.4f})")
    return best_k, best_labels, best_score


def main():
    print(f"Streaming a category-balanced sample of postings from: {POSTINGS_CSV}")
    postings = load_postings_sample()
    print(f"\nTotal postings sampled: {len(postings)}")

    print(f"\nLoading embedding model ({EMBEDDING_MODEL_NAME})...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    print("Computing embeddings for all sampled postings (this is the slow step)...")
    texts = [p["embedding_text"] for p in postings]
    embeddings = model.encode(texts, show_progress_bar=True)

    best_k, labels, silhouette = pick_best_k(embeddings)

    for posting, label in zip(postings, labels):
        posting["cluster_id"] = int(label)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Full results: every posting with its assigned cluster.
    results_path = os.path.join(OUTPUT_DIR, "posting_clusters.json")
    # Don't keep the (long) embedding_text in the saved file -- it was
    # only needed to compute the embedding, not useful afterward.
    clean_postings = [
        {k: v for k, v in p.items() if k != "embedding_text"} for p in postings
    ]
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(clean_postings, f, indent=2)
    print(f"\nSaved full clustering results to: {results_path}")

    # Sanity-check file: a readable sample of titles from each cluster,
    # specifically so a human can eyeball "do these actually look like
    # the same role?" -- this is a required step in the project plan, not
    # an optional nice-to-have.
    sanity_path = os.path.join(OUTPUT_DIR, "cluster_sanity_check.txt")
    with open(sanity_path, "w", encoding="utf-8") as f:
        f.write(f"Role cluster sanity check -- best k = {best_k}, silhouette score = {silhouette:.4f}\n")
        f.write("=" * 70 + "\n\n")
        for cluster_id in range(best_k):
            members = [p for p in clean_postings if p["cluster_id"] == cluster_id]
            f.write(f"CLUSTER {cluster_id} -- {len(members)} postings\n")
            f.write("-" * 40 + "\n")
            sample_titles = random.sample(members, min(8, len(members)))
            for m in sample_titles:
                f.write(f"  - {m['title']} ({m['company']})\n")
            f.write("\n")
    print(f"Saved a human-readable sanity check to: {sanity_path}")
    print("\nOpen that file and skim each cluster -- do the postings grouped")
    print("together actually look like the same real-world role? That's the")
    print("sanity check the project plan asks for.")
    print("\nDone.")


if __name__ == "__main__":
    main()
