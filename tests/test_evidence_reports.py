"""Tests for the data-health report and the held-out error analysis that feed the Evidence pages."""

import json
import os
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
sys.path.insert(0, os.path.join(BASE, "scripts", "extraction"))

import health_report  # noqa: E402
import heldout_error_analysis as hea  # noqa: E402


def test_committed_health_report_is_consistent():
    rep = json.load(open(os.path.join(BASE, "data", "health", "ingestion_report.json")))
    assert rep["snapshots"] == len(rep["per_snapshot"])
    assert rep["fetched"] == sum(r["fetched"] for r in rep["per_snapshot"])
    assert rep["unique_valid"] == rep["per_snapshot"][-1]["unique_total"]
    for r in rep["per_snapshot"]:
        assert r["fetched"] == r["rejected"] + r["duplicate_ids"] + r["duplicate_content"] + r["new"]


def test_health_report_on_empty_directory(tmp_path):
    rep = health_report.build_report(str(tmp_path), now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert rep["snapshots"] == 0 and rep["fetched"] == 0 and rep["first_snapshot"] is None


def test_committed_error_analysis_matches_results():
    err = json.load(open(os.path.join(BASE, "data", "heldout", "error_analysis.json")))
    res = json.load(open(os.path.join(BASE, "data", "heldout", "heldout_results.json")))
    assert err["num_items"] == res["num_items"] == len(err["items"])
    for method in ("baseline", "llm"):
        tp = sum(s[method]["true_positives"] for s in err["per_source"].values())
        assert tp == res[method]["true_positives"]


def test_recall_by_kind_counts_each_kind():
    labels = [{"id": "A", "essential_skills_or_knowledge": [{"name": "Mathematics"}], "essential_technologies": [{"title": "Python"}]}]
    out = hea.recall_by_kind(labels, {"baseline": {"A": {"python"}}, "llm": {"A": set()}})
    assert out["named tool or technology"]["baseline"] == 1 and out["named tool or technology"]["llm"] == 0
    assert out["broad skill or knowledge area"]["gold_skills"] == 1
