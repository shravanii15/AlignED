# AlignED

[![Run Tests](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/run_tests.yml)
[![Daily Job Pull](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml/badge.svg)](https://github.com/shravanii15/AlignED/actions/workflows/fetch_adzuna.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Do graduate computing programs actually teach what the job market wants?**

🔗 **[Try the live dashboard](https://aligned-shravanikulkarni.streamlit.app)** *(update this link if your deployed URL is different)*

AlignED is an end-to-end data pipeline and analytics dashboard that compares real graduate program curricula against real job-market demand, using the official US Department of Labor (O\*NET) skills taxonomy as a shared, unbiased yardstick — and proves every claim with actual statistics, not guesses.

## The problem

Prospective grad students, career switchers, and even program directors rarely have a data-backed answer to "does this curriculum still match what employers actually want?" AlignED builds that answer from scratch: real scraped course catalogs, real job postings, a validated AI-vs-classical skill extraction comparison, and statistically significant gap scoring — all the way to a browsable dashboard and a personal skill-gap tool.

## Screenshots

*(Add 2-3 screenshots here — see the "Adding screenshots" note at the bottom of this README for exactly how.)*

## Key results

| Metric | Result |
|---|---|
| University programs analyzed | 13 (Georgia Tech, ASU, UIUC, Northeastern, BU, Wisconsin, UMD ×2, Penn State, UW, Michigan) |
| Real courses analyzed | 1,378 |
| Real job postings analyzed | 1,660+ sampled, ~124,000 historical + a live daily pipeline |
| AI vs. classical extraction (F1 score) | **0.400 (AI)** vs. 0.364 (keyword baseline) — validated on a 104-item hand-labeled test set |
| Statistically significant skill gaps found | 231, across all 13 programs |
| Skills with a real, tested demand trend | 67 tracked (7 rising, 2 falling, over the dataset's real-volume weeks) |
| Final ranked recommendations | 90, combining gap size + demand trend |

The consistent, cross-program finding: named, hands-on tools — **Python, Docker, Kubernetes, Linux, Git, Tableau** — show up as statistically significant gaps in almost every program studied, often by 10-40 percentage points.

## How it works

```
Scrape course catalogs (13 programs)  ─┐
                                        ├─► SQLite database ─► Skill extraction (AI + baseline,
Pull job postings (live + historical) ─┘                       validated against each other)
                                                                        │
                                                                        ▼
                                          Gap scoring (two-proportion z-test)
                                                        │
                                                        ▼
                                      Demand trend detection (linear regression)
                                                        │
                                                        ▼
                                    Ranked recommendations (gap + trend combined)
                                                        │
                                                        ▼
                                       Streamlit dashboard (9 interactive pages)
```

Every stage grounds its output in the real, official O\*NET skills taxonomy — nothing is an invented list.

## What's in the dashboard

- **Overview** — headline numbers and a one-paragraph summary of the whole pipeline
- **Build Your Profile** — paste your own skills/resume text and get a personalized analysis: which real job roles best match your background, your strengths and gaps for that role, real example job openings, and a downloadable personalized PDF career report
- **Program Explorer** — pick any of the 13 programs and see its ranked, color-coded, plain-English skill-gap recommendations, with Excel/PDF export
- **Course Finder** — search or filter real courses across all 13 programs by keyword or specific skill
- **Compare Programs** — see 2-3 programs' top gaps side by side
- **Skill Coverage Heatmap** — a visual grid of programs × skills, real coverage percentages
- **Skill Demand Trends** — which tracked skills are statistically rising or falling in demand
- **Role Clusters** — how real job postings group into real-world roles, with sample postings per cluster
- **Methodology & Honest Limitations** — every real trade-off and limitation stated openly, the kind of thing an interviewer would ask about directly

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
