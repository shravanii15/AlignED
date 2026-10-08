# Data provenance and comparability

Where every number in AlignED comes from, what each source can and cannot support, and where the
sources are not equivalent. Read this before quoting a figure.

## Datasets

| Dataset | Source | Used for | Size | Caveat |
|---|---|---|---|---|
| University courses | Public course catalogs of 10 universities (scraped, `scripts/fetch_university_courses.py`) | Curriculum coverage | 13 corpora, 1,378 courses | Corpora are not equivalent (see below). Descriptions are public catalog text, not syllabi. |
| Historical job postings | Kaggle LinkedIn postings dataset (about 124,000 rows) | All gap scores, recommendations and trends | 1,660 sampled postings | Category-balanced across tech role families, not proportional to the real labor market. 68% of the full dataset is dated to one final week, so trends use only the 6 weeks with at least 100 postings. |
| Recent job postings | Adzuna API, collected daily | Weekly "Latest Market Pulse" comparison only | Grows daily (592 de-duplicated at first refresh) | Stored and displayed separately. Never part of a gap score. The API returns only the first 500 characters of each description. |
| Skill taxonomy | U.S. Department of Labor O\*NET | Normalizing skill names | 1,597 terms (57 skills/knowledge areas, the rest named technologies) | A vocabulary of named things. It has no entry for subjects such as "machine learning", so both extraction methods under-detect those. |
| Skill-extraction labels | 104-item development set; 50-item held-out set | Method comparison | 154 items | Held-out labels are AI-drafted and checked by one human, not independently double-annotated. |

## Corpus comparability (the 13 "programs")

The 13 course corpora were collected from public catalogs and are **not the same kind of thing**.
Some are a program's actual course list, some are a whole department catalog, some are an elective
pool, and one is a small sample. A gap measured against a broad catalog says "this catalog does not
mention the skill", which is different from "this degree does not teach it".

| Program | Courses | Kind of corpus |
|---|---|---|
| Georgia Tech MS Analytics (OMS) | 34 | Program course list |
| Georgia Tech MS Cybersecurity (OMS) | 13 | Program course list |
| Georgia Tech MS Computer Science | 295 | Department catalog (close to the full public list) |
| Arizona State Online MCS | 5 | Small sample (flagged in the app) |
| UIUC MS CS / MCS-DS | 161 | Department catalog |
| Northeastern MS CS | 184 | Department catalog |
| Boston University MS CS | 39 | Graduate course list |
| Wisconsin-Madison MS CS / Data Science | 138 | Elective pool |
| Maryland MS CS (CMSC) | 95 | Department catalog |
| Maryland Cybersecurity (ENPM) | 58 | Department catalog |
| Penn State World Campus MS Data Analytics | 19 | Program course list |
| University of Washington MSCS / MS Data Science | 134 | Department catalog |
| Michigan MS CSE | 203 | Department catalog |

Corpus kinds are inferred from how each source was collected and named. They are descriptive labels,
not an official statement from the universities. The Skill Gaps page flags programs with fewer than 30
courses, because a small corpus can miss skills a larger one would catch. Statistical tests use
Fisher's exact test when counts are small, but that protects against small-sample error, not against a
corpus that measures something different.

## What each measurement means

- **Coverage** is the share of a program's course descriptions that mention a skill. It is a text-mention
  proxy, not instructional depth or a student outcome.
- **Demand** is the share of sampled postings that mention a skill. It is demand within a balanced sample,
  not the labor market.
- **A gap** is demand minus coverage, kept only when the difference survives a significance test with
  Benjamini-Hochberg false-discovery correction. It marks something worth investigating, not proof that a
  program should change.
- **Market Pulse** compares recent postings with the fixed sample on the same 500-character window. It does
  not change gaps, recommendations or trends.

## Reproducibility

The database snapshot is committed. `python scripts/rebuild_all.py` recomputes the derived tables from it
and validates them before replacing anything. Raw daily Adzuna snapshots are committed under
`data/raw/adzuna/`. The Kaggle CSV (530 MB) is not committed; see the README for what can be rebuilt
from the repository alone.
