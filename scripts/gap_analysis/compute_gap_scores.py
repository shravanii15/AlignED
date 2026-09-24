"""
compute_gap_scores.py

What this script does, in plain terms:
This is the actual "gap analysis" -- the payoff of everything built so
far. For every university program, and for every real O*NET skill, it
answers one question: "Is this skill significantly more in-demand than
it's covered in this program's coursework?" -- and it now answers that
question twice, at two different scopes:

1. Overall market (cluster_id = NULL): program coverage vs. demand
   across ALL 1,660 sampled postings, regardless of role. This is the
   original, general-purpose comparison and is what "Program Explorer"
   shows by default.
2. Per role cluster (cluster_id = a real role_clusters.cluster_id):
   program coverage vs. demand within ONE specific role's postings only
   (e.g. just the "Data Science / Data Engineering" cluster). This is
   what actually answers "what does this program prepare me for, for
   THIS target role" -- a program's overall-market gap in AWS might be
   small, but its gap specifically against Cloud/DevOps postings could
   be much larger. Without this, the whole "role clusters" feature built
   earlier was cosmetic -- clusters existed in the database but nothing
   in the gap analysis actually used them (every gap_scores row had
   cluster_id = NULL). This is the fix for that.

How it works, step by step, for EACH scope (overall or one cluster):
1. For each program, compute its "coverage rate" for a skill: what
   fraction of that program's courses mention the skill at least once
   (from the extractions table, source_type='course'). This does not
   change between scopes -- a program's curriculum doesn't change
   depending on which job role you're comparing it to.
2. Compute the "market demand rate" for the same skill, WITHIN THIS
   SCOPE: what fraction of postings in this scope (all 1,660, or just
   the postings mapped to this one role cluster) mention it.
3. The raw gap is market_demand_rate - program_coverage_rate. A
   positive number means the market (at this scope) wants it more than
   the curriculum covers it -- a real candidate gap.
4. Run a two-proportion z-test per (program, skill) pair within this
   scope, exactly as before.
5. Apply a Benjamini-Hochberg FDR correction across every skill tested
   in THIS (program, scope) family together -- a cluster's postings are
   a smaller sample than the overall market, so each scope gets its own
   independent correction rather than being lumped in with any other
   scope's tests.
6. Save every significant, positive gap to gap_scores, tagged with the
   scope's cluster_id (NULL for overall-market rows, a real id for
   per-cluster rows).

A note on cluster quality: two of the eleven role clusters are excluded
from per-cluster analysis entirely -- "Mixed (weak cluster)" and
"Near-duplicate postings (data quality quirk)". Computing a "gap" against
a cluster that isn't actually a coherent role would produce a number
that looks precise but means nothing; see the Methodology page for the
full honest discussion of clustering quality (silhouette score 0.08).

Why this matters for the project:
Anyone can eyeball two lists and guess "this program seems light on
cloud skills." This script instead makes that claim with a real,
falsifiable statistical basis -- the same two-proportion z-test used in
A/B testing and clinical trials -- and, as of this version, can make
that claim specific to an actual target role, not just a generic
"the market" blur.
"""

import os
import sqlite3

from scipy.stats import false_discovery_control, norm

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")

SIGNIFICANCE_THRESHOLD = 0.05
TOP_N_PER_PROGRAM = 15
# Ignore skills a scope's postings barely mention -- a skill mentioned in
# only 1-2 postings isn't a meaningful "demand" signal, and including it
# just adds noise to the z-test at these tiny counts. Applied per-scope,
# so a smaller role cluster naturally tests a smaller (but still
# meaningful) set of skills than the overall market does.
MIN_MARKET_MENTIONS = 10

# Real, honest limitation of keyword matching: a handful of O*NET's
# official "skill"/"knowledge" category names are single, very common
# English words (e.g. "Design", "Science", "Writing"). A plain keyword
# scanner can't tell "data science" or "computer science" apart from a
# sentence like "we're a science-based company" or "design your career
# with us" -- it just sees the word "science" or "design" and counts it,
# which massively inflates their apparent market demand with false
# positives. This is exactly the kind of context-blindness the Week 2
# LLM-vs-baseline comparison already proved the AI method is better at.
# Rather than let a handful of noisy generic words dominate every
# program's "top gaps" list, we exclude them here from the full-scale
# scan and document why -- the named technologies (Python, Docker,
# Kubernetes, etc.) don't have this ambiguity problem and are the more
# trustworthy signal at this stage of the project.
AMBIGUOUS_GENERIC_TERMS = {
    "design", "science", "writing", "monitoring", "programming",
    "troubleshooting", "mathematics", "coordination", "instructing",
    "repairing",
}

# Role clusters excluded from per-cluster gap analysis: not real,
# coherent occupational groupings (see Methodology page), so a "gap"
# computed against them would be a precise-looking but meaningless
# number.
EXCLUDED_CLUSTER_LABEL_PREFIXES = ("Mixed", "Near-duplicate")


def two_proportion_z_test(x1, n1, x2, n2):
    """Standard two-proportion z-test. x1/n1 and x2/n2 are the two
    "successes out of trials" counts being compared (here: courses
    mentioning a skill out of all courses in a program, vs. postings
    mentioning a skill out of all postings in the scope being tested).
    Returns (z, p_value). If either group has zero trials, or the pooled
    variance is zero (e.g. the rate is 0% or 100% in both groups),
    there's nothing meaningful to test, so we return a p-value of 1.0
    (not significant)."""
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    variance = p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)
    if variance <= 0:
        return 0.0, 1.0
    se = variance ** 0.5
    z = (p2 - p1) / se
    p_value = 2 * (1 - norm.cdf(abs(z)))
    return z, p_value


def apply_fdr_correction(p_values):
    """Apply a Benjamini-Hochberg false discovery rate correction to a
    list of raw p-values from *multiple* tests run together (here: every
    skill tested for one program within one scope), returning the
    corrected "q-values" in the same order. Each q-value is always >=
    the raw p-value it came from -- correction can only make a result
    look less significant, never more, which is exactly the conservative
    direction you want when guarding against false positives from
    running many tests at once. An empty input returns an empty list
    (nothing to correct)."""
    if not p_values:
        return []
    return list(false_discovery_control(p_values, method="bh"))


def compute_significant_gaps(program_id, n_courses, skill_ids, coverage_counts, demand_counts, total_n, skill_info):
    """Run the full two-pass (raw p-value, then FDR-corrected) gap
    computation for ONE program within ONE scope (skill_ids/demand_counts/
    total_n together define the scope: either the overall market, or one
    role cluster's postings). Returns the list of significant, positive
    gaps, each as a dict. This is the shared core reused for every scope
    so the overall-market and per-cluster passes can never silently drift
    apart in logic."""
    candidates = []
    for skill_id in skill_ids:
        x_courses = coverage_counts.get((program_id, skill_id), 0)
        x_postings = demand_counts.get(skill_id, 0)
        coverage_rate = x_courses / n_courses
        demand_rate = x_postings / total_n
        gap_value = demand_rate - coverage_rate
        _, p_value = two_proportion_z_test(x_courses, n_courses, x_postings, total_n)
        candidates.append(
            {
                "skill_id": skill_id,
                "coverage_rate": coverage_rate,
                "demand_rate": demand_rate,
                "gap_value": gap_value,
                "p_value": p_value,
            }
        )

    # FDR correction has to see the full family of tests run for this
    # program within THIS scope at once -- correcting one skill's
    # p-value in isolation would defeat the whole point.
    q_values = apply_fdr_correction([c["p_value"] for c in candidates])
    for c, q_value in zip(candidates, q_values):
        c["q_value"] = q_value

    gaps = []
    for c in candidates:
        if c["gap_value"] > 0 and c["q_value"] < SIGNIFICANCE_THRESHOLD:
            skill_id = c["skill_id"]
            gaps.append(
                {
                    "skill_id": skill_id,
                    "skill_name": skill_info[skill_id][0],
                    "category": skill_info[skill_id][1],
                    "coverage_rate": c["coverage_rate"],
                    "demand_rate": c["demand_rate"],
                    "gap_value": c["gap_value"],
                    "p_value": c["p_value"],
                    "q_value": c["q_value"],
                }
            )
    gaps.sort(key=lambda g: g["gap_value"], reverse=True)
    return gaps


def relevant_skills_for_scope(demand_counts, skill_info):
    """Given a scope's skill_id -> mention_count map, return the skill
    ids with enough signal to test, excluding the generic/ambiguous
    terms documented above."""
    return [
        sid for sid, count in demand_counts.items()
        if count >= MIN_MARKET_MENTIONS and skill_info[sid][0].strip().lower() not in AMBIGUOUS_GENERIC_TERMS
    ]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    print("Loading programs...")
    cur.execute("SELECT program_id, university, program_name FROM programs")
    programs = cur.fetchall()

    print("Loading course counts per program...")
    cur.execute("SELECT program_id, COUNT(*) FROM courses GROUP BY program_id")
    course_count_by_program = dict(cur.fetchall())

    print("Loading per-program, per-skill course coverage counts...")
    cur.execute(
        """
        SELECT c.program_id, e.skill_id, COUNT(DISTINCT e.source_id)
        FROM extractions e
        JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword'
        GROUP BY c.program_id, e.skill_id
        """
    )
    coverage_counts = {}  # (program_id, skill_id) -> count of courses mentioning it
    for program_id, skill_id, count in cur.fetchall():
        coverage_counts[(program_id, skill_id)] = count

    print("Loading overall market posting counts and per-skill demand counts...")
    cur.execute("SELECT COUNT(*) FROM postings WHERE source = 'kaggle_sample'")
    total_postings = cur.fetchone()[0]

    cur.execute(
        """
        SELECT skill_id, COUNT(DISTINCT source_id)
        FROM extractions
        WHERE source_type = 'posting' AND method = 'baseline_keyword'
        GROUP BY skill_id
        """
    )
    demand_counts_overall = dict(cur.fetchall())  # skill_id -> count of postings mentioning it

    print("Loading real role clusters and their per-skill demand counts...")
    cur.execute("SELECT cluster_id, role_label FROM role_clusters ORDER BY cluster_id")
    all_clusters = cur.fetchall()
    real_clusters = [
        (cid, label) for cid, label in all_clusters
        if not label.startswith(EXCLUDED_CLUSTER_LABEL_PREFIXES)
    ]
    excluded_clusters = [label for _, label in all_clusters if label.startswith(EXCLUDED_CLUSTER_LABEL_PREFIXES)]
    print(f"  {len(real_clusters)} real role clusters will get their own per-cluster gap analysis.")
    print(f"  Excluded (not coherent role groupings): {excluded_clusters}")

    cur.execute("SELECT cluster_id, COUNT(*) FROM posting_cluster_map GROUP BY cluster_id")
    cluster_total_postings = dict(cur.fetchall())

    cur.execute(
        """
        SELECT pcm.cluster_id, e.skill_id, COUNT(DISTINCT e.source_id)
        FROM extractions e
        JOIN posting_cluster_map pcm ON pcm.posting_id = e.source_id
        WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'
        GROUP BY pcm.cluster_id, e.skill_id
        """
    )
    demand_counts_by_cluster = {}  # cluster_id -> {skill_id -> count}
    for cluster_id, skill_id, count in cur.fetchall():
        demand_counts_by_cluster.setdefault(cluster_id, {})[skill_id] = count

    print("Loading skill names...")
    cur.execute("SELECT skill_id, canonical_name, category FROM skills")
    skill_info = {sid: (name, cat) for sid, name, cat in cur.fetchall()}

    relevant_overall = relevant_skills_for_scope(demand_counts_overall, skill_info)
    print(f"\n{len(relevant_overall)} of {len(skill_info)} skills have enough overall-market mentions (>= {MIN_MARKET_MENTIONS}) to test.")

    # Build the full list of scopes to run: overall market first (as
    # before, cluster_id=None), then one scope per real role cluster.
    scopes = [(None, "Overall market", total_postings, demand_counts_overall)]
    for cluster_id, role_label in real_clusters:
        cluster_demand = demand_counts_by_cluster.get(cluster_id, {})
        cluster_total = cluster_total_postings.get(cluster_id, 0)
        scopes.append((cluster_id, role_label, cluster_total, cluster_demand))

    print("Clearing previous gap_scores rows...")
    cur.execute("DELETE FROM gap_scores")

    period_label = "2023-2024 (Kaggle historical postings sample)"
    all_gap_rows = []
    scope_summaries = []  # for the console report: (scope_label, [(university, program_name, n_courses, gaps), ...])

    for cluster_id, scope_label, scope_total_n, scope_demand_counts in scopes:
        relevant_skill_ids = relevant_skills_for_scope(scope_demand_counts, skill_info)
        program_summaries = []

        for program_id, university, program_name in programs:
            n_courses = course_count_by_program.get(program_id, 0)
            if n_courses == 0 or scope_total_n == 0:
                continue

            gaps = compute_significant_gaps(
                program_id, n_courses, relevant_skill_ids, coverage_counts,
                scope_demand_counts, scope_total_n, skill_info,
            )
            for g in gaps:
                all_gap_rows.append(
                    (program_id, g["skill_id"], cluster_id, period_label, g["coverage_rate"],
                     g["demand_rate"], g["gap_value"], g["p_value"], g["q_value"])
                )
            program_summaries.append((university, program_name, n_courses, gaps))

        scope_summaries.append((scope_label, scope_total_n, len(relevant_skill_ids), program_summaries))

    cur.executemany(
        """INSERT INTO gap_scores
           (program_id, skill_id, cluster_id, period, program_coverage_rate, market_demand_rate, gap_value, p_value, q_value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        all_gap_rows,
    )
    conn.commit()
    conn.close()

    print(f"\nSaved {len(all_gap_rows)} statistically significant gap rows across {len(scopes)} scopes (overall market + {len(scopes) - 1} role clusters).")
    print("(Significance is based on the FDR-corrected q-value within each program+scope's own family of tests -- see the module docstring for why.)")
    print("\n" + "=" * 78)
    print("TOP GAPS PER PROGRAM, PER SCOPE (skills the market wants significantly more than the curriculum covers)")
    print("=" * 78)
    for scope_label, scope_total_n, n_relevant_skills, program_summaries in scope_summaries:
        print(f"\n\n### SCOPE: {scope_label}  ({scope_total_n} postings, {n_relevant_skills} skills tested)")
        for university, program_name, n_courses, gaps in program_summaries:
            print(f"\n{university} -- {program_name} ({n_courses} courses)")
            if not gaps:
                print("  No statistically significant gaps found.")
                continue
            for g in gaps[:TOP_N_PER_PROGRAM]:
                print(
                    f"  {g['skill_name']:<45} coverage={g['coverage_rate']*100:5.1f}%  "
                    f"market={g['demand_rate']*100:5.1f}%  gap={g['gap_value']*100:5.1f}pts  "
                    f"p={g['p_value']:.4f}  q={g['q_value']:.4f}"
                )

    print("\nDone.")


if __name__ == "__main__":
    main()
