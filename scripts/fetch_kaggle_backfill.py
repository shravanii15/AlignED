"""
fetch_kaggle_backfill.py

What this script does, in plain terms:
Our live job-posting pipeline (fetch_adzuna_jobs.py) only pulls a handful
of fresh postings each day -- that's realistic for a live, scheduled
pipeline, but it means we don't have much historical depth to look at
trends over time. This script downloads a big, already-collected dataset
of real LinkedIn job postings from 2023-2024 (published on Kaggle by
user "arshkon") to give the project real historical depth without
needing months of live scraping.

This is a one-time (or occasional) download, not something that needs to
run daily like the Adzuna script.
"""

import os
import shutil

from dotenv import load_dotenv

load_dotenv()

# kagglehub reads this environment variable to authenticate, so we set it
# here from our .env file rather than typing the token into this file.
kaggle_token = os.getenv("KAGGLE_API_TOKEN")
if not kaggle_token:
    raise SystemExit("Missing KAGGLE_API_TOKEN. Check your .env file.")
os.environ["KAGGLE_API_TOKEN"] = kaggle_token

import kagglehub  # noqa: E402  (import after setting the token on purpose)

DATASET = "arshkon/linkedin-job-postings"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "kaggle_backfill")

print(f"Downloading dataset: {DATASET}")
print("This is a large dataset, so it may take a few minutes the first time.")

download_path = kagglehub.dataset_download(DATASET)
print(f"Downloaded to a temporary cache folder: {download_path}")

# Copy the CSV files out of kagglehub's cache folder and into our own
# project's data folder, so everything AlignED uses lives in one place.
# This dataset ships extra CSVs (skills, companies, salaries) inside
# subfolders like "jobs/" and "mappings/", not just the main postings.csv
# at the top level -- we walk every subfolder so we don't miss them, and
# keep each file's subfolder name as a prefix so nothing overwrites
# another file that happens to share a name.
os.makedirs(DATA_DIR, exist_ok=True)
copied = []
for root, _dirs, files in os.walk(download_path):
    for filename in files:
        if not filename.lower().endswith(".csv"):
            continue
        rel_folder = os.path.relpath(root, download_path)
        if rel_folder == ".":
            dst_filename = filename
        else:
            dst_filename = f"{rel_folder.replace(os.sep, '_')}_{filename}"
        src = os.path.join(root, filename)
        dst = os.path.join(DATA_DIR, dst_filename)
        shutil.copy2(src, dst)
        copied.append(dst_filename)

print(f"\nCopied {len(copied)} CSV file(s) into: {DATA_DIR}")
for filename in copied:
    size_mb = os.path.getsize(os.path.join(DATA_DIR, filename)) / (1024 * 1024)
    print(f"  - {filename} ({size_mb:.1f} MB)")

print("\nDone. These files are excluded from Git (see .gitignore) since")
print("they're large and easy to re-download -- only the code that fetches")
print("them is tracked.")
