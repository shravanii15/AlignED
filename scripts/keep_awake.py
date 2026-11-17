"""
keep_awake.py: open the live app in a real (headless) browser so Streamlit Community Cloud counts it as a visit.

A plain HTTP request does not count (the app only wakes and stays awake when a browser opens its websocket), so this
uses Playwright. If the app is asleep it clicks the "get this app back up" button and waits for the page to load.

    python scripts/keep_awake.py [url]

Exit code 0 means the app rendered; 1 means it did not within the time limit, so the workflow shows a red run.
"""

import re
import sys
import time

APP_URL = "https://aligned-shravanikulkarni.streamlit.app/"
READY_TEXT = "Where does graduate education diverge"
WAKE_BUTTON_TEXT = "get this app back up"
TIMEOUT_SECONDS = 240


def _frames_text(page):
    """Visible text of the page and of every iframe in it. Streamlit Community Cloud serves the app inside an iframe,
    so the main document's text alone never contains the app."""
    out = []
    for frame in page.frames:
        try:
            out.append((frame, frame.inner_text("body")))
        except Exception:  # a frame can navigate or detach while we read it
            continue
    return out


def visit(url=APP_URL, timeout=TIMEOUT_SECONDS):
    from playwright.sync_api import sync_playwright

    deadline = time.time() + timeout
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        while time.time() < deadline:
            for frame, text in _frames_text(page):
                if READY_TEXT in text:
                    browser.close()
                    return True
                if WAKE_BUTTON_TEXT in text.lower():
                    try:
                        frame.get_by_role("button", name=re.compile(WAKE_BUTTON_TEXT, re.IGNORECASE)).click(timeout=5_000)
                    except Exception:
                        pass
            time.sleep(5)
        page.screenshot(path="keep_awake_failure.png")
        for _, text in _frames_text(page):
            print("--- visible text at timeout ---")
            print(text[:500])
        browser.close()
    return False


def main(argv=None):
    url = (argv or sys.argv[1:] or [APP_URL])[0]
    ok = visit(url)
    print("App is awake." if ok else "App did not load in time.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
