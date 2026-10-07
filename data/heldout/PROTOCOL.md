# Held-out evaluation protocol

**Why:** the 104-item development set was used while the extraction methods were built and tuned (for
example the 0.65 similarity threshold), so scores on it are optimistic. This set is a fresh sample,
labeled before the methods are run on it, and scored once with the settings frozen.

**Sample:** 30 course descriptions (spread across programs) and 20 job postings (spread across role
clusters), drawn with seed 2026 from the project database. Every item in the development set is excluded.
Postings of 400 to 6,000 characters are eligible, and text is capped at 3,000 characters, the same cap the
development set used.

**Labeling (AI-drafted, human-verified):** the first draft of the labels was written by Claude (an AI) on
2026-10-07 from the text alone, before any method's output existed. A human (the project author) then checks every
item, correcting column F and marking each row OK or FIXED; the importer's `--require-review` option refuses to
produce an answer key until all 50 rows are marked. Describe these labels as AI-drafted and human-verified, never as
fully hand-labeled. Names are matched to the same O*NET vocabulary the extractors use.
Names outside the vocabulary are reported and left out of scoring (neither method can predict them).

**Frozen before scoring:** extractor code, vocabulary, the 0.65 similarity threshold and the matching rules.
The evaluation stores SHA-256 hashes of the extractor files and of the labels in `heldout_results.json`.
If the code changes after labeling, the result must be re-run and the change disclosed.

**Scoring:** micro-averaged precision, recall and F1 (same as the development evaluation), plus a paired
bootstrap (5,000 resamples of items) giving 95% intervals for each F1 and for the LLM minus baseline difference.

**Rules:** the held-out set is scored once. No threshold, prompt or matching change may be made in response to
held-out results. If a change is made anyway, the old set is no longer held out and a new one must be drawn.

**Known limits:** one human verifier working from an AI draft (no agreement score, and a reviewer can anchor on a draft); 50 items give wide intervals; the vocabulary is
O*NET, so tools it does not list cannot be scored.

## Steps
1. `cd scripts/extraction && python build_heldout_set.py` (already done, creates the items and the sheet)
2. Check every row of `data/heldout/labeling_sheet.xlsx` (column F is the draft; type OK or FIXED in column G), save, close.
3. `python import_heldout_labels.py --require-review` (add `--accept-unmatched` to leave out names that are not in the vocabulary)
4. `python extract_baseline.py --items ../../data/heldout/heldout_items.json --out ../../data/heldout/baseline_predictions.json`
5. `python extract_llm.py --items ../../data/heldout/heldout_items.json --out ../../data/heldout/llm_predictions.json` (needs Ollama running)
6. `python evaluate_heldout.py`
