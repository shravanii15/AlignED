# Evaluation report

How AlignED's results were checked, what held up, and what did not. All figures come from committed code
and data; the commands to regenerate them are given for each section.

## 1. Skill extraction: development set versus held-out set

| Set | Items | Keyword baseline F1 | LLM + embeddings F1 | Winner |
|---|---|---|---|---|
| Development (used while building) | 104 | 0.364 | 0.426 | LLM |
| Held-out (fresh, labeled before either method ran) | 50 | **0.311** (95% interval 0.234 to 0.377) | 0.198 (0.125 to 0.270) | **Keyword** |

The 95% interval for the difference (LLM minus keyword) is -0.177 to -0.046, which excludes zero. The
development result is optimistic because the similarity cutoff was tuned on those items. The pipeline uses the
keyword method.

- Protocol, label provenance and frozen code hashes: `data/heldout/PROTOCOL.md`, `data/heldout/heldout_results.json`.
- Labels for the 50 items are AI-drafted and checked by one human, not independently double-annotated.
- Both methods have low recall (about 0.2 and 0.1) because the O*NET vocabulary has no entry for subjects such as
  machine learning.
- Regenerate: `python scripts/extraction/evaluate_heldout.py`.

## 2. Gap significance: is the posting side independent?

The main tests treat every posting as independent, and they run **Benjamini-Hochberg separately for each
program and scope** (about 70 skills per family), not across all published gaps together. Postings from the same
employer are not independent (Capital One is 64 of the 1,660). `scripts/gap_analysis/robustness_check.py` runs
two **sensitivity analyses**. Neither replaces the published test, and the first is an approximation.

**(a) Design-effect adjustment (approximate).** For each skill, the design effect is the company-clustered
variance of the mention rate divided by the variance under independence. The posting side is replaced by its
effective size (counts divided by the design effect, rounded) and the original test (z-test, or Fisher's exact test
for small counts) is rerun, followed by the same Benjamini-Hochberg correction within each program. Intervals are
Newcombe hybrid-Wilson on the effective counts. Because the counts are rounded and the test is not a direct
cluster-robust test, treat these as approximate.

**(b) Company-cluster bootstrap (independent check).** Companies are resampled with all their postings (2,000
rounds); the course side is redrawn as Binomial(n_courses, observed coverage). The 2.5th and 97.5th percentiles of
(demand - coverage) give a 95% interval per gap. These intervals are per-gap and not adjusted for multiple
testing, so they are consistent with, but not stronger than, the corrected result in (a).

| Quantity | Value |
|---|---|
| Postings / distinct companies | 1,660 / 1,011 (largest company 3.9%) |
| Median design effect | 1.37 (Python 3.25) |
| Published significant gaps | 170 |
| Still significant after (a), corrected | **166** |
| Dropped by (a) | 4 (Chef 1.5 pts and NumPy 1.5 pts at Georgia Tech CS, LinkedIn 3.8 pts at Washington, Node.js 2.3 pts at Michigan) |
| Newly significant by (a) | 0 |
| Gaps whose bootstrap 95% interval is above zero (b) | 170 of 170 |

Reading: the headline result is robust to employer clustering; only small gaps near the threshold are fragile.
Per-gap intervals are in `data/robustness/cluster_robust_gaps.json`. For example, Python at Georgia Tech
Analytics is a 40-point gap with a design-effect interval of about 29 to 44 points.

What this does not address:
- **Courses are not independent** within a program (shared curriculum design). The course side is treated as the
  program's own offerings (a finite population), not a random sample, so the results describe these programs'
  published course lists and do not generalize to other programs.
- The posting sample is category-balanced, not market-proportional, so demand rates describe the sample
  (see `docs/DATA_PROVENANCE.md`).
- A "significant gap" means a significant difference in how often a skill is mentioned, not a curriculum deficiency.

Regenerate: `python scripts/gap_analysis/robustness_check.py`.

## 2b. Held-out set: leakage check

The held-out builder excludes development items by a fingerprint of the first 200 normalized characters, which
would miss a near-duplicate with a different opening. As an additional check, every held-out item was compared
with every development item by 8-word-shingle overlap (`heldout.dev_overlaps`): the largest overlap was 14.8%
(boilerplate-level), and none reached the 30% screening threshold. A test keeps this true
(`tests/test_audit_fixes.py`).

## 2c. Every quoted number is regenerated

`python scripts/verify_claims.py` recomputes 15 headline numbers (programs, courses, postings, skills, gaps,
recommendations, Fisher-tested gaps, trend counts, held-out F1 scores, the 166/170 result) from the database and
saved result files and exits with an error if any quoted value no longer matches. The count of passing tests
comes from pytest and the CI badge, not from this script.

## 3. Trends

67 skills were tested for demand trends; 9 looked significant on a raw p-value and 0 survived
Benjamini-Hochberg correction, so the page presents them as early hints.

## 4. Known limitations still open

- No skill-depth measure: a mention in a course description is not evidence of how deeply it is taught.
- No market-weighted demand estimate; only a category-balanced one.
- Held-out set is small (50 items) and single-verified.
- A larger skill vocabulary would raise recall for both extraction methods.
