# AlignED: portfolio copy (edit freely)

Facts below come from the repo and the live app. Anything marked (confirm) needs your check first.

## One-line pitch

AlignED measures whether graduate computing programs teach what employers ask for: 13 programs, 1,378 courses and 1,660 job postings, with every skill gap statistically tested.

## Three bullets for the project card

- **Built:** an end-to-end analytics product: scraped course catalogs, a daily job-posting pipeline, a constrained SQLite model with dbt tests, a FastAPI service, and a Streamlit app, all in Docker with CI.
- **Found:** 170 statistically significant skill gaps after multiple-comparison correction. Python, Docker, Kubernetes and Linux are the most common gaps; Python is missing from 10 of 13 programs.
- **Decided on evidence:** an LLM extractor beat my keyword baseline on the data I tuned on, then lost on 50 unseen items (F1 0.198 vs 0.311). I shipped the simpler method and published the reversal.

## Résumé bullets

- Analyzed 1,378 course descriptions from 13 graduate programs against 1,660 job postings; identified 170 significant skill gaps using z-tests and Fisher's exact tests with Benjamini-Hochberg correction, and checked robustness with an employer-clustered bootstrap (all 170 intervals above zero).
- Evaluated an LLM skill extractor against a keyword baseline on a held-out set of 50 items; the LLM led on tuning data (F1 0.426 vs 0.364) but lost on unseen data (0.198 vs 0.311, 95% interval for the difference below zero), so I shipped the simpler method.
- Built a daily ingestion pipeline (Prefect, GitHub Actions) that validates and deduplicates a live job feed; found and corrected a 500-character truncation that made Python demand look like it collapsed from 40% to 7%.
- Designed a constrained SQLite schema (unique keys, CHECK constraints, indexes) with dbt tests and an atomic rebuild, plus a migration with tests that prove bad rows are rejected.
- Shipped a Streamlit app, FastAPI service and Docker images; added a bring-your-own-data tool that runs the same tested analysis on any course list.

## Role-tailored blurbs

**Data scientist / analyst.** I treated "which skills are missing" as a hypothesis-testing problem, not a ranking. Each gap is tested, corrected for running about 70 tests per program, and re-checked with an employer-clustered bootstrap. The headline went from 236 raw gaps to 170 honest ones, and demand "trends" went from 9 to 0.

**Data / analytics engineer.** A daily job validates and deduplicates a live feed by id and content hash, records every rejection, and rebuilds the database atomically only after validation. The schema enforces its own rules, and dbt tests check the result tables on every rebuild.

**ML engineer.** I held out 50 items before running either extractor and froze the code with hashes. The LLM lost, so I shipped the keyword method. Error analysis shows recall, not precision, is the limit: both methods miss most broad skill areas and tie on named tools.

**Product manager.** The app has three entry points by user need: check a job posting, see a program's gaps, or analyze your own courses. I traded a live feed for a fixed sample so published numbers do not drift, and listed the limits on the page instead of hiding them. The product brief proposes success metrics but claims no usage numbers.

**Forward-deployed engineer.** "Analyze Your Program" takes a CSV or pasted course list from a client, validates input with plain-language errors, and returns the same tested analysis in seconds, with nothing stored. A versioned API and Docker images expose it to other systems.

## "Challenges" section (pick two)

1. **My AI method looked better, but only on data I had tuned it on.** I tested both methods on 50 new items. The result flipped, so I switched methods and said so in the app.
2. **The job feed cut every posting to 500 characters.** My first comparison made Python look like it fell from 40% to 7%. I noticed it was too dramatic, found the cutoff, and re-measured my sample on the same 500 characters. The difference disappeared.
3. **Too many "gaps" were probably luck.** About 70 skills tested per program means some look real by chance. Correcting for it cut significant gaps from 236 to 170.

## Honest limits (keep these visible)

- Labels for the 50-item test are AI-drafted and human-verified, not independent. 50 items is small.
- A course description mentioning a skill is a proxy for coverage, not proof of how well it is taught.
- Some of the 1,378 courses come from department catalogs, not a single program's required list.
- The posting sample is category-balanced, not the whole labor market.

## LinkedIn post (draft)

> I spent the last few months asking a question I couldn't answer when choosing a grad program: does the curriculum teach what employers actually ask for?
>
> So I built AlignED. It compares 1,378 course descriptions from 13 graduate computing programs with 1,660 job postings, and tests every skill gap instead of just ranking them.
>
> A few things I'm proud of:
> - 170 gaps survived multiple-comparison correction (236 looked significant before it).
> - I tested my own method on 50 new items. The LLM I expected to win lost to a simple keyword baseline, so I shipped the simpler one and published the result.
> - A daily pipeline validates a live job feed. It also caught a bug that made Python demand look like it collapsed from 40% to 7%. It was a 500-character truncation in the feed.
> - You can paste any job posting, or upload your own course list, and get the same tested analysis.
>
> Live app and code are below. I'd love feedback, especially from people who hire for data roles.
>
> [live app link] · [GitHub link]
>
> #datascience #dataengineering #machinelearning #analytics

(Add a 30 to 60 second Loom or GIF as the first media item. Posts with a visible demo get far more clicks.)
