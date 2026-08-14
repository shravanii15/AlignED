"""
conftest.py

What this file does, in plain terms:
The scripts under scripts/gap_analysis/ and scripts/extraction/ aren't
set up as an installable Python package (no setup.py/__init__.py) --
they're meant to be run directly, e.g. `python compute_gap_scores.py`.
For tests to be able to `import compute_gap_scores` and call its pure
functions directly, both folders need to be on Python's import path.
pytest automatically loads this file before running any tests, so this
is the one place that needs to happen, rather than repeating the same
sys.path setup at the top of every test file.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../AlignED
sys.path.insert(0, os.path.join(BASE_DIR, "scripts", "gap_analysis"))
sys.path.insert(0, os.path.join(BASE_DIR, "scripts", "extraction"))
