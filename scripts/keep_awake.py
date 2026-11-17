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


def visit(url=APP_URL, timeout=TIMEOUT_SECONDS):
    from playwright.sync_api import sync_playwright

    deadline = time.time() + timeout
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        while time.time() < deadline:
            body = page.inner_text("body")
            if READY_TEXT in body:
                browser.close()
                return True
            if WAKE_BUTTON_TEXT in body.lower():
                page.get_by_role("button", name=re.compile(WAKE_BUTTON_TEXT, re.IGNORECASE)).click()
            time.sleep(5)
        browser.close()
    return False


def main(argv=None):
    url = (argv or sys.argv[1:] or [APP_URL])[0]
    ok = visit(url)
    print("App is awake." if ok else "App did not load in time.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
