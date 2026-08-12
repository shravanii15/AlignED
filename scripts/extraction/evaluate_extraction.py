"""
evaluate_extraction.py

What this script does, in plain terms:
This is the script that actually answers the question this whole phase of
the project exists to answer: "is the AI extractor (extract_llm.py) any
better than a plain keyword scanner (extract_baseline.py)?" It's the
single most important deliverable here -- "I built an AI extractor" is a
weak claim on its own, but "I built one and proved, on a hand-labeled
gold set of 104 real course/job postings, that it beats a classical
baseline by X points of F1" is a strong one. This script produces that X.

How "correctness" is judged:
For each of the 104 gold-set items, data/gold_set/gold_set_labeled_onet.json
holds a human's judgment of the true relevant terms, split into three
buckets: essential_skills_or_knowledge, essential_technologies, and
optional. We treat the union of all three as "the true set" for that item
-- i.e. we do NOT penalize a method for finding an "optional" skill just
because it wasn't "essential," and we don't reward it more for essential
vs. optional either. That's a deliberate simplification: the gold labels
distinguish importance, but neither extractor in this project is asked to
predict importance, only "is this relevant at all" -- so holding them to
a finer-grained standard than what we asked them to produce wouldn't be a
fair test.

The metrics: precision, recall, F1 -- and why "micro-averaged":
For each item we compare its predicted term set against its true term set
(case-insensitive) and count:
  - true positives  (TP): predicted AND actually true
  - false positives (FP): predicted but NOT actually true
  - false negatives (FN): actually true but NOT predicted
We then have a choice about how to roll 104 items' worth of TP/FP/FN
counts into one overall score:
  - "Macro-average": compute precision/recall separately for each item,
    then average those 104 per-item scores.
  - "Micro-average": pool every TP/FP/FN from every item into one giant
    bucket first, then compute precision/recall once from the totals.
We use MICRO-averaging here, and it's not just a coin flip -- it's the
more standard and defensible choice for this kind of task, for two
concrete reasons: (1) items with very few true skills (e.g. a one-line
course blurb with just 2 true skills) would otherwise get the same vote
as items with a dozen true skills, even though getting 1 term right or
wrong on a tiny item swings that item's score wildly (e.g. 0% vs 50%) in
a way that has little to do with real extractor quality; micro-averaging
naturally weights every individual TERM-level decision equally instead of
every ITEM equally. (2) it's the standard choice in the information
extraction / NER literature this task most resembles.

Output:
- A console table comparing baseline vs. LLM side by side.
- The same numbers saved as JSON to
  data/gold_set/evaluation_results.json, so a later write-up/report can
  quote these figures without re-running everything.
"""

import json
import os

from extract_common import normalize_term

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gold_set")
GOLD_LABELS_PATH = os.path.join(DATA_DIR, "gold_set_labeled_onet.json")
BASELINE_PREDICTIONS_PATH = os.path.join(DATA_DIR, "baseline_extractions.json")
LLM_PREDICTIONS_PATH = os.path.join(DATA_DIR, "llm_extractions.json")
RESULTS_PATH = os.path.join(DATA_DIR, "evaluation_results.json")


def load_true_sets(gold_labels):
    """Build {item_id: set_of_normalized_true_terms} from the hand-labeled
    gold file, by flattening essential_skills_or_knowledge +
    essential_technologies + optional into one set per item (see the
    module docstring for why we don't keep the essential/optional split
    for scoring purposes)."""
    true_sets = {}
    for item in gold_labels:
        terms = set()
        for entry in item.get("essential_skills_or_knowledge", []):
            terms.add(normalize_term(entry["name"]))
        for entry in item.get("essential_technologies", []):
            terms.add(normalize_term(entry["title"]))
        for entry in item.get("optional", []):
            terms.add(normalize_term(entry["name_or_title"]))
        true_sets[item["id"]] = terms
    return true_sets


def load_predicted_sets(predictions):
    """Build {item_id: set_of_normalized_predicted_terms} from either
    extractor's output file (both extract_baseline.py and extract_llm.py
    save the same {"id", "predicted_skills": [{"term", "type"}]} shape,
    which is exactly what makes them comparable in the first place)."""
    predicted_sets = {}
    for item in predictions:
        terms = {normalize_term(p["term"]) for p in item.get("predicted_skills", [])}
        predicted_sets[item["id"]] = terms
    return predicted_sets


def compute_micro_metrics(true_sets, predicted_sets):
    """Pool true-positive/false-positive/false-negative counts across
    every item first (see module docstring for why micro- rather than
    macro-averaging), then compute one overall precision/recall/F1 from
    the totals. Returns both the aggregate metrics and the raw counts,
    since the raw counts are useful context in the printed report."""
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for item_id, true_terms in true_sets.items():
        predicted_terms = predicted_sets.get(item_id, set())
        total_tp += len(predicted_terms & true_terms)
        total_fp += len(predicted_terms - true_terms)
        total_fn += len(true_terms - predicted_terms)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return {
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def print_comparison_table(baseline_metrics, llm_metrics):
    """Print a clean, readable side-by-side comparison to the console."""
    header = f"{'Metric':<18}{'Baseline':>15}{'LLM':>15}{'LLM - Baseline':>18}"
    print("\n" + "=" * len(header))
    print("EXTRACTION METHOD COMPARISON (micro-averaged over 104 gold-set items)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    rows = [
        ("Precision", "precision"),
        ("Recall", "recall"),
        ("F1 score", "f1"),
    ]
    for label, key in rows:
        b = baseline_metrics[key]
        l = llm_metrics[key]
        diff = l - b
        sign = "+" if diff >= 0 else ""
        print(f"{label:<18}{b:>15.3f}{l:>15.3f}{sign}{diff:>17.3f}")

    print("-" * len(header))
    for label, key in [
        ("True positives", "true_positives"),
        ("False positives", "false_positives"),
        ("False negatives", "false_negatives"),
    ]:
        print(f"{label:<18}{baseline_metrics[key]:>15}{llm_metrics[key]:>15}")
    print("=" * len(header))


def main():
    print(f"Loading gold-standard labels from: {GOLD_LABELS_PATH}")
    with open(GOLD_LABELS_PATH, "r", encoding="utf-8") as f:
        gold_labels = json.load(f)
    true_sets = load_true_sets(gold_labels)
    print(f"  -> {len(true_sets)} labeled items loaded.")

    print(f"Loading baseline predictions from: {BASELINE_PREDICTIONS_PATH}")
    with open(BASELINE_PREDICTIONS_PATH, "r", encoding="utf-8") as f:
        baseline_predictions = json.load(f)
    baseline_sets = load_predicted_sets(baseline_predictions)

    print(f"Loading LLM predictions from: {LLM_PREDICTIONS_PATH}")
    with open(LLM_PREDICTIONS_PATH, "r", encoding="utf-8") as f:
        llm_predictions = json.load(f)
    llm_sets = load_predicted_sets(llm_predictions)

    # Sanity check: warn (don't crash) if either predictions file doesn't
    # cover every gold-set item -- this can legitimately happen if
    # extract_llm.py was stopped partway through a long local-inference
    # run, and the user deserves to know her comparison might be
    # incomplete rather than getting a silently skewed number.
    for name, predicted_sets in [("baseline", baseline_sets), ("LLM", llm_sets)]:
        missing = set(true_sets.keys()) - set(predicted_sets.keys())
        if missing:
            print(
                f"  !! WARNING: {name} predictions are missing "
                f"{len(missing)} item(s) present in the gold set: "
                f"{sorted(missing)}"
            )

    baseline_metrics = compute_micro_metrics(true_sets, baseline_sets)
    llm_metrics = compute_micro_metrics(true_sets, llm_sets)

    print_comparison_table(baseline_metrics, llm_metrics)

    results = {
        "num_gold_items": len(true_sets),
        "baseline": baseline_metrics,
        "llm": llm_metrics,
        "f1_improvement_llm_minus_baseline": llm_metrics["f1"] - baseline_metrics["f1"],
    }
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved evaluation summary to: {RESULTS_PATH}")
    print("\nDone.")


if __name__ == "__main__":
    main()
