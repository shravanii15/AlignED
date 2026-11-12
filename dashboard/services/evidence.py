"""services/evidence.py: loads the committed JSON evidence files (held-out evaluation, error analysis, ingestion health).
A missing or unreadable file returns None so the page shows a note instead of failing."""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELDOUT_RESULTS = os.path.join(BASE_DIR, "data", "heldout", "heldout_results.json")
ERROR_ANALYSIS = os.path.join(BASE_DIR, "data", "heldout", "error_analysis.json")
HEALTH_REPORT = os.path.join(BASE_DIR, "data", "health", "ingestion_report.json")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
