"""
robustness_check.py: does the headline result survive when postings are not treated as independent?

The main analysis compares proportions with a z-test (or Fisher's exact test), which assumes every
posting is an independent observation. Postings from the same employer are not: one company can post
the same requirements many times (Capital One alone is 64 of the 1,660 postings). This script repeats
the overall-market gap tests with a cluster-robust variance for the posting side, clustering by company,
and reports how many of the published significant gaps still hold, with confidence intervals on every gap.

    python scripts/gap_analysis/robustness_check.py     # writes data/robustness/cluster_robust_gaps.json

It does NOT change gap_scores or any published number. Both checks below are SENSITIVITY ANALYSES, not
replacement tests: the design-effect adjustment is an approximation (effective counts are rounded and the original
test is rerun on them), so a second, independent method is reported next to it.

Second method, company-cluster bootstrap: resample companies (with all of their postings) with replacement
2,000 times, and for each published gap recompute the posting-side mention rate; the course side is redrawn as
Binomial(n_courses, observed coverage). The 2.5th and 97.5th percentiles of (demand - coverage) give a 95% interval.

Method (design-effect adjustment, the standard correction for clustered samples):
  For each skill, the design effect deff = cluster-robust variance of the mention rate (postings grouped by
  company, ratio estimator) divided by the variance under independence. deff >= 1 means the postings carry
  less information than 1,660 independent ones. The posting side is replaced by its effective size,
  x2/deff of n2/deff, and the ORIGINAL test (z-test, or Fisher's exact when expected counts are small) is rerun,
  followed by the same Benjamini-Hochberg correction within each program.
  Confidence intervals for each gap use Newcombe's hybrid-Wilson interval on the effective counts.
Courses are treated as the sampled units within a program (the program's own offerings are the population),
so the course side is unchanged.
"""

import json
import math
import random
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db")
OUT_PATH = os.path.join(BASE_DIR, "data", "robustness", "cluster_robust_gaps.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compute_gap_scores import (  # noqa: E402
    MIN_MARKET_MENTIONS, SIGNIFICANCE_THRESHOLD, apply_fdr_correction, compare_proportions, relevant_skills_for_scope,
)

Z95 = 1.959964


def cluster_robust_variance(clusters, skill_postings, total):
    """Variance of the overall mention rate of one skill with postings grouped by cluster key.
    clusters: {key: [posting_id, ...]}; skill_postings: set of posting ids mentioning the skill."""
    p = len(skill_postings) / total
    g = len(clusters)
    if g < 2:
        return p * (1 - p) / total
    ssq = 0.0
    for members in clusters.values():
        y = sum(1 for m in members if m in skill_postings)
        ssq += (y - p * len(members)) ** 2
    return g / (g - 1) * ssq / total ** 2


def wilson(x, n, z=Z95):
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def newcombe_diff_ci(x1, n1, x2, n2):
    """95% interval for p2 - p1 (Newcombe's hybrid-score method)."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1)
    l2, u2 = wilson(x2, n2)
    d = p2 - p1
    return d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)


def design_effect(var_cluster, count, total):
    p = count / total
    srs = p * (1 - p) / total
    return max(1.0, var_cluster / srs) if srs > 0 else 1.0


def robust_test(x1, n1, x2, n2, deff):
    """Rerun the original test with the posting side shrunk to its effective size. Returns (gap, p, (lo, hi))."""
    n2e = max(1, round(n2 / deff))
    x2e = min(n2e, round(x2 / deff))
    _, p_value, _ = compare_proportions(x1, n1, x2e, n2e)
    lo, hi = newcombe_diff_ci(x1, n1, x2e, n2e)
    return x2 / n2 - x1 / n1, p_value, (lo, hi)


BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 11


def cluster_bootstrap_intervals(clusters, by_skill, tested_pairs, n_courses, coverage, rounds=BOOTSTRAP_ROUNDS, seed=BOOTSTRAP_SEED):
    """95% percentile intervals for (demand - coverage) for each (program_id, skill_id) pair, resampling companies.
    Pure-Python (no numpy dependency): 1,011 companies x a few hundred skills x 2,000 rounds is fast enough."""
    rng = random.Random(seed)
    keys = list(clusters)
    sizes = [len(clusters[k]) for k in keys]
    skills = sorted({sid for _, sid in tested_pairs})
    # per company: number of postings mentioning each skill
    pos = {sid: [sum(1 for m in clusters[k] if m in by_skill[sid]) for k in keys] for sid in skills}
    diffs = {pair: [] for pair in tested_pairs}
    g = len(keys)
    for _ in range(rounds):
        idx = [rng.randrange(g) for _ in range(g)]
        total = sum(sizes[i] for i in idx)
        rates = {sid: sum(pos[sid][i] for i in idx) / total for sid in skills}
        for (pid, sid) in tested_pairs:
            n1 = n_courses[pid]
            p1 = coverage.get((pid, sid), 0) / n1
            c1 = sum(rng.random() < p1 for _ in range(n1)) / n1
            diffs[(pid, sid)].append(rates[sid] - c1)
    out = {}
    for pair, values in diffs.items():
        values.sort()
        out[pair] = (values[int(0.025 * rounds)], values[int(0.975 * rounds) - 1])
    return out


def run(db_path=DB_PATH, bootstrap_rounds=BOOTSTRAP_ROUNDS):
    conn = sqlite3.connect(db_path)
    skill_info = {sid: (name, cat) for sid, name, cat in conn.execute("SELECT skill_id, canonical_name, category FROM skills")}
    postings = conn.execute("SELECT posting_id, LOWER(TRIM(company)) FROM postings WHERE source = 'kaggle_sample'").fetchall()
    total = len(postings)
    clusters = {}
    for pid, company in postings:
        clusters.setdefault(company or f"_unknown_{pid}", []).append(pid)

    by_skill = {}
    for sid, pid in conn.execute(
        "SELECT skill_id, source_id FROM extractions WHERE source_type = 'posting' AND method = 'baseline_keyword'"
    ):
        by_skill.setdefault(sid, set()).add(pid)
    demand_counts = {sid: len(s) for sid, s in by_skill.items()}
    tested = [sid for sid in relevant_skills_for_scope(demand_counts, skill_info)]
    deffs = {sid: design_effect(cluster_robust_variance(clusters, by_skill[sid], total), demand_counts[sid], total) for sid in tested}

    n_courses = dict(conn.execute("SELECT program_id, COUNT(*) FROM courses GROUP BY program_id"))
    coverage = {}
    for pid, sid, n in conn.execute(
        """SELECT c.program_id, e.skill_id, COUNT(DISTINCT e.source_id) FROM extractions e
           JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
           WHERE e.source_type = 'course' AND e.method = 'baseline_keyword' GROUP BY 1, 2"""
    ):
        coverage[(pid, sid)] = n
    published = {(r[0], r[1]) for r in conn.execute("SELECT program_id, skill_id FROM gap_scores WHERE cluster_id IS NULL")}
    programs = conn.execute("SELECT program_id, university, program_name FROM programs").fetchall()

    rows = []
    for program_id, university, program_name in programs:
        n1 = n_courses[program_id]
        cands = []
        for sid in tested:
            x1 = coverage.get((program_id, sid), 0)
            p2 = demand_counts[sid] / total
            diff, p_value, ci = robust_test(x1, n1, demand_counts[sid], total, deffs[sid])
            cands.append((sid, x1, p2, diff, p_value, ci))
        qs = apply_fdr_correction([c[4] for c in cands])
        for (sid, x1, p2, diff, p_value, ci), q in zip(cands, qs):
            rows.append({
                "program_id": program_id, "program": f"{university} · {program_name}", "skill_id": sid, "skill": skill_info[sid][0],
                "coverage_rate": x1 / n1, "demand_rate": p2, "gap": diff, "gap_ci_low": ci[0], "gap_ci_high": ci[1], "design_effect": deffs[sid],
                "robust_p": p_value, "robust_q": float(q), "robust_significant": bool(diff > 0 and q < SIGNIFICANCE_THRESHOLD),
                "published_significant": (program_id, sid) in published,
            })

    boot = cluster_bootstrap_intervals(clusters, by_skill, [(r["program_id"], r["skill_id"]) for r in rows if r["published_significant"]],
                                       n_courses, coverage, rounds=bootstrap_rounds)
    for r in rows:
        if r["published_significant"]:
            lo, hi = boot[(r["program_id"], r["skill_id"])]
            r["bootstrap_ci_low"], r["bootstrap_ci_high"], r["bootstrap_excludes_zero"] = lo, hi, bool(lo > 0)
    pub = [r for r in rows if r["published_significant"]]
    kept = [r for r in pub if r["robust_significant"]]
    newly = [r for r in rows if r["robust_significant"] and not r["published_significant"]]
    # Effective sample size: how many independent postings the 1,660 are worth, for a typical skill.
    deff = sorted(deffs.values())
    summary = {
        "postings": total, "companies": len(clusters), "largest_company_share": max(len(m) for m in clusters.values()) / total,
        "published_gaps": len(pub), "bootstrap_excludes_zero": sum(1 for r in pub if r["bootstrap_excludes_zero"]),
        "bootstrap_rounds": bootstrap_rounds, "still_significant": len(kept), "lost": len(pub) - len(kept), "newly_significant": len(newly),
        "median_design_effect": deff[len(deff) // 2] if deff else None,
        "min_market_mentions": MIN_MARKET_MENTIONS,
    }
    conn.close()
    return summary, rows


def main(argv=None):
    summary, rows = run()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "gaps": [r for r in rows if r["published_significant"]]}, f, indent=1)
    s = summary
    print(f"{s['postings']} postings from {s['companies']} companies (largest company = {s['largest_company_share']*100:.1f}%).")
    print(f"Published significant gaps: {s['published_gaps']}; still significant with company-clustered variance: {s['still_significant']}; "
          f"lost: {s['lost']}; newly significant: {s['newly_significant']}.")
    print(f"Company-cluster bootstrap ({s['bootstrap_rounds']} rounds): {s['bootstrap_excludes_zero']} of {s['published_gaps']} published gaps have a 95% interval above zero.")
    print(f"Median design effect: {s['median_design_effect']:.2f} (1.00 = no clustering effect).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
