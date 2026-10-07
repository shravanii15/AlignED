"""scripts/ingest/adzuna_client.py: fetch job postings from the Adzuna API.

Retries transient failures (timeouts, HTTP 429 and 5xx) with exponential
backoff, and gives up with a clear error rather than returning partial data
silently. The HTTP session and the sleep function are injectable so the retry
logic is tested without network access or real waiting.
"""

import json
import os
import time
from datetime import date

import requests

API_URL = "https://api.adzuna.com/v1/api/jobs/us/search/{page}"
DEFAULT_QUERIES = ["data scientist", "data engineer", "machine learning engineer", "data analyst", "software engineer"]
RESULTS_PER_PAGE = 50
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 1.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    """Raised when the API cannot be reached after all retries."""


def _get_with_retry(session, url, params, sleep, attempts=MAX_ATTEMPTS):
    last = None
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last = exc
        else:
            if response.status_code in RETRYABLE_STATUS:
                last = FetchError(f"HTTP {response.status_code}")
            elif response.status_code >= 400:
                raise FetchError(f"HTTP {response.status_code} (not retried)")
            else:
                return response.json()
        if attempt < attempts - 1:
            sleep(BACKOFF_SECONDS * (2 ** attempt))
    raise FetchError(f"gave up after {attempts} attempts: {last}")


def fetch_jobs(app_id, app_key, queries=None, pages=1, per_page=RESULTS_PER_PAGE, session=None, sleep=time.sleep, pause=0.5):
    """Return a de-duplicated list of raw Adzuna results across all queries."""
    session = session or requests.Session()
    seen, jobs = set(), []
    for query in queries or DEFAULT_QUERIES:
        for page in range(1, pages + 1):
            data = _get_with_retry(
                session,
                API_URL.format(page=page),
                {"app_id": app_id, "app_key": app_key, "what": query, "results_per_page": per_page, "content-type": "application/json"},
                sleep,
            )
            for job in data.get("results", []):
                if job.get("id") not in seen:
                    seen.add(job.get("id"))
                    jobs.append(job)
            sleep(pause)  # stay polite to the API
    return jobs


def save_snapshot(jobs, directory, today=None):
    """Write the untouched raw response to data/raw/adzuna/YYYY-MM-DD.json.

    Raw snapshots are never edited: the database can always be rebuilt from
    them, and a bug in validation never loses source data."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{(today or date.today()).isoformat()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=1)
    return path
