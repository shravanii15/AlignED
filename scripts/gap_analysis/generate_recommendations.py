"""
generate_recommendations.py

What this script does, in plain terms:
This is the payoff step that ties everything from Week 3 together. It
takes the statistically significant gaps found by compute_gap_scores.py
("this program under-covers this skill relative to how often it shows up
in our sampled job postings") and cross-references each one against
compute_skill_trends.py ("and is demand for this skill rising, falling,
or flat?") to produce one final, ranked, plain-English recommendation
list -- the kind of output a real curriculum advisory board or program
director could actually read and act on, not just a table of raw
numbers.

As of this version, gap_scores contains rows at TWO scopes -- overall
market (cluster_id NULL) and per real role cluster (cluster_id set) --
so this script now generates a separate ranked recommendation list for
EACH (program, scope) combination, not just each program. A program's
top-3 recommendations "vs. the overall market" and its top-3
recommendations "vs. Data Scientist postings specifically" are
genuinely different lists, computed and ranked independently, because
they're answering different questions.

How the priority ranking works (unchanged from before, per scope):
Each gap already has a gap_value (how many percentage points the market
wants a skill more than the curriculum covers it, within that scope). We
adjust that number up or down based on the trend:
  - Rising demand -> priority boosted 50% (this gap is getting MORE
    urgent over time, not less)
  - Falling demand -> priority reduced 30% (still a real, statistically
    significant gap today, but worth a lower priority than a rising one)
  - No trend data / no significant trend -> left as-is
This is a simple, explainable weighting scheme (not a black-box model),
chosen deliberately -- for a recommendation a real person needs to trust
and act on, being able to say exactly *why* something is ranked where it
is matters more than squeezing out a slightly "smarter" black-box score.
Trend data itself is only tracked at the overall-market level (there
isn't enough per-cluster historical volume to detect a per-cluster
trend), so the same trend label/slope is used regardless of scope.

Within each (program, scope) combination, the top 3 recommendations by
adjusted priority are labeled 'high', the next 4 'medium', and the rest
'low' -- simple, consistent tiers rather than an arbitrary numeric
cutoff.
"""

import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "gap_analysis", "recommendations.json")
OUTPUT_REPORT_PATH = os.path.join(BASE_DIR, "data", "gap_analysis", "recommendations_report.txt")

RISING_BOOST = 1.5
FALLING_PENALTY = 0.7
TOP_N_HIGH = 3
TOP_N_MEDIUM = 4  # ranks 4-7 -> medium, everything after -> low
MAX_RECOMMENDATIONS_PER_PROGRAM = 10


def build_rationale(skill_name, coverage_rate, demand_rate, gap_value, trend_label, slope, scope_label="Overall market"):
    # Deliberately precise wording: "statistically significant" describes
    # the *observed text coverage* in this sampled corpus -- it does not
    # mean "the market really wants this skill" in some absolute sense
    # (the postings sample isn't a random draw from the whole labor
    # market, and "coverage" is a text-mention proxy, not a depth-of-
    # instruction measurement). See the dashboard's Methodology page for
    # the full reasoning.
    demand_phrase = (
        f"{demand_rate * 100:.0f}% of real job postings we sampled"
        if scope_label == "Overall market"
        else f"{demand_rate * 100:.0f}% of real {scope_label} postings we sampled"
    )
    base = (
        f"{skill_name} appears in {demand_phrase}, "
        f"but only {coverage_rate * 100:.0f}% of this program's courses cover it -- "
        f"a {gap_value * 100:.0f} percentage-point gap that's a statistically significant "
        f"difference in observed text coverage, not noise from a small sample."
    )
    if trend_label == "rising":
        return base + f" Demand for {skill_name} is also trending upward, making this a higher-priority addition."
    if trend_label == "falling":
        return base + f" That said, demand for {skill_name} has been trending downward recently, so this may be a lower priority than it first appears."
    return base + " No significant demand trend was detected either way over the available time window."


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    cur.execute(
        """
        SELECT g.program_id, p.university, p.program_name, g.cluster_id, g.skill_id, s.canonical_name,
               g.program_coverage_rate, g.market_demand_rate, g.gap_value
        FROM gap_scores g
        JOIN programs p ON p.program_id = g.program_id
        JOIN skills s ON s.skill_id = g.skill_id
        """
    )
    gap_rows = cur.fetchall()
    print(f"Loaded {len(gap_rows)} significant gap rows (all scopes).")

    cur.execute("SELECT cluster_id, role_label FROM role_clusters")
    role_label_by_cluster = dict(cur.fetchall())

    cur.execute("SELECT skill_id, trend_label, slope FROM skill_trends")
    trend_by_skill = {sid: (label, slope) for sid, label, slope in cur.fetchall()}
    print(f"Loaded trend data for {len(trend_by_skill)} skills.")

    cur.execute("DELETE FROM recommendations")

    # Group by (program_id, cluster_id) -- each combination gets its own
    # independently ranked top-N list, since "top gaps vs. the overall
    # market" and "top gaps vs. Data Scientist postings" are different
    # questions with different answers.
    by_scope = {}
    for program_id, university, program_name, cluster_id, skill_id, skill_name, coverage_rate, demand_rate, gap_value in gap_rows:
        trend_label, slope = trend_by_skill.get(skill_id, ("no trend data", None))
        scope_label = "Overall market" if cluster_id is None else role_label_by_cluster.get(cluster_id, f"Cluster {cluster_id}")

        priority_score = gap_value
        if trend_label == "rising":
            priority_score *= RISING_BOOST
        elif trend_label == "falling":
            priority_score *= FALLING_PENALTY

        rationale = build_rationale(skill_name, coverage_rate, demand_rate, gap_value, trend_label, slope, scope_label)

        entry = {
            "program_id": program_id,
            "university": university,
            "program_name": program_name,
            "cluster_id": cluster_id,
            "scope_label": scope_label,
            "skill_id": skill_id,
            "skill_name": skill_name,
            "coverage_rate": coverage_rate,
            "demand_rate": demand_rate,
            "gap_value": gap_value,
            "trend_label": trend_label,
            "priority_score": priority_score,
            "rationale": rationale,
        }
        key = (program_id, cluster_id)
        by_scope.setdefault(key, {"university": university, "program_name": program_name, "scope_label": scope_label, "items": []})
        by_scope[key]["items"].append(entry)

    all_recommendations = []
    insert_rows = []
    report_lines = []
    report_lines.append("AlignED -- Curriculum Gap Recommendations")
    report_lines.append("=" * 78)
    report_lines.append(
        "Each recommendation combines a statistically significant skill gap "
        "(gap scoring, at a given scope: overall market or one target role) "
        "with that skill's demand trend into one ranked, explained priority "
        "per program per scope.\n"
    )

    n_scopes_with_recs = 0
    for (program_id, cluster_id), data in by_scope.items():
        items = sorted(data["items"], key=lambda e: e["priority_score"], reverse=True)
        items = items[:MAX_RECOMMENDATIONS_PER_PROGRAM]
        if items:
            n_scopes_with_recs += 1

        report_lines.append(f"\n{data['university']} -- {data['program_name']}  [scope: {data['scope_label']}]")
        report_lines.append("-" * 78)

        for rank, item in enumerate(items):
            if rank < TOP_N_HIGH:
                tier = "high"
            elif rank < TOP_N_HIGH + TOP_N_MEDIUM:
                tier = "medium"
            else:
                tier = "low"

            item["priority_tier"] = tier
            item["rank"] = rank + 1
            all_recommendations.append(item)
            insert_rows.append(
                (
                    item["program_id"], item["skill_id"], cluster_id, item["gap_value"], item["trend_label"],
                    item["priority_score"], tier, item["rationale"],
                )
            )

            report_lines.append(f"  [{tier.upper():<6}] #{rank + 1} {item['skill_name']}")
            report_lines.append(f"           {item['rationale']}")

        if not items:
            report_lines.append("  No significant gaps found for this program/scope.")

    cur.executemany(
        """INSERT INTO recommendations
           (program_id, skill_id, cluster_id, gap_value, trend_label, priority_score, priority_tier, rationale)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        insert_rows,
    )
    conn.commit()
    conn.close()

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_recommendations, f, indent=2)
    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    n_programs = len({pid for pid, _ in by_scope})
    print(f"\nSaved {len(all_recommendations)} ranked recommendations across {n_programs} programs and {len(by_scope)} program/scope combinations ({n_scopes_with_recs} with at least one recommendation).")
    print(f"  -> {OUTPUT_JSON_PATH}")
    print(f"  -> {OUTPUT_REPORT_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    main()
