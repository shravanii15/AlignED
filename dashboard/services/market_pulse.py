"""services/market_pulse.py: loads the weekly market-pulse file written by scripts/market_pulse.py.

The file is small JSON committed to the repository, so the deployed app updates when it changes.
A missing or unreadable file returns None and the page simply hides the section."""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PULSE_PATH = os.path.join(BASE_DIR, "data", "market_pulse", "latest.json")


def load_market_pulse(path=PULSE_PATH):
    try:
        with open(path, encoding="utf-8") as f:
            pulse = json.load(f)
        if not isinstance(pulse.get("skills"), list) or "refreshed_at" not in pulse:
            return None
        return pulse
    except (OSError, ValueError):
        return None


def refreshed_date(pulse):
    """'2026-10-08' from the refresh timestamp, or None."""
    return str(pulse["refreshed_at"])[:10] if pulse else None
