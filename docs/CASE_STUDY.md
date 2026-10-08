# AlignED: case study

*Curriculum x labor-market analysis for graduate computing programs.*
[Live app](https://aligned-shravanikulkarni.streamlit.app) · [Code](https://github.com/shravanii15/AlignED)

## The problem

Graduate programs and job descriptions change at different speeds, and "industry-ready" is usually
claimed rather than measured. I wanted to measure where the two diverge.

## The question

Do graduate computing curricula mention the skills that appear in sampled job postings, and which differences
are strong enough to take seriously?

## What I built

- A pipeline that collects 1,378 course descriptions (13 programs) and 1,660 job postings, maps skills to the
  O\*NET taxonomy, and stores everything in SQLite.
- A statistical layer: two-proportion tests (Fisher's exact test for small counts) with Benjamini-Hochberg
  correction, producing 170 significant gaps and evidence-ranked recommendations.
- A Streamlit app to explore gaps by program and job type, compare programs, and match a job posting or resume
  to missing skills.
- Engineering around it: validated daily ingestion, Prefect orchestration, dbt tests, a FastAPI service,
  Docker, CI and 251 automated tests.

## What surprised me

**The AI method lost.** On the 104 items I used while building, a local LLM beat a keyword baseline (F1 0.426
vs 0.364). I then labeled 50 fresh items before running either method and scored once with settings frozen.
The order reversed: keyword 0.311, LLM 0.198, and the 95% interval for the difference excluded zero. The
pipeline uses the keyword method, and the app says so.

**Correction removed most of the excitement.** Testing about 70 skills per program produced 236 apparent gaps;
170 survived false-discovery correction. For demand trends it was starker: 9 of 67 looked significant, 0 held up.

**A data limit nearly fooled me.** Newer job postings come with only the first 500 characters of each
description. Compared naively with the full-text sample, Python appeared to fall from 40% to 7% of postings.
Measured on the same 500 characters, the difference vanished.

## What I learned

- A result that looks better on the data you tuned on is not evidence. Hold out data before you look.
- Statistical significance is not practical importance, and many tests at once need correction.
- Text mentions are a proxy for coverage, not teaching quality. The corpora are not equivalent (see
  [DATA_PROVENANCE.md](DATA_PROVENANCE.md)), and I report that instead of hiding it.
- Keeping published numbers fixed while still showing fresh data (a separate weekly "market pulse") avoids
  silent changes to results.

## Limits I state openly

Category-balanced posting sample; mixed corpus types; O\*NET has no entry for subjects like machine learning
(recall is low for both methods); held-out labels were checked by one person; trends are exploratory.

## Stack

Python, SQLite, Streamlit, Plotly, scipy, pandas, Prefect, dbt (DuckDB), FastAPI, Docker, GitHub Actions, pytest.
