"""
heldout.py: shared helpers for the held-out evaluation.

The 104-item development set was used while the extraction methods were being built and tuned (for
example the 0.65 similarity threshold), so scores on it are optimistic. The held-out set is a fresh
sample that is labeled by hand BEFORE the methods are run on it, and it is scored exactly once with
the settings frozen. See data/heldout/PROTOCOL.md.
"""

import hashlib
import re
import json
import os
import random
import sqlite3

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELDOUT_DIR = os.path.join(BASE, "data", "heldout")
DEV_ITEMS_PATH = os.path.join(BASE, "data", "gold_set", "gold_set_combined.json")
DB_PATH = os.path.join(BASE, "database", "aligned.db")

MAX_TEXT_CHARS = 3000          # same cap the development set used for postings
MIN_COURSE_CHARS = 80          # skip one-line course blurbs, there is nothing to label
MAX_POSTING_CHARS_BEFORE_CAP = 6000


def text_fingerprint(text):
    """Stable fingerprint of the first 200 normalised characters, used to keep dev items out of the held-out set."""
    return hashlib.sha256(" ".join((text or "").lower().split())[:200].encode("utf-8")).hexdigest()


def _shingles(text, k=8):
    words = re.findall(r"\w+", " ".join((text or "").lower().split()))
    return {" ".join(words[i:i + k]) for i in range(max(1, len(words) - k + 1))}


def shingle_overlap(a, b, k=8):
    """Share of the smaller text's 8-word shingles that also occur in the other text (0 to 1).
    Catches near-duplicates that the 200-character fingerprint misses (different openings, same body)."""
    sa, sb = _shingles(a, k), _shingles(b, k)
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def dev_overlaps(items, dev_path=DEV_ITEMS_PATH, threshold=0.3):
    """(held-out id, dev id, overlap) for every pair at or above the threshold. Empty means no leakage found."""
    with open(dev_path, encoding="utf-8") as f:
        dev = json.load(f)
    return [(h["id"], d.get("id"), round(o, 3)) for h in items for d in dev
            if (o := shingle_overlap(h["text"], d["text"])) >= threshold]


def dev_fingerprints(path=DEV_ITEMS_PATH):
    with open(path, encoding="utf-8") as f:
        return {text_fingerprint(item["text"]) for item in json.load(f)}


def _spread(rows, key, n, rng):
    """Pick n rows spread as evenly as possible across the groups given by key(row)."""
    groups = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    for members in groups.values():
        rng.shuffle(members)
    names = sorted(groups, key=str)
    picked = []
    while len(picked) < n and any(groups.values()):
        for name in names:
            if groups[name] and len(picked) < n:
                picked.append(groups[name].pop())
    return picked


def sample_items(db_path=DB_PATH, n_courses=30, n_postings=20, seed=2026, exclude=None):
    """Draw the held-out items. Deterministic for a given seed and database. Courses are spread across
    programs and postings across role clusters, and anything already in the dev set is excluded."""
    exclude = exclude if exclude is not None else dev_fingerprints()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        courses = [dict(r) for r in conn.execute(
            """SELECT c.course_id, c.course_code, c.course_name, c.description, p.university, p.program_name
               FROM courses c JOIN programs p ON p.program_id = c.program_id
               WHERE LENGTH(c.description) >= ? ORDER BY c.course_id""", (MIN_COURSE_CHARS,))]
        postings = [dict(r) for r in conn.execute(
            """SELECT p.posting_id, p.title, p.company, p.description, COALESCE(r.role_label, 'unclustered') AS role
               FROM postings p
               LEFT JOIN posting_cluster_map m ON m.posting_id = p.posting_id
               LEFT JOIN role_clusters r ON r.cluster_id = m.cluster_id
               WHERE p.source = 'kaggle_sample' AND LENGTH(p.description) BETWEEN 400 AND ?
               ORDER BY p.posting_id""", (MAX_POSTING_CHARS_BEFORE_CAP,))]
    finally:
        conn.close()
    courses = [c for c in courses if text_fingerprint(c["description"]) not in exclude]
    postings = [p for p in postings if text_fingerprint(p["description"]) not in exclude]
    rng = random.Random(seed)
    chosen_c = _spread(courses, lambda r: r["program_name"], n_courses, rng)
    chosen_p = _spread(postings, lambda r: r["role"], n_postings, rng)

    items = []
    for i, c in enumerate(sorted(chosen_c, key=lambda r: r["course_id"]), start=1):
        items.append({"id": f"HC{i:03d}", "source_type": "course", "context": f"{c['university']}: {c['program_name']}",
                      "title": f"{c['course_code'] or ''} {c['course_name']}".strip(), "text": c["description"][:MAX_TEXT_CHARS]})
    for i, p in enumerate(sorted(chosen_p, key=lambda r: r["posting_id"]), start=1):
        items.append({"id": f"HP{i:03d}", "source_type": "posting", "context": f"{p['role']} | {p['company'] or ''}",
                      "title": p["title"] or "", "text": p["description"][:MAX_TEXT_CHARS]})
    return items


def parse_skill_cell(cell):
    """Split what a labeler typed into separate skills. Accepts semicolons or new lines. 'NONE' means no skills."""
    if cell is None:
        return None
    text = str(cell).replace("\r", "\n").replace(";", "\n")
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    if len(parts) == 1 and parts[0].lower() == "none":
        return []
    return parts


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()
