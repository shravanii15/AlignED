<p align="center"><img src="docs/banner.svg" alt="AlignED banner" width="100%"></p>

# AlignED

[![Run Tests](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml)
[![Adzuna raw pull (experimental)](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Do graduate computing programs teach what the job market asks for?**

AlignED compares 1,378 course descriptions from 13 graduate programs against 1,660 sampled job postings. Skills are mapped to the O\*NET taxonomy, and each gap is tested for statistical significance.

**[Live dashboard](https://aligned-shravanikulkarni.streamlit.app)**

## Screenshots

| Home | Skill Gaps |
|---|---|
| ![Home](docs/screenshots/home.png) | ![Skill Gaps](docs/screenshots/skill-gaps.png) |
| **Match a Job** | **Which Jobs Fit Me** |
| ![Match a Job](docs/screenshots/match-job.png) | ![Which Jobs Fit Me](docs/screenshots/fit-me.png) |

## Key results

| Metric | Result |
|---|---|
| Programs / courses | 13 programs, 1,378 courses |
| Job postings used for gap scoring | 1,660 (category-balanced sample) |
| Significant skill gaps | 170 across all programs, overall-market scope (two-proportion z-test, or Fisher's exact test for small counts, with Benjamini-Hochberg FDR correction) |
| Skill extraction benchmark | LLM F1 0.400 vs. keyword baseline 0.364, on 104 hand-labeled items |
| Skills with a confirmed demand trend | 0 of 67 after FDR correction (9 had raw p < 0.05) |

Python, Docker, Kubernetes, Linux, Git and Tableau show up as significant gaps in most programs, often by 10 to 40 percentage points.

## How it works

![Architecture diagram](docs/architecture.svg)

Scrape course catalogs, extract skills, normalize them to O\*NET, compare each program's coverage with market demand, test for significance, and rank recommendations. Results are stored in SQLite and served by a Streamlit dashboard.

## Dashboard

Built around two questions: "does this program teach what employers want?" and "what should I learn?"

- **Home:** two starting points, one for a job you found and one for choosing a program.
- **Match a Job:** paste a job posting and your skills to see what you have, what is missing, and what to learn first (ordered by how common each skill is across 1,660 postings), with a copyable summary.
- **Skill Gaps:** pick a program and a type of job. The top five missing skills appear as cards, each with a button to find courses that mention it and a collapsed "How we know" panel with the statistics. Excel and PDF downloads.
- **Which Jobs Fit Me:** paste your skills to see which job families fit you, what to learn next, and example postings, with a PDF.
- **Compare Programs:** top gaps for 2 to 3 programs side by side.
- **Explore the Data:** skills by program, rising and falling skills, job families from embedding-based clustering, and a course search.
- **Methodology:** how the numbers are produced, and their limits.

## Engineering

- pytest suite covering the statistical core (z-tests, FDR correction, trend classification) and recommendation logic, run on every push by GitHub Actions
- SQLite schema in `database/schema.sql` with enforced foreign keys and additive migrations
- `scripts/rebuild_all.py` recomputes the derived tables on a temporary copy, validates them, and swaps them in atomically; database resets clear dependent tables in foreign-key order instead of disabling constraints
- Evaluation fails closed: the extraction benchmark refuses to publish metrics unless predictions cover exactly the gold-set items
- Dashboard split into per-page modules with shared `services/` and `utils/`

**Stack:** Python, SQLite, Streamlit, Plotly, pandas, scipy, scikit-learn, sentence-transformers, Ollama, BeautifulSoup, GitHub Actions

## Run it

```bash
git clone https://github.com/shravanii15/AlignED.git
cd AlignED/dashboard
pip install -r requirements.txt
streamlit run app.py
```

Tests: `pip install -r requirements-test.txt`, then `python -m pytest tests/`.

## Reproducing the database

The committed `database/aligned.db` is a snapshot. What can be reproduced depends on the inputs:

- **From the repository alone:** `python scripts/rebuild_all.py` recomputes the derived tables (gap scores and recommendations) from the raw tables in the snapshot. It works on a temporary copy, runs `scripts/validate_database.py` (foreign keys, duplicates, gap and recommendation invariants, tier and trend consistency), and replaces the real database only if every check passes.
- **From raw sources:** `python scripts/rebuild_all.py --full` runs every stage in order and checks each stage's inputs first. Committed inputs: the scraped course catalogs (`data/sample_*_courses.json`), the O\*NET vocabulary (`data/taxonomy/`) and the 1,660-posting clustering sample (`data/clustering/`). Not committed, because of size or credentials: the 530 MB Kaggle postings CSV (`scripts/fetch_kaggle_backfill.py`, needs Kaggle credentials), the O\*NET and Adzuna API keys (copy `.env.example` to `.env`), and a local Ollama model for the LLM benchmark. The scraping and API scripts under `scripts/` regenerate the committed inputs if you want to start from the web.

Stage order: `setup_database.py`, `gap_analysis/build_lookup_tables.py`, `extract_course_skills.py`, `extract_posting_skills.py`, `extract_posting_trends.py`, `compute_skill_trends.py`, `compute_gap_scores.py`, `generate_recommendations.py`. `setup_database.py` builds a new database file and swaps it in only when complete.

The 170 gaps in the results table are the overall-market scope. The database holds 1,040 gap rows in total, because each program is also compared against each job family separately.

## Limitations

- **Coverage is a text signal.** "Covered" means a skill name appears in a course description, not that it is taught in depth. "Demand" means it appears in the sampled postings.
- **The posting sample is category-balanced**, not proportional to the real labor market, so demand figures describe this sample only.
- **Corpus sizes differ by program** (course counts range widely), which affects coverage rates.
- **The 0.400 vs. 0.364 benchmark is an internal comparison** on the same 104 items used during development, not a held-out evaluation. The faster keyword method is used at full scale. The LLM's raw answers were matched to the taxonomy by embedding similarity, which can confuse near neighbors (SQL with MySQL, for example). The matching step now tries exact, alias and spelling-variant matches first and blocks known confusions; the benchmark numbers above predate that change and will be re-run.
- **The database is a historical snapshot.** The Adzuna workflow is an experimental raw pull that writes `data/sample_adzuna_pull.json`. It does not change any dashboard number; gap scores and trends come from the Kaggle historical postings in the committed database.
- **Trend detection** uses about 124,000 historical postings, restricted to the weeks with enough volume (68% were dated to a single week by a collection artifact).

More detail is on the dashboard's Methodology page.

## Repository layout

```
scripts/      collection, extraction, gap analysis
dashboard/    Streamlit app
database/     schema and committed SQLite snapshot
data/gold_set/ 104-item hand-labeled evaluation set
tests/        pytest suite
```

## Author

Shravani Kulkarni, MS Data Science
