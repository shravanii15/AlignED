"""
fetch_adzuna_jobs.py

What this script does, in plain terms:
It asks Adzuna (a job search website) for a handful of real, current
"data scientist" job postings, prints them so we can see they're real,
and saves them to a file so later steps in the pipeline can use them.

This is the first real, working piece of AlignED.
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load the secret keys from the .env file sitting next to this project.
# We NEVER type the actual keys directly into this file - that's the
# whole point of keeping them in .env instead.
load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Safety check: stop with a clear message if the keys didn't load,
# instead of failing with a confusing error later.
if not APP_ID or not APP_KEY:
    raise SystemExit("Missing Adzuna credentials. Check your .env file.")

# This is the web address Adzuna's search feature lives at.
# "us" means we're searching the US job market specifically.
URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"

params = {
    "app_id": APP_ID,
    "app_key": APP_KEY,
    "what": "data scientist",
    "results_per_page": 5,
    "content-type": "application/json",
}

print("Asking Adzuna for 5 real 'data scientist' job postings...")
response = requests.get(URL, params=params, timeout=30)
response.raise_for_status()  # stop immediately if something went wrong

data = response.json()
jobs = data.get("results", [])

print(f"Success! Got {len(jobs)} job postings.\n")

for job in jobs:
    title = job.get("title", "Unknown title")
    company = job.get("company", {}).get("display_name", "Unknown company")
    location = job.get("location", {}).get("display_name", "Unknown location")
    print(f"- {title} at {company} ({location})")

# Save the full, raw results to the data/ folder so later scripts
# (the ones that extract skills from this text) can read them.
# On a fresh checkout (like GitHub Actions), the data/ folder doesn't
# exist yet - Git doesn't track empty folders - so we create it here
# if needed, instead of assuming it's already there.
data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(data_dir, exist_ok=True)
output_path = os.path.join(data_dir, "sample_adzuna_pull.json")
with open(output_path, "w") as f:
    json.dump(jobs, f, indent=2)

print(f"\nSaved full results to: {output_path}")
