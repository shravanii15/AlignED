"""
compute_gap_scores.py

What this script does, in plain terms:
This is the actual "gap analysis" -- the payoff of everything built so
far. For every university program, and for every real O*NET skill, it
answers one question: "Is this skill significantly more in-demand in the
real job market than it's covered in this program's coursework?"

How it works, step by step:
1. For each program, compute its "coverage rate" for a skill: what
   fraction of that program's courses mention the skill at least once
   (from the extractions table, source_type='course').
2. Compute the overall "market demand rate" for the same skill: what
   fraction of our 1,660 sampled job postings mention it
   (source_type='posting').
3. The raw gap is simply market_demand_rate - program_coverage_rate. A
   positive number means the market wants it more than the curriculum
   covers it -- a real candidate gap.
4. But with only ~90-140 courses per program, a raw percentage-point
   difference can easily be noise from small sample size, not a real
   signal. So for every (program, skill) pair we run a two-proportion
   z-test -- a standard statistics test for "are these two rates actually
   different, or could this difference plausibly have happened by chance
   alone?"
5. Here's the subtlety a lot of "portfolio" statistics projects miss:
   we're not running ONE test, we're running ~70 tests per program (one
   per relevant skill) at once. If each test has a 5% chance of a false
   positive on its own, running 70 of them means we should EXPECT a
   handful of "significant" results to be false alarms just from running
   that many tests -- this is the classic "multiple comparisons" problem
   (the same issue behind the "green jellybeans cause acne" XKCD joke).
   So instead of trusting the raw p-value directly, we apply a
   Benjamini-Hochberg false discovery rate (FDR) correction across each
   program's full set of tests, and only call something significant if
   its *corrected* p-value (the "q-value") is below 0.05. We use
   Benjamini-Hochberg rather than the stricter Bonferroni correction
   because Bonferroni is built for "zero tolerance for any false
   positive," which is appropriate for something like a clinical drug
   trial, but is so conservative here it would likely wipe out most real
   findings; FDR instead controls the *expected proportion* of false
   positives among the results we call significant, which is the more
   standard, practical choice for this kind of exploratory analysis.
6. Save every significant, positive gap to the gap_scores table (with
   both the raw p-value and the corrected q-value, for transparency),
   and print each program's top gaps to the console as a human-readable
   summary.

Why this matters for the project:
Anyone can eyeball two lists and guess "this program seems light on
cloud skills." This script instead makes that claim with a real,
falsifiable statistical basis -- the same two-proportion z-test used in
A/B testing and clinical trials -- which is a meaningfully stronger claim
for a portfolio project.
"""

import os
import sqlite3

from scipy.stats import false_discovery_control, norm

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")

SIGNIFICANCE_THRESHOLD = 0.05
TOP_N_PER_PROGRAM = 15
# Ignore skills the market data barely mentions -- a skill mentioned in
# only 1-2 of 1,660 postings isn't a meaningful "market demand" signal,
# and including it just adds noise to the z-test at these tiny counts.
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


def two_proportion_z_test(x1, n1, x2, n2):
    """Standard two-proportion z-test. x1/n1 and x2/n2 are the two
    "successes out of trials" counts being compared (here: courses
    mentioning a skill out of all courses in a program, vs. postings
    mentioning a skill out of all sampled postings). Returns (z, p_value).
    If either group has zero trials, or the pooled variance is zero
    (e.g. the rate is 0% or 100% in both groups), there's nothing
    meaningful to test, so we return a p-value of 1.0 (not significant)."""
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
    skill tested for one program), returning the corrected "q-values" in
    the same order. Each q-value is always >= the raw p-value it came
    from -- correction can only make a result look less significant,
    never more, which is exactly the conservative direction you want
    when guarding against false positives from running many tests at
    once. An empty input returns an empty list (nothing to correct)."""
    if not p_values:
        return []
    return list(false_discovery_control(p_values, method="bh"))


def main():
    conn = sqlite3.connect(DB_PATH)
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

    print("Loading market-wide posting counts and per-skill demand counts...")
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
    demand_counts = dict(cur.fetchall())  # skill_id -> count of postings mentioning it

    print("Loading skill names...")
    cur.execute("SELECT skill_id, canonical_name, category FROM skills")
    skill_info = {sid: (name, cat) for sid, name, cat in cur.fetchall()}

    # Only test skills with meaningful market signal, and skip the
    # generic, keyword-ambiguous terms documented above.
    relevant_skill_ids = [
        sid for sid, count in demand_counts.items()
        if count >= MIN_MARKET_MENTIONS and skill_info[sid][0].strip().lower() not in AMBIGUOUS_GENERIC_TERMS
    ]
    excluded_count = sum(
        1 for sid, count in demand_counts.items()
        if count >= MIN_MARKET_MENTIONS and skill_info[sid][0].strip().lower() in AMBIGUOUS_GENERIC_TERMS
    )
    print(f"\n{len(relevant_skill_ids)} of {len(skill_info)} skills have enough market mentions (>= {MIN_MARKET_MENTIONS}) to test.")
    print(f"({excluded_count} generic/ambiguous terms excluded -- see AMBIGUOUS_GENERIC_TERMS.)")

    print("Clearing previous gap_scores rows...")
    cur.execute("DELETE FROM gap_scores")

    period_label = "2023-2024 (Kaggle historical postings sample)"
    all_gap_rows = []
    program_summaries = []

    for program_id, university, program_name in programs:
        n_courses = course_count_by_program.get(program_id, 0)
        if n_courses == 0:
            continue

        # First pass: compute every skill's raw p-value for THIS program.
        # The FDR correction has to see the full family of tests run for
        # this program at once -- correcting one skill's p-value in
        # isolation would defeat the whole point.
        candidates = []
        for skill_id in relevant_skill_ids:
            x_courses = coverage_counts.get((program_id, skill_id), 0)
            x_postings = demand_counts.get(skill_id, 0)
            coverage_rate = x_courses / n_courses
            demand_rate = x_postings / total_postings
            gap_value = demand_rate - coverage_rate
            _, p_value = two_proportion_z_test(x_courses, n_courses, x_postings, total_postings)
            candidates.append(
                {
                    "skill_id": skill_id,
                    "coverage_rate": coverage_rate,
                    "demand_rate": demand_rate,
                    "gap_value": gap_value,
                    "p_value": p_value,
                }
            )

        # Second pass: correct all of this program's p-values together,
        # then decide significance using the corrected q-value instead of
        # the raw p-value.
        q_values = apply_fdr_correction([c["p_value"] for c in candidates])
        for c, q_value in zip(candidates, q_values):
            c["q_value"] = q_value

        program_gaps = []
        for c in candidates:
            if c["gap_value"] > 0 and c["q_value"] < SIGNIFICANCE_THRESHOLD:
                skill_id = c["skill_id"]
                program_gaps.append(
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
                all_gap_rows.append(
                    (program_id, skill_id, None, period_label, c["coverage_rate"], c["demand_rate"],
                     c["gap_value"], c["p_value"], c["q_value"])
                )

        program_gaps.sort(key=lambda g: g["gap_value"], reverse=True)
        program_summaries.append((university, program_name, n_courses, program_gaps))

    cur.executemany(
        """INSERT INTO gap_scores
           (program_id, skill_id, cluster_id, period, program_coverage_rate, market_demand_rate, gap_value, p_value, q_value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        all_gap_rows,
    )
    conn.commit()
    conn.close()

    print(f"\nSaved {len(all_gap_rows)} statistically significant gap rows across {len(program_summaries)} programs.")
    print("(Significance is now based on the FDR-corrected q-value, not the raw p-value -- see the module docstring for why.)")
    print("\n" + "=" * 78)
    print("TOP GAPS PER PROGRAM (skills the market wants significantly more than the curriculum covers)")
    print("=" * 78)
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
