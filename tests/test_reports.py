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
