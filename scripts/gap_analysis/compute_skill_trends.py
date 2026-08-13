"""
compute_skill_trends.py

What this script does, in plain terms:
Reads the weekly skill-mention counts built by extract_posting_trends.py
and answers, for each tracked skill: "is demand for this trending up,
down, or basically flat?"

Two methods, compared on purpose (same "don't just build one thing, prove
which approach is better/simpler" pattern as Week 2's AI-vs-baseline
comparison):

1. A simple baseline: split the available weeks in half, average the
   demand rate in each half, and report the percent change. Easy to
   explain to a non-technical audience, but only looks at two coarse
   chunks of time and throws away the week-by-week pattern.

2. Linear regression with a significance test: fit a straight line
   through ALL the weekly demand-rate points (using scipy's linregress),
   and check whether the slope is statistically different from zero
   (p < 0.05) rather than just eyeballing two averages. This is the more
   rigorous method, and it's what actually decides each skill's final
   'rising' / 'falling' / 'no clear trend' label.

An honest scope note: the historical dataset only covers about 4.5
months (17 real weeks, with 2 weeks missing from the raw data -- a real
data quality gap, not a bug in our code). That's a short window for
serious time-series forecasting, so what this really produces is early
trend *detection* over the available window, not a long-range forecast.
The daily Adzuna pipeline built in Week 1 keeps extending this window for
real, going forward.
"""

import json
import os
import sqlite3

from scipy.stats import linregress

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # .../AlignED
DB_PATH = os.path.join(BASE_DIR, "database", "aligned.db")
CHECKPOINT_PATH = os.path.join(BASE_DIR, "data", "gap_analysis", "trend_extraction_checkpoint.json")
OUTPUT_JSON_PATH = os.path.join(BASE_DIR, "data", "gap_analysis", "skill_trends.json")

SIGNIFICANCE_THRESHOLD = 0.05
MIN_WEEKS_REQUIRED = 5  # need a reasonable number of points before trying to fit a trend line

# Real data-quality finding, caught by actually inspecting the raw weekly
# totals before trusting any trend numbers: postings in this historical
# dataset are NOT evenly spread across the ~4.5 month window. The first
# 10 of 17 weeks combined have only ~26 postings total, while the single
# last week alone has 84,744 -- 68% of the entire dataset. This is almost
# certainly a data-collection artifact (e.g. a bulk export/scrape
# timestamp), not real listing activity concentrated in one week. Trying
# to fit a trend across weeks with only 1-6 postings would just be fitting
# noise, so we exclude any week below this volume threshold and are
# upfront about only trusting the well-populated weeks that remain.
MIN_POSTINGS_PER_WEEK = 100


def classify_trend(slope, p_value):
    if p_value >= SIGNIFICANCE_THRESHOLD:
        return "no clear trend"
    return "rising" if slope > 0 else "falling"


def main():
    print(f"Loading extraction checkpoint from: {CHECKPOINT_PATH}")
    with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)

    if not state.get("done"):
        print("WARNING: checkpoint is not marked done -- extract_posting_trends.py may not have finished. Proceeding anyway with whatever data is present.")

    week_totals = state["week_totals"]
    skill_week_counts = state["skill_week_counts"]
    all_weeks_sorted = sorted(week_totals.keys())
    print(f"Weeks available (raw): {len(all_weeks_sorted)} -> {all_weeks_sorted}")
    for w in all_weeks_sorted:
        print(f"    {w}: {week_totals[w]} postings")

    weeks_sorted = [w for w in all_weeks_sorted if week_totals[w] >= MIN_POSTINGS_PER_WEEK]
    dropped = [w for w in all_weeks_sorted if w not in weeks_sorted]
    print(f"\nDropping {len(dropped)} sparse weeks with < {MIN_POSTINGS_PER_WEEK} postings (likely a data-collection artifact, not real low activity): {dropped}")
    print(f"Using {len(weeks_sorted)} well-populated weeks for trend detection: {weeks_sorted}")

    # Same generic, keyword-ambiguous terms excluded during gap scoring
    # (common English words that a plain keyword scan can't disambiguate
    # from unrelated text), plus a few more single/short tokens that
    # turned up as clearly spurious matches once we actually looked at
    # the first trend results (e.g. "Route", "Ada" matching inside
    # unrelated words/phrases like "ADA compliance" boilerplate).
    AMBIGUOUS_GENERIC_TERMS = {
        "design", "science", "writing", "monitoring", "programming",
        "troubleshooting", "mathematics", "coordination", "instructing",
        "repairing", "speaking", "route", "ada",
    }

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT skill_id, canonical_name FROM skills")
    skill_names = {
        str(sid): name for sid, name in cur.fetchall()
        if name.strip().lower() not in AMBIGUOUS_GENERIC_TERMS
    }

    cur.execute("DELETE FROM skill_trends")

    results = []
    insert_rows = []
    skipped_too_few_weeks = 0

    for skill_id_str, week_counts in skill_week_counts.items():
        if skill_id_str not in skill_names:
            continue  # excluded ambiguous/generic term
        # Build the full weekly series (0 where the skill wasn't
        # mentioned that week, not just the weeks it happened to appear).
        rates = []
        for i, week in enumerate(weeks_sorted):
            count = week_counts.get(week, 0)
            total = week_totals[week]
            rates.append(count / total if total else 0.0)

        if len(rates) < MIN_WEEKS_REQUIRED:
            skipped_too_few_weeks += 1
            continue

        week_indices = list(range(len(rates)))
        slope, intercept, r_value, p_value, std_err = linregress(week_indices, rates)

        midpoint = len(rates) // 2
        first_half_rate = sum(rates[:midpoint]) / midpoint if midpoint else 0.0
        second_half_rate = sum(rates[midpoint:]) / (len(rates) - midpoint) if (len(rates) - midpoint) else 0.0

        trend_label = classify_trend(slope, p_value)
        skill_name = skill_names.get(skill_id_str, f"skill_id={skill_id_str}")

        result = {
            "skill_id": int(skill_id_str),
            "skill_name": skill_name,
            "weeks_covered": len(rates),
            "slope": slope,
            "p_value": p_value,
            "r_squared": r_value ** 2,
            "trend_label": trend_label,
            "first_half_rate": first_half_rate,
            "second_half_rate": second_half_rate,
        }
        results.append(result)
        insert_rows.append(
            (int(skill_id_str), len(rates), slope, p_value, r_value ** 2, trend_label, first_half_rate, second_half_rate)
        )

    cur.executemany(
        """INSERT INTO skill_trends
           (skill_id, weeks_covered, slope, p_value, r_squared, trend_label, first_half_rate, second_half_rate)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        insert_rows,
    )
    conn.commit()
    conn.close()

    os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    rising = sorted([r for r in results if r["trend_label"] == "rising"], key=lambda r: r["slope"], reverse=True)
    falling = sorted([r for r in results if r["trend_label"] == "falling"], key=lambda r: r["slope"])
    stable = [r for r in results if r["trend_label"] == "no clear trend"]

    print(f"\n{skipped_too_few_weeks} skills skipped (fewer than {MIN_WEEKS_REQUIRED} weeks of data).")
    print(f"Saved {len(results)} skill trend rows to the database and to: {OUTPUT_JSON_PATH}")

    print("\n" + "=" * 78)
    print(f"RISING skills ({len(rising)}) -- statistically significant upward trend, p < {SIGNIFICANCE_THRESHOLD}")
    print("=" * 78)
    for r in rising:
        print(
            f"  {r['skill_name']:<20} first-half={r['first_half_rate']*100:5.1f}%  "
            f"second-half={r['second_half_rate']*100:5.1f}%  slope={r['slope']*100:+.2f}pts/wk  p={r['p_value']:.4f}"
        )

    print("\n" + "=" * 78)
    print(f"FALLING skills ({len(falling)}) -- statistically significant downward trend, p < {SIGNIFICANCE_THRESHOLD}")
    print("=" * 78)
    for r in falling:
        print(
            f"  {r['skill_name']:<20} first-half={r['first_half_rate']*100:5.1f}%  "
            f"second-half={r['second_half_rate']*100:5.1f}%  slope={r['slope']*100:+.2f}pts/wk  p={r['p_value']:.4f}"
        )

    print(f"\n{len(stable)} skills showed no statistically significant trend over this window.")
    print("\nDone.")


if __name__ == "__main__":
    main()
