# AlignED

[![Run Tests](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml)
[![Daily Job Pull](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Do graduate computing programs actually teach what the job market wants?**

🔗 **[Try the live dashboard](https://aligned-shravanikulkarni.streamlit.app)** *(update this link if your deployed URL is different)*

AlignED is an end-to-end data pipeline and analytics dashboard that compares real graduate program course descriptions against demand observed in a sampled set of real job postings, using the official US Department of Labor (O\*NET) skills taxonomy as a common, external vocabulary — and backs every claim with actual statistical testing, not guesses.

## Screenshots

*(Add 2-3 screenshots here — see the "Adding screenshots" note at the bottom of this README for exactly how.)*

## Key results

| Metric | Result |
|---|---|
| University programs analyzed | 13 (Georgia Tech, ASU, UIUC, Northeastern, BU, Wisconsin, UMD ×2, Penn State, UW, Michigan) |
| Real courses analyzed | 1,378 |
| Real job postings analyzed (gap scoring) | 1,660, sampled from the historical dataset |
| Historical postings used for demand-trend detection | ~124,000 (see "A note on the data" below for how this differs from the 1,660 sample) |
| AI vs. classical extraction (F1 score) | **0.400 (AI)** vs. 0.364 (keyword baseline) — benchmarked on a 104-item hand-labeled test set (internal comparison, not held-out validation — see Methodology) |
| Statistically significant skill gaps found | 159, across all 13 programs (after Benjamini-Hochberg FDR correction for running ~70 tests per program — see Methodology) |
| Skills with a statistically confirmed demand trend | 0 of 67 tracked, after Benjamini-Hochberg FDR correction across all 67 simultaneous tests (9 looked significant on a raw p-value alone -- see "A note on trend significance" below) |
| Evidence-ranked recommendations | 69 (overall-market scope), 722 total across all program/role-scope combinations |

The consistent, cross-program finding: named, hands-on tools — **Python, Docker, Kubernetes, Linux, Git, Tableau** — show up as statistically significant gaps in almost every program studied, often by 10-40 percentage points.

## The problem

Prospective grad students, career switchers, and even program directors rarely have a data-backed answer to "does this curriculum still match what employers actually want?" AlignED builds an evidence-based answer to that: real scraped course descriptions, a sampled set of real job postings, a benchmarked AI-vs-classical skill extraction comparison, and statistically significant gap scoring — all the way to a browsable dashboard and a personal skill-gap tool.

**A note on what "gap" means:** "Program coverage" means a skill's name appears in a course description — not that it's taught in depth or assessed. "Market demand" means a skill appears in this project's sampled job postings — not that every employer requires it. Every gap score is a text-coverage signal, not a certified measurement of learning outcomes or labor-market truth. Full reasoning is on the dashboard's Methodology page.

## How it works

![AlignED architecture diagram](docs/architecture.svg)

Every stage grounds its output in the real, official O\*NET skills taxonomy — nothing is an invented list.

## What's in the dashboard

The sidebar is grouped into 3 workflows instead of one flat list, so it's clear where to start:

- **Overview** — headline numbers and a one-paragraph summary of the whole pipeline
- **Analyze**
  - **Program Explorer** — pick any of the 13 programs *and* a target role (or "Overall market"), and see ranked, color-coded, plain-English skill-gap recommendations computed specifically for that combination, with Excel/PDF export
  - **Compare Programs** — see 2-3 programs' top overall-market gaps side by side
- **Explore**
  - **Skill Coverage Heatmap** — a visual grid of programs × skills, real coverage percentages
  - **Skill Demand Trends** — which tracked skills are statistically rising or falling in demand
  - **Role Groups** — how real job postings group into broad role families (embedding-based, silhouette score disclosed honestly), with sample postings per group
  - **Course Finder** — search or filter real courses across all 13 programs by keyword or specific skill
- **Personalize**
  - **Build Your Profile** — paste your own skills/resume text and get a personalized analysis: which real job roles best match your background (shown as "X of N core skills covered," not an unvalidated match %), your strengths and gaps for that role, real example job openings, and a downloadable personalized PDF career report
- **Methodology & Honest Limitations** — every real trade-off and limitation stated openly, the kind of thing an interviewer would ask about directly

## Engineering quality

This isn't just a notebook with a chart at the end — it's built and checked the way a small production data product would be:

- **Automated tests** — a real pytest suite (`tests/`) covers the statistical core (two-proportion z-tests, FDR correction, trend classification) and the recommendation text generator, not just "does it run without crashing." Runs on every push via GitHub Actions (see badge at the top).
- **CI on every push** — the `Run Tests` workflow re-runs the full suite automatically; the `Daily Job Pull` workflow re-runs the Adzuna ingestion daily and fails loudly if the API breaks.
- **Structured, migrated schema** — `database/schema.sql` is the single source of truth for every table, with foreign keys enforced (not just implied) and additive migrations (`ALTER TABLE ... ADD COLUMN`) used instead of silently reshaping tables.
- **Reproducible pipeline** — the entire database can be rebuilt from scratch by rerunning the scripts in `scripts/` in order (scrape → extract → score → recommend); nothing is hand-edited or one-off.
- **Modular dashboard code** — `dashboard/app.py` delegates to per-page modules under `sections/`, with shared logic (queries, layout, nav state) factored into `services/` and `utils/` rather than duplicated across pages.
- **Honest validation, not just a working demo** — the AI skill-extraction method was benchmarked against a classical keyword baseline on a 104-item hand-labeled gold set before being chosen for full-scale use (see Key results above and the Methodology page).

## Tech stack

- **Data collection:** Python, BeautifulSoup, Requests, GitHub Actions (daily automated pipeline)
- **AI/ML:** Ollama (local LLM), sentence-transformers (embeddings), scikit-learn (k-means clustering), scipy (statistical significance testing)
- **Data:** SQLite, O\*NET Web Services API, Adzuna API, Kaggle historical dataset
- **Dashboard:** Streamlit, Plotly, openpyxl, fpdf2
- **Testing:** pytest, with a GitHub Actions workflow running the suite on every push (see badge above)

## Try it yourself

**Live version:** [aligned-shravanikulkarni.streamlit.app](https://aligned-shravanikulkarni.streamlit.app) — no setup needed.

**Run it locally:**
```bash
git clone https://github.com/shravanii15/AlignED.git
cd AlignED/dashboard
pip install -r requirements.txt
streamlit run app.py
```

**Run the full data pipeline yourself** (optional — the committed database already has real, complete data, so this is only needed to regenerate it from scratch):
```bash
pip install -r requirements.txt   # repo-root requirements, for the pipeline scripts
python -m pytest tests/           # run the test suite
```
Then run the scripts under `scripts/` in order: scraping → `setup_database.py` → extraction → gap scoring → trends → recommendations. Each script's own docstring explains what it does and why.

## A note on the data

The committed `database/aligned.db` is a **frozen snapshot**, not a live-updating database — it reflects whatever the pipeline scripts produced the last time they were run and the file was recommitted. The one exception is `data/sample_adzuna_pull.json`, which genuinely does update daily via the GitHub Action shown in the badge above. Rerunning the full pipeline (see above) will regenerate the database with fresh data at any time.

There are four distinct things called "job posting data" in this project, and it's worth being precise about which is which:

- **1,660 sampled postings** — the fixed sample actually used for gap scoring (program coverage vs. market demand, the two-proportion z-tests). This is what every gap score and recommendation on the dashboard is based on. **It's a category-balanced sample** (deliberately drawn across a fixed set of tech role categories — software engineering, data science, cybersecurity, DevOps, etc. — for role-clustering purposes), not a random draw proportional to the real labor market. So "demand" throughout this project means demand *within this sampled set*, not necessarily the true relative demand across the whole job market.
- **~124,000 historical postings** — a larger backfill (Kaggle) used only for demand-trend detection (Skill Demand Trends page), and even then restricted to the 6 weeks with meaningful volume — see Methodology for why.
- **Live daily Adzuna pipeline** — a small number of real postings pulled in automatically every day via GitHub Actions. This keeps growing the raw `postings` table (currently a handful beyond the 1,660 sample), but it is **not** yet re-integrated into gap scoring or trend detection — the analysis you see on the dashboard is not recalculated from today's job market in real time.
- **The committed database snapshot** — the frozen file described above, which is what the deployed dashboard actually reads from.

In short: the numbers on this dashboard reflect a specific, dated sample — not a continuously live labor market — and that's stated here on purpose rather than left ambiguous.

## A note on trend significance

Gap scoring on this dashboard applies a Benjamini-Hochberg false discovery rate (FDR) correction across every skill tested for a program, because testing ~70 skills at once means a few "significant" results are expected purely from chance. The Skill Demand Trends page now applies that exact same correction to its own ~67 simultaneous trend tests — and the honest result is that **0 tracked skills currently show a statistically confirmed rising or falling trend once that correction is applied**, even though 9 looked significant using a raw p-value alone. The trends page still shows the strongest directional signals, clearly labeled as exploratory rather than confirmed, with both the raw p-value and the FDR-corrected q-value visible for every skill. This is a real, checked result, not a placeholder — earlier versions of this project applied FDR correction to gap scoring but not to trend detection, which meant the two pages were quietly using different, inconsistent standards for "significant." They now use the same one.

## Repository structure

```
scripts/
  fetch_university_courses.py, fetch_onet_taxonomy.py, ...   Data collection
  extraction/                                                 AI vs. baseline skill extraction + evaluation
  gap_analysis/                                               Gap scoring, trend detection, recommender
dashboard/                                                    Streamlit app (the browsable front-end)
database/                                                     SQLite schema + the committed database snapshot
data/gold_set/                                                104-item hand-labeled evaluation set
tests/                                                         pytest suite covering the statistical core
```

## Testing

The statistical and matching logic that everything else depends on — the two-proportion z-test used for gap scoring, trend classification, recommendation text generation, and the keyword-matching engine — has a real pytest suite (`tests/`), run automatically on every push via GitHub Actions (see the badge at the top). Run it yourself with:
```bash
python -m pytest tests/ -v
```

## Honest limitations

This project documents its own trade-offs and limitations openly, rather than hiding them — including a caught data-quality bug (68% of historical postings were dated in a single week due to a data-collection artifact) and a deliberate speed-vs-accuracy trade-off (using the faster, validated-but-slightly-less-accurate keyword method at full scale instead of the slower AI method). Full details are in the dashboard's **Methodology & Limitations** page.

## Adding screenshots

To finish the "Screenshots" section above: take 2-3 screenshots of the live dashboard (Overview, Build Your Profile results, and Program Explorer are good choices), save them into a new `docs/screenshots/` folder in this repo, then replace the placeholder line with something like:
```markdown
![Overview page](docs/screenshots/overview.png)
![Build Your Profile results](docs/screenshots/profile.png)
```

## Author

Shravani Kulkarni — MS Data Science
