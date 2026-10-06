"""Tests for generated PDF reports."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))

from services.reports_pdf import build_match_pdf_report  # noqa: E402


def test_match_pdf_is_a_valid_pdf():
    data = build_match_pdf_report(["Python", "Git"], [("Docker", 0.10), ("Kubernetes", 0.11)], 4)
    assert data.startswith(b"%PDF-") and len(data) > 1000


def test_match_pdf_handles_nothing_missing_and_unicode():
    data = build_match_pdf_report(["Python"], [], 1)
    assert data.startswith(b"%PDF-")
    data = build_match_pdf_report([], [("Café ☃ skill", 0.05)], 1)
    assert data.startswith(b"%PDF-")


def _sample_recs():
    import pandas as pd

    return pd.DataFrame([
        {"canonical_name": "Python", "market_demand_rate": 0.40, "program_coverage_rate": 0.0, "gap_value": 0.40,
         "trend_label": "no clear trend", "q_value": 0.0001, "p_value": 0.0001, "priority_tier": "high",
         "rationale": "Python appears in 40% of postings, but no course description names it."},
        {"canonical_name": "Docker", "market_demand_rate": 0.10, "program_coverage_rate": 0.004, "gap_value": 0.096,
         "trend_label": "rising", "q_value": 0.02, "p_value": 0.01, "priority_tier": "medium",
         "rationale": "Docker appears in 10% of postings."},
    ])


def test_skill_gap_pdf_builds_with_and_without_strengths():
    from services.reports_pdf import build_pdf_report

    recs = _sample_recs()
    assert build_pdf_report("Uni", "MS CS", 100, recs, "all jobs", 1660, 2).startswith(b"%PDF-")
    assert build_pdf_report("Uni", "MS CS", 100, recs, "all jobs", 1660, 2, strengths=[("C", 3)]).startswith(b"%PDF-")
    assert build_pdf_report("Uni", "MS CS", 100, recs.iloc[0:0], "all jobs", 1660, 0).startswith(b"%PDF-")


def test_excel_report_is_plain_language_and_keeps_numbers_numeric():
    import io

    from openpyxl import load_workbook
    from services.reports_excel import build_excel_report

    wb = load_workbook(io.BytesIO(build_excel_report("Uni", "MS CS", 100, _sample_recs())))
    assert wb.sheetnames == ["Skills to learn", "How to read this"]
    ws = wb["Skills to learn"]
    headers = [c.value for c in ws[6]]
    assert "How common in jobs" in headers and "q-value" not in " ".join(str(h) for h in headers)
    assert ws["C7"].value == 0.40 and isinstance(ws["D7"].value, (int, float))
