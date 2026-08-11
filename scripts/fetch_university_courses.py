"""
fetch_university_courses.py

What this script does, in plain terms:
It visits university course catalog pages that follow a specific pattern
("Course Name (CODE 1234)" in bold, followed by a description) and pulls
out each course's code, name, and description automatically.

This version handles multiple programs that share this same pattern,
one after another, instead of needing a separate script per program.
"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

# Programs that use this same "bold heading + description" pattern.
# To add another one later, just add a new entry here.
PROGRAMS = [
    {
        "name": "Georgia Tech - MS Analytics (OMS Analytics)",
        "url": "https://pe.gatech.edu/degrees/analytics/curriculum",
        "output_file": "sample_gatech_analytics_courses.json",
    },
    {
        "name": "Georgia Tech - MS Cybersecurity (OMS Cybersecurity)",
        "url": "https://pe.gatech.edu/degrees/cybersecurity/curriculum",
        "output_file": "sample_gatech_cybersecurity_courses.json",
    },
]

course_pattern = re.compile(r"^(.*?)\s*\(([A-Z]{2,4}\s?\d{4})\)\s*$")
headers = {"User-Agent": "Mozilla/5.0 (AlignED research project; educational use)"}
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def scrape_program(name, url):
    """Fetch one program's page and pull out its courses. Returns a list."""
    print(f"Fetching: {name}")
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        text = bold_tag.get_text(strip=True)
        match = course_pattern.match(text)
        if not match:
            continue

        course_name = match.group(1).strip()
        course_code = match.group(2).strip()

        next_node = bold_tag.find_next(string=True)
        description = next_node.strip() if next_node else ""

        # Keep the longest description if a course code appears more than once
        # (this is the duplicate-listing issue we found and fixed earlier).
        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


if __name__ == "__main__":
    for program in PROGRAMS:
        courses = scrape_program(program["name"], program["url"])
        print(f"  -> Found {len(courses)} unique courses.")

        output_path = os.path.join(DATA_DIR, program["output_file"])
        with open(output_path, "w") as f:
            json.dump(courses, f, indent=2)
        print(f"  -> Saved to: {output_path}\n")

    print("Done with all programs.")
