"""
fetch_university_courses.py

What this script does, in plain terms:
It visits university course catalog pages and pulls out each course's code,
name, and description automatically. Different universities format their
catalog pages differently (some use a bold heading followed by a paragraph,
some use a bold heading followed by a bullet point, some don't use bold text
at all and just rely on plain text lines), so this script has a handful of
different "parser" functions -- one per distinct page pattern. Each program
in the PROGRAMS list below says which parser function to use for it.

This script is meant to be run on your own computer (not inside an
automated sandbox), because some sandboxes block outgoing web requests.
"""

import json
import os
import re
import requests
from bs4 import BeautifulSoup

headers = {"User-Agent": "Mozilla/5.0 (AlignED research project; educational use)"}
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _get_soup(url):
    """Download a page and hand back a BeautifulSoup object for it."""
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _clean_title(text):
    """Strip common trailing credit-hour phrases off the end of a course
    title, e.g. "Machine Learning." -> "Machine Learning", or
    "Advanced Database Systems credit: 4 Hours." -> "Advanced Database
    Systems". Different catalogs word this differently, so we try a few
    patterns."""
    cleaned = text.strip()
    cleaned = re.sub(r"credit:\s*.+$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\(\d+(?:-\d+)?\s*(?:to\s*\d+\s*)?Credits?\)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\(\d+(?:-\d+)?\s*Hours?\)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    # Georgia Tech's main catalog writes credit hours without parentheses,
    # e.g. "Introduction to Computing. 3 Credit Hours." -- strip that too.
    cleaned = re.sub(r"\.\s*\d+(?:-\d+)?\s*Credit Hours?\.?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.rstrip(".").strip()
    return cleaned


def _save_courses(seen, program_name, output_file):
    courses = list(seen.values())
    print(f"  -> Found {len(courses)} unique courses.")
    output_path = os.path.join(DATA_DIR, output_file)
    with open(output_path, "w") as f:
        json.dump(courses, f, indent=2)
    print(f"  -> Saved to: {output_path}\n")


# ---------------------------------------------------------------------------
# Parser 1: Georgia Tech pattern (existing, do not change its behavior)
# ---------------------------------------------------------------------------

course_pattern = re.compile(r"^(.*?)\s*\(([A-Z]{2,4}\s?\d{4})\)\s*$")


def scrape_program(name, url):
    """Handles Georgia Tech's OMS catalog pages.
    Pattern: a <strong>/<b> tag reading "Course Name (CODE 1234)" immediately
    followed by a text description.

    BUG FIX (found during Week 2 gold-set prep): Georgia Tech's page
    actually lists every course 3 times in slightly different HTML layouts
    (a short list, then two fuller sections). The original version of this
    function used `bold_tag.find_next(string=True)`, which grabs the very
    next text node in the document -- fragile against that repetition, and
    it was quietly grabbing the heading text itself back as the
    "description" instead of the real paragraph (e.g. "Deep Learning
    (CS 7643)" instead of the actual multi-sentence description). Fixed by
    reading the whole containing paragraph's text and stripping the
    heading off the front, the same more robust technique used by the
    newer parsers below -- and by keeping the LONGEST version found across
    all three repeated listings, since "keep the longest description"
    logic was already here but had nothing good to compare against
    before."""
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

        # GT's page groups multiple courses inside one shared paragraph, so
        # grabbing the whole paragraph's text (like the first version of
        # this fix did) bleeds into the next course(s)' text too. Instead,
        # walk forward node by node and stop the moment we reach another
        # bold heading -- that's the real boundary of this course's own
        # description, wherever it happens to sit in the page structure.
        description_parts = []
        for node in bold_tag.find_all_next(string=True):
            parent_bold = node.find_parent(["strong", "b"])
            if parent_bold is not None and parent_bold is not bold_tag:
                break
            node_text = node.strip()
            if node_text and node_text != text:
                description_parts.append(node_text)
        description = " ".join(description_parts).strip(" -–:")

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 2: ASU pattern
# "CSE 230: Title" in bold, immediately followed by a single bullet point
# (<li>) that holds the whole description.
# Confidence: HIGH -- verified directly via web_fetch; the bold heading and
# following "- description" bullet were clearly visible in the fetched page.
# ---------------------------------------------------------------------------

asu_heading_pattern = re.compile(r"^([A-Z]{2,4}\s?\d{3,4}):\s*(.+)$")


def scrape_asu_bullet_program(name, url):
    """Handles ASU Online's degree-program pages.
    Pattern: a bold heading like "CSE 230: Computer Organization and
    Assembly Language Programming" followed by one bullet-list item
    containing the course description. ASU only lists a handful of
    representative courses per program, so a small course count here is
    expected and not a bug."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        text = bold_tag.get_text(strip=True)
        match = asu_heading_pattern.match(text)
        if not match:
            continue

        course_code = match.group(1).strip()
        course_name = match.group(2).strip()

        description_tag = bold_tag.find_next("li")
        description = description_tag.get_text(" ", strip=True) if description_tag else ""

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 3: "CourseLeaf-style" catalog pattern
# Shared by: UIUC, Northeastern, University of Maryland (CMSC and ENPM),
# and UT Austin. All of these run on the same family of catalog software
# ("CourseLeaf"), which renders each course as a bold heading paragraph
# followed by a separate description paragraph, sometimes followed by extra
# metadata paragraphs (Prerequisite(s), Corequisite(s), Cross-listed with,
# Restriction, Formerly, Credit Only Granted for, Recommended Preparation)
# that we want to skip over rather than treat as the description.
#
# Confidence:
#   - UIUC: HIGH (verified directly; heading text "CS 100 Computer Science
#     Orientation credit: 1 Hour." followed by a plain description paragraph).
#   - Northeastern: HIGH (verified directly; heading text like
#     "CS 1800. Discrete Structures. (4 Hours)" followed by description,
#     then optional "Prerequisite(s):"/"Corequisite(s):" paragraphs).
#   - UMD (CMSC and ENPM): HIGH (verified directly for CMSC; heading text
#     like "CMSC401 Algorithms for Geospatial Computing (3 Credits)" followed
#     by description, then optional Prerequisite/Cross-listed with/Credit
#     Only Granted for/Restriction/Formerly paragraphs. ENPM was not fetched
#     directly since it's the same catalog site/software as CMSC, but the
#     pattern should be identical -- MEDIUM confidence for ENPM specifically).
#   - UT Austin: MEDIUM/LOW -- the live fetch of this page only returned the
#     catalog's navigation sidebar, not the actual course listing content
#     (the course text likely loads through the same CourseLeaf template but
#     wasn't captured by this fetch). This parser is written to match the
#     documented pattern ("CS 391L. Machine Learning." heading, description,
#     credit-hours sentence) and CourseLeaf's known conventions, but it is
#     the least-verified of this group and should be double-checked once the
#     script actually runs.
# ---------------------------------------------------------------------------

courseleaf_heading_pattern = re.compile(r"^([A-Z]{2,6}[\s-]?\d{3,4}[A-Z]?)\.?:?\s+(.+)$")

courseleaf_skip_prefixes = (
    "Prerequisite",
    "Corequisite",
    "Cross-listed with",
    "Credit Only Granted for",
    "Restriction",
    "Formerly",
    "Recommended Preparation",
    "Same as",
)


def _next_courseleaf_description(bold_tag):
    """Walk forward through the document looking for the paragraph that
    holds the actual course description, skipping metadata paragraphs like
    "Prerequisite(s): ..." along the way. Stops (returns empty string) if it
    runs into what looks like the next course's bold heading first."""
    node = bold_tag
    while True:
        node = node.find_next(["p", "li"])
        if node is None:
            return ""
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.find(["strong", "b"]) and courseleaf_heading_pattern.match(text):
            # We've wandered into the next course's heading without finding
            # a real description paragraph in between.
            return ""
        if any(text.startswith(prefix) for prefix in courseleaf_skip_prefixes):
            continue
        return text


def scrape_courseleaf_program(name, url):
    """Handles CourseLeaf-based catalog sites: UIUC, Northeastern, UMD
    (CMSC and ENPM), and UT Austin.
    Pattern: a bold heading such as "CS 100 Computer Science Orientation
    credit: 1 Hour." or "CMSC401 Algorithms for Geospatial Computing
    (3 Credits)", followed by a description paragraph. Some courses have
    extra "Prerequisite(s):"/"Cross-listed with:"/etc. paragraphs after the
    description -- those are skipped, not treated as the description."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        text = bold_tag.get_text(" ", strip=True)
        match = courseleaf_heading_pattern.match(text)
        if not match:
            continue

        course_code = match.group(1).strip()
        course_name = _clean_title(match.group(2))
        if not course_name:
            continue

        description = _next_courseleaf_description(bold_tag)
        # UT Austin appends a "X Semester Credit Hours." sentence to the end
        # of the description -- keep it, it's genuine catalog content, no
        # need to strip it.

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 4: Boston University GRS bulletin pattern
# A bulleted list where each <li> starts with a bold, linked heading like
# "CAS CS 511: Formal Methods 1" and the description text follows right
# after it inside the same list item.
# Confidence: HIGH -- verified directly via web_fetch.
# ---------------------------------------------------------------------------

bu_heading_pattern = re.compile(r"^([A-Z]{2,4}\s+[A-Z]{2,4}\s?\d{3,4}):\s*(.+)$")


def scrape_bu_program(name, url):
    """Handles Boston University's GRS course-listing pages.
    Pattern: each course is a bullet-list item whose first piece of text is
    a bold, linked heading like "CAS CS 511: Formal Methods 1", and the
    description text (including any "Undergraduate Prerequisites: ..." bit)
    follows directly after it in the same list item."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        heading_text = bold_tag.get_text(" ", strip=True)
        match = bu_heading_pattern.match(heading_text)
        if not match:
            continue

        course_code = match.group(1).strip()
        course_name = match.group(2).strip()

        list_item = bold_tag.find_parent("li")
        if list_item is None:
            description = ""
        else:
            full_text = list_item.get_text(" ", strip=True)
            description = full_text[len(heading_text):].strip(" -–")

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 5: University of Wisconsin-Madison "Guide" pattern
# Bold heading like "COMP SCI 540 -- INTRODUCTION TO ARTIFICIAL
# INTELLIGENCE", then a short "N credits." paragraph, then the real
# description paragraph, then a "View details" line and a "Requisites:"
# paragraph that we want to ignore.
# Confidence: HIGH -- verified directly via web_fetch.
# Judgment call: some course headings are cross-listed, e.g.
# "COMP SCI/L I S 102" (the number is shared between both subject codes).
# For those we only keep the first subject ("COMP SCI") paired with the
# shared number -- MEDIUM confidence specifically for cross-listed courses.
# ---------------------------------------------------------------------------

wisconsin_credits_pattern = re.compile(r"^\d+(?:-\d+)?\s+credits?\.?$", re.IGNORECASE)


def _parse_wisconsin_heading(text):
    """Turn "COMP SCI/L I S 102 -- INTRODUCTION TO AI" into
    ("COMP SCI 102", "Introduction To Ai"). Returns None if the text doesn't
    look like a course heading."""
    text = text.replace("​", "")  # drop any zero-width spaces
    for dash in ("—", "–", "--", "-"):
        if dash in text:
            left, _, right = text.partition(dash)
            break
    else:
        return None

    left = left.strip()
    title = right.strip()
    if not left or not title:
        return None

    number_match = re.search(r"(\d{3,4})\s*$", left)
    if not number_match:
        return None
    number = number_match.group(1)

    subject = left.split("/")[0].strip()
    subject = re.sub(r"\d{3,4}\s*$", "", subject).strip()  # drop a trailing number if this subject wasn't cross-listed
    subject = re.sub(r"\s+", " ", subject)
    if not subject:
        return None

    return f"{subject} {number}", title


def _next_wisconsin_description(bold_tag):
    node = bold_tag
    while True:
        node = node.find_next("p")
        if node is None:
            return ""
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if wisconsin_credits_pattern.match(text):
            continue
        if text.lower() == "view details":
            continue
        if text.startswith("Requisites:") or text.startswith("Course Designation:"):
            return ""
        if node.find(["strong", "b"]):
            return ""
        return text


def scrape_wisconsin_program(name, url):
    """Handles the University of Wisconsin-Madison course guide pages.
    Pattern: a bold heading like "COMP SCI 540 -- INTRODUCTION TO
    ARTIFICIAL INTELLIGENCE", then a "N credits." line, then the
    description paragraph, then a "View details" line and a "Requisites:"
    paragraph -- the credits line and everything from "Requisites:" onward
    is ignored."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        heading_text = bold_tag.get_text(" ", strip=True)
        parsed = _parse_wisconsin_heading(heading_text)
        if parsed is None:
            continue
        course_code, course_name = parsed
        course_name = course_name.title()

        description = _next_wisconsin_description(bold_tag)

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 6: University of Washington CSE catalog pattern
# Bold heading like "CSE 546 Machine Learning (4)" (sometimes followed by
# distribution-area abbreviations like "NSc, RSN"), then the description,
# then a "[View course details in MyPlan: CSE 546]" link that we want to
# ignore.
# Confidence: HIGH -- verified directly via web_fetch.
# ---------------------------------------------------------------------------

uw_heading_pattern = re.compile(r"^([A-Z]{2,6}\s?\d{3})\s+(.+?)\s*\(\d+(?:-\d+)?\)")


def scrape_uw_program(name, url):
    """Handles the University of Washington CSE course catalog page.
    Pattern: a bold heading like "CSE 546 Machine Learning (4) NSc, RSN",
    followed by the description text in the same block, followed by a
    "View course details in MyPlan: ..." link that isn't part of the real
    description and gets stripped off."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)

    seen = {}
    for bold_tag in soup.find_all(["strong", "b"]):
        heading_text = bold_tag.get_text(" ", strip=True)
        match = uw_heading_pattern.match(heading_text)
        if not match:
            continue

        course_code = match.group(1).strip()
        course_name = match.group(2).strip()

        container = bold_tag.find_parent("p") or bold_tag.parent
        full_text = container.get_text(" ", strip=True) if container else ""
        remainder = full_text[len(heading_text):].strip()
        remainder = re.sub(r"View course details.*$", "", remainder, flags=re.IGNORECASE).strip()
        description = remainder

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


# ---------------------------------------------------------------------------
# Parser 7: plain-text heading pattern (no bold tag at all)
# Shared by: Carnegie Mellon (School of Computer Science and Heinz College),
# Penn State World Campus (DAAN), and University of Michigan (EECS).
#
# These pages don't wrap the course heading in <strong>/<b> at all (at least
# not in a way that survives to the fetched page text), so instead of
# hunting for a specific tag we work off the page's plain text, line by
# line: find lines that look like a course heading, and treat the LONGEST
# nearby line (before the next course heading) as the description. Real
# course descriptions are almost always much longer than the short label
# lines around them ("Fall and Spring: 12 units", "3 Credits",
# "Prerequisite: ...", etc.), so "pick the longest candidate line" turns out
# to be a simple and fairly reliable way to find the real description
# without needing to know the exact underlying HTML tags.
#
# Known limitation: if a course's real description is unusually short (e.g.
# literally just "Thesis Research", matching its own title), this heuristic
# can occasionally grab the wrong short line. This is rare and is a
# documented trade-off, not an oversight.
#
# Confidence:
#   - CMU (both schools): HIGH -- verified directly via web_fetch. Heading
#     like "07-380 Artificial Intelligence and Machine Learning II", next
#     line "Fall and Spring: 12 units", then description, then optional
#     "Prerequisites:"/"Course Website:" lines.
#   - Penn State DAAN: MEDIUM -- verified directly via web_fetch, but the
#     heading text wasn't wrapped in visible bold markers the way most other
#     sites were, so the exact underlying tag is uncertain (could be a
#     heading tag, a <dt>, or styled with CSS instead of a semantic tag).
#     The page also repeats each course's code/title/credits a second time
#     right before the description, which this line-based approach handles
#     naturally since it just looks for the longest nearby line.
#   - Michigan EECS: HIGH -- verified directly via web_fetch. Heading like
#     "EECS 545. Machine Learning (CSE)", description ends with
#     "CourseProfile (ATLAS)" which we strip off.
# ---------------------------------------------------------------------------

plain_heading_skip_prefixes = (
    "Prerequisite",
    "Advisory Prerequisite",
    "Enforced Prerequisite",
    "Corequisite",
    "Credit Exclusion",
    "Minimum grade",
    "Fewer than",
    "Cross-listed with",
    "Course Website",
    "Recommended Preparation",
)


def scrape_plain_text_heading_program(name, url, heading_pattern, max_window=25):
    """Handles catalog pages where the course heading is plain text rather
    than a bold tag: Carnegie Mellon (SCS and Heinz), Penn State (DAAN), and
    University of Michigan (EECS).
    `heading_pattern` is a compiled regex with two capture groups: the
    course code and the course title. We scan the page's plain text line by
    line, find lines that match `heading_pattern`, and treat the longest
    non-label line before the next heading as the description."""
    print(f"Fetching: {name}")
    soup = _get_soup(url)
    page_text = soup.get_text("\n")
    lines = [line.strip() for line in page_text.split("\n")]
    lines = [line for line in lines if line]

    heading_idxs = [i for i, line in enumerate(lines) if heading_pattern.match(line)]

    seen = {}
    for pos, idx in enumerate(heading_idxs):
        match = heading_pattern.match(lines[idx])
        course_code = match.group(1).strip()
        course_name = _clean_title(match.group(2))
        if not course_name:
            continue

        window_end = heading_idxs[pos + 1] if pos + 1 < len(heading_idxs) else min(idx + 1 + max_window, len(lines))
        window = lines[idx + 1:window_end]

        candidates = []
        for line in window:
            if line == course_code or line == course_name:
                continue
            if any(line.startswith(prefix) for prefix in plain_heading_skip_prefixes):
                continue
            candidates.append(line)

        description = max(candidates, key=len) if candidates else ""
        description = re.sub(r"\s*CourseProfile \(ATLAS\)\s*$", "", description).strip()

        if course_code not in seen or len(description) > len(seen[course_code]["description"]):
            seen[course_code] = {
                "program": name,
                "course_code": course_code,
                "course_name": course_name,
                "description": description,
            }

    return list(seen.values())


cmu_heading_pattern = re.compile(r"^(\d{2}-\d{3})\s+(.+)$")
psu_heading_pattern = re.compile(r"^([A-Z]{2,6}(?:-[A-Z])?\s?\d{3}):\s*(.+)$")
michigan_heading_pattern = re.compile(r"^([A-Z]{2,6}\s\d{3})\.\s+(.+)$")


# ---------------------------------------------------------------------------
# Programs to scrape. Each entry says which parser function to use and any
# extra keyword arguments that parser needs. A program can list either a
# single "url" or a list of "urls" (used for Boston University, whose
# course list is split across two pages) -- results from multiple URLs for
# the same program are merged together and deduplicated by course code.
# ---------------------------------------------------------------------------

PROGRAMS = [
    {
        "name": "Georgia Tech - MS Analytics (OMS Analytics)",
        "url": "https://pe.gatech.edu/degrees/analytics/curriculum",
        "output_file": "sample_gatech_analytics_courses.json",
        "parser": scrape_program,
    },
    {
        "name": "Georgia Tech - MS Cybersecurity (OMS Cybersecurity)",
        "url": "https://pe.gatech.edu/degrees/cybersecurity/curriculum",
        "output_file": "sample_gatech_cybersecurity_courses.json",
        "parser": scrape_program,
    },
    {
        "name": "ASU - Online Master of Computer Science",
        "url": "https://asuonline.asu.edu/online-degree-programs/graduate/computer-science-mcs/",
        "output_file": "sample_asu_mcs_courses.json",
        "parser": scrape_asu_bullet_program,
    },
    {
        "name": "UIUC - CS Course Catalog",
        "url": "https://catalog.illinois.edu/courses-of-instruction/cs/",
        "output_file": "sample_uiuc_cs_courses.json",
        "parser": scrape_courseleaf_program,
    },
    {
        "name": "Northeastern - CS Course Descriptions",
        "url": "https://catalog.northeastern.edu/course-descriptions/cs/",
        "output_file": "sample_northeastern_cs_courses.json",
        "parser": scrape_courseleaf_program,
    },
    {
        "name": "Boston University - Graduate CS Courses",
        "urls": [
            "https://www.bu.edu/academics/grs/courses/computer-science/",
            "https://www.bu.edu/academics/grs/courses/computer-science/2/",
        ],
        "output_file": "sample_bu_cs_courses.json",
        "parser": scrape_bu_program,
    },
    {
        "name": "University of Wisconsin-Madison - Computer Sciences",
        "url": "https://guide.wisc.edu/courses/comp_sci/",
        "output_file": "sample_wisconsin_cs_courses.json",
        "parser": scrape_wisconsin_program,
    },
    {
        "name": "University of Maryland - CMSC Graduate Catalog",
        "url": "https://academiccatalog.umd.edu/graduate/courses/cmsc/",
        "output_file": "sample_umd_cmsc_courses.json",
        "parser": scrape_courseleaf_program,
    },
    {
        "name": "University of Maryland - ENPM Graduate Catalog",
        "url": "https://academiccatalog.umd.edu/graduate/courses/enpm/",
        "output_file": "sample_umd_enpm_courses.json",
        "parser": scrape_courseleaf_program,
    },
    {
        "name": "Penn State World Campus - Data Analytics (DAAN)",
        "url": "https://bulletins.psu.edu/university-course-descriptions/graduate/daan/",
        "output_file": "sample_psu_daan_courses.json",
        "parser": scrape_plain_text_heading_program,
        "parser_kwargs": {"heading_pattern": psu_heading_pattern},
    },
    {
        "name": "Carnegie Mellon - School of Computer Science",
        "url": "https://coursecatalog.web.cmu.edu/schools-colleges/schoolofcomputerscience/courses/",
        "output_file": "sample_cmu_scs_courses.json",
        "parser": scrape_plain_text_heading_program,
        "parser_kwargs": {"heading_pattern": cmu_heading_pattern},
    },
    {
        "name": "Carnegie Mellon - Heinz College",
        "url": "https://coursecatalog.web.cmu.edu/schools-colleges/heinzcollegeofinformationsystemsandpublicpolicy/",
        "output_file": "sample_cmu_heinz_courses.json",
        "parser": scrape_plain_text_heading_program,
        "parser_kwargs": {"heading_pattern": cmu_heading_pattern},
    },
    {
        "name": "University of Washington - CSE Course Catalog",
        "url": "https://www.washington.edu/students/crscat/cse.html",
        "output_file": "sample_uw_cse_courses.json",
        "parser": scrape_uw_program,
    },
    {
        "name": "University of Michigan - EECS Course Bulletin",
        "url": "https://bulletin.engin.umich.edu/courses/eecs/",
        "output_file": "sample_umich_eecs_courses.json",
        "parser": scrape_plain_text_heading_program,
        "parser_kwargs": {"heading_pattern": michigan_heading_pattern},
    },
    {
        # Replaces UT Austin, which returned 0 courses when actually run
        # (its real page structure didn't match what we could see in
        # advance). Georgia Tech's main CS catalog is a different, richer
        # page than the two OMS pages already scraped above -- it covers
        # the full CS department, undergrad through grad -- and uses the
        # same CourseLeaf-style pattern already verified to work.
        "name": "Georgia Tech - Main CS Course Catalog",
        "url": "https://catalog.gatech.edu/coursesaz/cs/",
        "output_file": "sample_gatech_maincatalog_cs_courses.json",
        "parser": scrape_courseleaf_program,
    },
]


if __name__ == "__main__":
    for program in PROGRAMS:
        name = program["name"]
        parser = program["parser"]
        parser_kwargs = program.get("parser_kwargs", {})
        urls = program["urls"] if "urls" in program else [program["url"]]

        try:
            merged = {}
            for url in urls:
                courses = parser(name, url, **parser_kwargs)
                for course in courses:
                    code = course["course_code"]
                    if code not in merged or len(course["description"]) > len(merged[code]["description"]):
                        merged[code] = course

            _save_courses(merged, name, program["output_file"])

        except Exception as exc:
            # One program failing to scrape (site down, layout changed,
            # network hiccup, etc.) shouldn't stop the rest of the programs
            # from being scraped.
            print(f"  !! WARNING: could not scrape '{name}' ({url}): {exc}\n")
            continue

    print("Done with all programs.")
