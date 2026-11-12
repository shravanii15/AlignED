"""
heldout_error_analysis.py: where do the two extraction methods go wrong on the held-out set?

    python scripts/extraction/heldout_error_analysis.py     # writes data/heldout/error_analysis.json

Uses exactly the same matching and metric functions as evaluate_heldout.py, then breaks the result down:
  - per source type (courses vs postings): micro precision, recall and F1 for each method,
  - per item: the gold skills, and each method's true positives, false positives and misses,
  - the most frequent false positives and misses per method (error themes).
The dashboard's Model Evaluation page reads this file.
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluate_extraction import compute_micro_metrics, normalize_term, load_predicted_sets, load_true_sets  # noqa: E402
from heldout import HELDOUT_DIR  # noqa: E402

OUT_PATH = os.path.join(HELDOUT_DIR, "error_analysis.json")
SNIPPET_CHARS = 700
TOP_ERRORS = 8


def _load(name):
    with open(os.path.join(HELDOUT_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def recall_by_kind(labels, preds):
    """Share of gold skills each method found, split by what kind of skill it is: a named tool or technology
    (Python, Docker) versus a broad O*NET skill or knowledge area (Mathematics, Computers and Electronics)."""
    gold_kind = {}
    for item in labels:
        for e in item.get("essential_skills_or_knowledge", []):
            gold_kind[(item["id"], normalize_term(e["name"]))] = "broad skill or knowledge area"
        for e in item.get("essential_technologies", []):
            gold_kind[(item["id"], normalize_term(e["title"]))] = "named tool or technology"
    out = {}
    for kind in sorted(set(gold_kind.values())):
        keys = [k for k, v in gold_kind.items() if v == kind]
        out[kind] = {"gold_skills": len(keys), **{m: sum(1 for (i, t) in keys if t in sets.get(i, set())) for m, sets in preds.items()}}
    return out


def analyse(items, labels, baseline, llm):
    true_sets = load_true_sets(labels)
    preds = {"baseline": load_predicted_sets(baseline), "llm": load_predicted_sets(llm)}
    by_id = {i["id"]: i for i in items}
    per_item, source_of = [], {}
    for item_id in sorted(true_sets):
        src = by_id[item_id]["source_type"]
        source_of[item_id] = src
        row = {"id": item_id, "source_type": src, "title": by_id[item_id]["title"], "context": by_id[item_id]["context"],
               "text": by_id[item_id]["text"][:SNIPPET_CHARS], "gold": sorted(true_sets[item_id])}
        for method, sets in preds.items():
            p = sets.get(item_id, set())
            row[method] = {"true_positives": sorted(p & true_sets[item_id]), "false_positives": sorted(p - true_sets[item_id]),
                           "misses": sorted(true_sets[item_id] - p)}
        per_item.append(row)

    per_source = {}
    for src in sorted(set(source_of.values())):
        ids = [i for i, s in source_of.items() if s == src]
        t = {i: true_sets[i] for i in ids}
        per_source[src] = {"items": len(ids), **{m: compute_micro_metrics(t, {i: sets.get(i, set()) for i in ids}) for m, sets in preds.items()}}

    themes = {}
    for method in preds:
        fp, fn = Counter(), Counter()
        for row in per_item:
            fp.update(row[method]["false_positives"])
            fn.update(row[method]["misses"])
        themes[method] = {"most_common_false_positives": fp.most_common(TOP_ERRORS), "most_common_misses": fn.most_common(TOP_ERRORS)}
    return {"num_items": len(per_item), "per_source": per_source, "recall_by_kind": recall_by_kind(labels, preds), "themes": themes, "items": per_item}


def main(argv=None):
    result = analyse(_load("heldout_items.json"), _load("heldout_labeled.json"), _load("baseline_predictions.json"), _load("llm_predictions.json"))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    for src, m in result["per_source"].items():
        print(f"{src:8} items={m['items']:>3}  baseline P/R/F1 {m['baseline']['precision']:.2f}/{m['baseline']['recall']:.2f}/{m['baseline']['f1']:.2f}"
              f"   LLM {m['llm']['precision']:.2f}/{m['llm']['recall']:.2f}/{m['llm']['f1']:.2f}")
    for kind, v in result["recall_by_kind"].items():
        print(f"{kind:32} gold={v['gold_skills']:>3}  baseline found {v['baseline']}  LLM found {v['llm']}")
    print(f"Saved {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
