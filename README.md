# AlignED

**Do graduate computing programs actually teach what the job market wants?**

AlignED is an end-to-end data pipeline and analytics dashboard that compares real graduate program curricula against real job-market demand, using the official US Department of Labor (O\*NET) skills taxonomy as a shared, unbiased yardstick — and proves every claim with actual statistics, not guesses.

## The problem

Prospective grad students, career switchers, and even program directors rarely have a data-backed answer to "does this curriculum still match what employers actually want?" AlignED builds that answer from scratch: real scraped course catalogs, real job postings, a validated AI-vs-classical skill extraction comparison, and statistically significant gap scoring — all the way to a browsable dashboard.

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
                                       Streamlit dashboard (5 interactive pages)
```

Every stage grounds its output in the real, official O\*NET skills taxonomy — nothing is an invented list.

## Tech stack

- **Data collection:** Python, BeautifulSoup, Requests, GitHub Actions (daily automated pipeline)
- **AI/ML:** Ollama (local LLM), sentence-transformers (embeddings), scikit-learn (k-means clustering), scipy (statistical significance testing)
- **Data:** SQLite, O\*NET Web Services API, Adzuna API, Kaggle historical dataset
- **Dashboard:** Streamlit, Plotly, openpyxl, fpdf2

## Try it yourself

```bash
git clone https://github.com/shravanii15/AlignED.git
cd AlignED/dashboard
pip install -r requirements.txt
streamlit run app.py
```

*(A live public link will be added here once published — see the dashboard's own README for deployment steps.)*

## Repository structure

```
scripts/
  fetch_university_courses.py, fetch_onet_taxonomy.py, ...   Data collection
  extraction/                                                 AI vs. baseline skill extraction + evaluation
  gap_analysis/                                               Gap scoring, trend detection, recommender
dashboard/                                                    Streamlit app (the browsable front-end)
database/                                                     SQLite schema + the live database
data/gold_set/                                                104-item hand-labeled evaluation set
```

## Honest limitations

This project documents its own trade-offs and limitations openly, rather than hiding them — including a caught data-quality bug (68% of historical postings were dated in a single week due to a data-collection artifact) and a deliberate speed-vs-accuracy trade-off (using the faster, validated-but-slightly-less-accurate keyword method at full scale instead of the slower AI method). Full details are in the dashboard's **Methodology & Limitations** page.

## Author

Shravani Kulkarni — MS Data Science
