# AlignED

[![Run Tests](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml)
[![Daily Job Pull](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Do graduate computing programs teach what the job market asks for?**

AlignED compares 1,378 course descriptions from 13 graduate programs against 1,660 sampled job postings. Skills are mapped to the O\*NET taxonomy, and each gap is tested for statistical significance.

**[Live dashboard](https://aligned-shravanikulkarni.streamlit.app)**

## Screenshots

<!-- screenshots go here -->

## Key results

| Metric | Result |
|---|---|
| Programs / courses | 13 programs, 1,378 courses |
| Job postings used for gap scoring | 1,660 (category-balanced sample) |
| Significant skill gaps | 159 across all programs (two-proportion z-tests, Benjamini-Hochberg FDR correction) |
| Skill extraction benchmark | LLM F1 0.400 vs. keyword baseline 0.364, on 104 hand-labeled items |
| Skills with a confirmed demand trend | 0 of 67 after FDR correction (9 had raw p < 0.05) |

Python, Docker, Kubernetes, Linux, Git and Tableau show up as significant gaps in most programs, often by 10 to 40 percentage points.

## How it works

![Architecture diagram](docs/architecture.svg)

Scrape course catalogs, extract skills, normalize them to O\*NET, compare each program's coverage with market demand, test for significance, and rank recommendations. Results are stored in SQLite and served by a Streamlit dashboard.

## Dashboard

- **Program Explorer:** pick a program and a target role, get ranked skill gaps with statistical evidence, and export to Excel or PDF.
- **Compare Programs:** top gaps for 2 to 3 programs side by side.
- **Market Intelligence:** skill coverage heatmap, demand trends, role groups from embedding-based clustering, and a course search.
- **Build Your Profile:** paste your skills or resume text to see which roles fit and what to learn next.
- **Methodology:** how the numbers are produced, and their limits.

## Engineering

- pytest suite covering the statistical core (z-tests, FDR correction, trend classification) and recommendation logic, run on every push by GitHub Actions
- SQLite schema in `database/schema.sql` with enforced foreign keys and additive migrations
- Pipeline can be rebuilt end to end from `scripts/` (scrape, extract, score, recommend)
- Dashboard split into per-page modules with shared `services/` and `utils/`

**Stack:** Python, SQLite, Streamlit, Plotly, pandas, scipy, scikit-learn, sentence-transformers, Ollama, BeautifulSoup, GitHub Actions

## Run it

```bash
git clone https://github.com/shravanii15/AlignED.git
cd AlignED/dashboard
pip install -r requirements.txt
streamlit run app.py
```

To run the tests: `pip install -r requirements.txt` at the repo root, then `python -m pytest tests/`. To rebuild the database, run the scripts under `scripts/` in order (each has a docstring explaining its step). Copy `.env.example` to `.env` for API keys.

## Limitations

- **Coverage is a text signal.** "Covered" means a skill name appears in a course description, not that it is taught in depth. "Demand" means it appears in the sampled postings.
- **The posting sample is category-balanced**, not proportional to the real labor market, so demand figures describe this sample only.
- **Corpus sizes differ by program** (course counts range widely), which affects coverage rates.
- **The 0.400 vs. 0.364 benchmark is an internal comparison** on the same 104 items used during development, not a held-out evaluation. The faster keyword method is used at full scale.
- **The database is a snapshot.** The daily Adzuna pull adds raw postings, but gap scoring and trends are not recomputed from them yet.
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
