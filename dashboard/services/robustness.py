"""services/robustness.py: loads the company-clustered sensitivity results written by
scripts/gap_analysis/robustness_check.py (data/robustness/cluster_robust_gaps.json). Missing file -> None."""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(BASE_DIR, "data", "robustness", "cluster_robust_gaps.json")


def load_robustness(path=PATH):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if "summary" in data and "gaps" in data else None
    except (OSError, ValueError):
        return None


def gap_interval(data, program_id, skill_id):
    """(low, high) 95% interval for one published gap, as fractions, or None."""
    if not data:
        return None
    for g in data["gaps"]:
        if g["program_id"] == program_id and g["skill_id"] == skill_id:
            return g["gap_ci_low"], g["gap_ci_high"]
    return None
