"""
evaluate_heldout.py: score both extraction methods on the held-out set, with confidence intervals.

    python evaluate_heldout.py

Needs data/heldout/heldout_labeled.json plus baseline_predictions.json and llm_predictions.json (produced
by running the two extractors with --items data/heldout/heldout_items.json). It refuses to run if either
prediction file is incomplete, exactly like the development-set evaluation.

Beyond the single F1 number it reports a 95% bootstrap confidence interval for each method and for the
DIFFERENCE between them. The items are resampled with replacement 5,000 times; the same resample is
applied to both methods (a paired bootstrap), so item difficulty cancels out. If the interval for the
difference includes zero, the data cannot tell the two methods apart.
"""

import json
import os
import random
import sys

from evaluate_extraction import compute_micro_metrics, load_predicted_sets, load_true_sets, validate_predictions
from heldout import HELDOUT_DIR, file_sha256

BOOTSTRAP_ROUNDS = 5000
SEED = 7
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
FROZEN_FILES = ["extract_baseline.py", "extract_llm.py", "extract_common.py", "renormalize.py"]


def bootstrap(true_sets, baseline_sets, llm_sets, rounds=BOOTSTRAP_ROUNDS, seed=SEED):
    """Paired bootstrap over items. Returns percentile 95% intervals for each F1 and for LLM minus baseline."""
    ids = sorted(true_sets)
    rng = random.Random(seed)
    base, llm, diff = [], [], []
    for _ in range(rounds):
        sample = [rng.choice(ids) for _ in ids]
        # items can repeat in a resample, so give every draw its own key
        t = {i: true_sets[k] for i, k in enumerate(sample)}
        b = {i: baseline_sets.get(k, set()) for i, k in enumerate(sample)}
        m = {i: llm_sets.get(k, set()) for i, k in enumerate(sample)}
        fb, fl = compute_micro_metrics(t, b)["f1"], compute_micro_metrics(t, m)["f1"]
        base.append(fb)
        llm.append(fl)
        diff.append(fl - fb)

    def interval(values):
        values = sorted(values)
        return [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]
    return {"baseline_f1_ci95": interval(base), "llm_f1_ci95": interval(llm), "difference_ci95": interval(diff)}


def verdict(diff_ci):
    lo, hi = diff_ci
    if lo > 0:
        return "LLM better than keyword baseline (95% interval for the difference is above zero)"
    if hi < 0:
        return "Keyword baseline better than LLM (95% interval for the difference is below zero)"
    return "No reliable difference (95% interval for the difference includes zero)"


def main():
    with open(os.path.join(HELDOUT_DIR, "heldout_labeled.json"), encoding="utf-8") as f:
        labels = json.load(f)
    with open(os.path.join(HELDOUT_DIR, "baseline_predictions.json"), encoding="utf-8") as f:
        baseline = json.load(f)
    with open(os.path.join(HELDOUT_DIR, "llm_predictions.json"), encoding="utf-8") as f:
        llm = json.load(f)
    true_sets = load_true_sets(labels)
    validate_predictions("baseline", true_sets.keys(), baseline)
    validate_predictions("LLM", true_sets.keys(), llm)
    b_sets, l_sets = load_predicted_sets(baseline), load_predicted_sets(llm)

    b_metrics, l_metrics = compute_micro_metrics(true_sets, b_sets), compute_micro_metrics(true_sets, l_sets)
    cis = bootstrap(true_sets, b_sets, l_sets)
    dev_path = os.path.join(os.path.dirname(HELDOUT_DIR), "gold_set", "evaluation_results.json")
    dev = json.load(open(dev_path, encoding="utf-8")) if os.path.exists(dev_path) else None

    print(f"\nHELD-OUT EVALUATION ({len(true_sets)} items, micro-averaged)")
    print(f"{'':<12}{'Precision':>11}{'Recall':>9}{'F1':>8}   95% interval for F1")
    for name, m, ci in (("Baseline", b_metrics, cis["baseline_f1_ci95"]), ("LLM", l_metrics, cis["llm_f1_ci95"])):
        print(f"{name:<12}{m['precision']:>11.3f}{m['recall']:>9.3f}{m['f1']:>8.3f}   [{ci[0]:.3f}, {ci[1]:.3f}]")
    d = l_metrics["f1"] - b_metrics["f1"]
    print(f"\nLLM minus baseline F1: {d:+.3f}   95% interval [{cis['difference_ci95'][0]:+.3f}, {cis['difference_ci95'][1]:+.3f}]")
    print(verdict(cis["difference_ci95"]))
    if dev:
        print(f"\nDevelopment set for comparison: baseline F1 {dev['baseline']['f1']:.3f}, LLM F1 {dev['llm']['f1']:.3f} "
              f"(difference {dev['f1_improvement_llm_minus_baseline']:+.3f})")

    results = {"num_items": len(true_sets), "baseline": b_metrics, "llm": l_metrics, "f1_difference_llm_minus_baseline": d,
               "bootstrap_rounds": BOOTSTRAP_ROUNDS, **cis, "verdict": verdict(cis["difference_ci95"]),
               "development_set": dev,
               "frozen_code_sha256": {f: file_sha256(os.path.join(SCRIPTS, f)) for f in FROZEN_FILES},
               "labels_sha256": file_sha256(os.path.join(HELDOUT_DIR, "heldout_labeled.json"))}
    with open(os.path.join(HELDOUT_DIR, "heldout_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {os.path.join(HELDOUT_DIR, 'heldout_results.json')}")


if __name__ == "__main__":
    sys.exit(main())
