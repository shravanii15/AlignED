"""
generate_recommendations.py

What this script does, in plain terms:
This is the payoff step that ties everything from Week 3 together. It
takes the statistically significant gaps found by compute_gap_scores.py
("this program under-covers this skill, and the market really does want
it more") and cross-references each one against compute_skill_trends.py
("and is demand for this skill rising, falling, or flat?") to produce one
final, ranked, plain-English recommendation list per program -- the kind
of output a real curriculum advisory board or program director could
actually read and act on, not just a table of raw numbers.

How the priority ranking works:
Each gap already has a gap_value (how many percentage points the market
wants a skill more than the curriculum covers it). We adjust that number
up or down based on the trend:
  - Rising demand -> priority boosted 50% (this gap is getting MORE
    urgent over time, not less)
  - Falling demand -> priority reduced 30% (still a real, statistically
    significant gap today, but worth a lower priority than a rising one)
  - No trend data / no significant trend -> left as-is
This is a simple, explainable weighting scheme (not a black-box model),
chosen deliberately -- for a recommendation a real person needs to trust
and act on, being able to say exactly *why* something is ranked where it
is matters more than squeezing out a slightly "smarter" black-box score.

Within each program, the top 3 recommendations by adjusted priority are
labeled 'high', the next 4 'medium', and the rest 'low' -- simple,
consistent tiers rather than an arbitrary numeric cutoff.
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


def build_rationale(skill_name, coverage_rate, demand_rate, gap_value, trend_label, slope):
    base = (
        f"{skill_name} appears in {demand_rate * 100:.0f}% of real job postings we sampled, "
        f"but only {coverage_rate * 100:.0f}% of this program's courses cover it -- "
        f"a {gap_value * 100:.0f} percentage-point gap that's statistically real, not noise."
    )
    if trend_label == "rising":
        return base + f" Demand for {skill_name} is also trending upward, making this a higher-priority addition."
    if trend_label == "falling":
        return base + f" That said, demand for {skill_name} has been trending downward recently, so this may be a lower priority than it first appears."
    return base + " No significant demand trend was detected either way over the available time window."


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT g.program_id, p.university, p.program_name, g.skill_id, s.canonical_name,
               g.program_coverage_rate, g.market_demand_rate, g.gap_value
        FROM gap_scores g
        JOIN programs p ON p.program_id = g.program_id
        JOIN skills s ON s.skill_id = g.skill_id
        """
    )
    gap_rows = cur.fetchall()
    print(f"Loaded {len(gap_rows)} significant gap rows.")

    cur.execute("SELECT skill_id, trend_label, slope FROM skill_trends")
    trend_by_skill = {sid: (label, slope) for sid, label, slope in cur.fetchall()}
    print(f"Loaded trend data for {len(trend_by_skill)} skills.")

    cur.execute("DELETE FROM recommendations")

    by_program = {}
    for program_id, university, program_name, skill_id, skill_name, coverage_rate, demand_rate, gap_value in gap_rows:
        trend_label, slope = trend_by_skill.get(skill_id, ("no trend data", None))

        priority_score = gap_value
        if trend_label == "rising":
            priority_score *= RISING_BOOST
        elif trend_label == "falling":
            priority_score *= FALLING_PENALTY

        rationale = build_rationale(skill_name, coverage_rate, demand_rate, gap_value, trend_label, slope)

        entry = {
            "program_id": program_id,
            "university": university,
            "program_name": program_name,
            "skill_id": skill_id,
            "skill_name": skill_name,
            "coverage_rate": coverage_rate,
            "demand_rate": demand_rate,
            "gap_value": gap_value,
            "trend_label": trend_label,
            "priority_score": priority_score,
            "rationale": rationale,
        }
        by_program.setdefault(program_id, {"university": university, "program_name": program_name, "items": []})
        by_program[program_id]["items"].append(entry)

    all_recommendations = []
    insert_rows = []
    report_lines = []
    report_lines.append("AlignED -- Curriculum Gap Recommendations")
    report_lines.append("=" * 78)
    report_lines.append(
        "Each recommendation combines a statistically significant skill gap "
        "(Week 3, gap scoring) with that skill's demand trend (Week 3, trend "
        "detection) into one ranked, explained priority per program.\n"
    )

    for program_id, data in by_program.items():
        items = sorted(data["items"], key=lambda e: e["priority_score"], reverse=True)
        items = items[:MAX_RECOMMENDATIONS_PER_PROGRAM]

        report_lines.append(f"\n{data['university']} -- {data['program_name']}")
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
                    item["program_id"], item["skill_id"], item["gap_value"], item["trend_label"],
                    item["priority_score"], tier, item["rationale"],
                )
            )

            report_lines.append(f"  [{tier.upper():<6}] #{rank + 1} {item['skill_name']}")
            report_lines.append(f"           {item['rationale']}")

        if not items:
            report_lines.append("  No significant gaps found for this program.")

    cur.executemany(
        """INSERT INTO recommendations
           (program_id, skill_id, gap_value, trend_label, priority_score, priority_tier, rationale)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        insert_rows,
    )
    conn.commit()
    conn.close()

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(all_recommendations, f, indent=2)
    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\nSaved {len(all_recommendations)} ranked recommendations across {len(by_program)} programs.")
    print(f"  -> {OUTPUT_JSON_PATH}")
    print(f"  -> {OUTPUT_REPORT_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    main()
