"""
fetch_onet_taxonomy.py

What this script does, in plain terms:
This is the O*NET counterpart to fetch_esco_taxonomy.py. O*NET (the
Occupational Information Network) is the official US Department of Labor
skills taxonomy -- the one real American employers, career counselors, and
labor economists actually use day to day. We're adding it as our *primary*
taxonomy going forward, replacing ESCO in that role, for one big reason:
ESCO only has abstract "skills" (e.g. "use software development tools"),
while O*NET also has concrete "Technology Skills" -- specific, named,
real-world tools like Python, AWS, Docker, Kubernetes, Git, and Tableau.
That's exactly the kind of thing a job posting or a course syllabus
actually mentions by name, so it's much more useful for grounding an AI
model's skill extraction than ESCO's more abstract categories.

Like the ESCO script, we don't pull all of O*NET (which covers every
occupation from farmers to surgeons). We only pull the computing/tech
branch -- roughly the "Computer and Mathematical Occupations" major group
(O*NET-SOC codes starting with "15-1" and "15-2"): software developers,
data scientists, database administrators, network/systems administrators,
information security analysts, web developers, computer support
specialists, and similar roles.

How it works, step by step:
1. Instead of hardcoding O*NET-SOC codes (which could go stale or simply
   be wrong), we ask O*NET's own keyword-search endpoint for occupations
   matching terms like "software developer", "data scientist", "database
   administrator", etc. We keep only the results whose O*NET-SOC code
   falls in the Computer/Mathematical major group, since a keyword search
   can occasionally surface a loosely-related occupation (e.g. a "sales
   engineer" that merely mentions software).
2. For each occupation we find this way, we ask O*NET for three things:
     - "Technology Skills" -- the named-tool list. This is the headline
       feature ESCO doesn't have, so we also save it as its own file.
     - "Skills" -- O*NET's general skill descriptors (similar in spirit
       to ESCO's essential/optional skills).
     - "Knowledge" -- broader subject-matter areas (e.g. "Computers and
       Electronics"), which ESCO doesn't split out separately.
3. We combine everything into de-duplicated lists and save them, so later
   scripts (the LLM skill-extraction pipeline) can check their output
   against this real, government-grade taxonomy instead of trusting the
   AI blindly -- exactly how the ESCO script is used today.

A note on things we could not directly test:
This script was written by reading O*NET's public API reference docs
(https://services.onetcenter.org/reference/), but the sandbox this script
was written in cannot make live, authenticated calls to external APIs
(outbound requests get proxy-blocked here, the same known limitation that
affects the Adzuna and university-scraping scripts in this project). So
the endpoint paths, parameter names, and response shapes below were
confirmed by reading the docs, but the script itself was never run
end-to-end. It's meant to be run by a human on their own machine, where
this restriction doesn't apply. Anywhere we had to make a judgment call
instead of reading it directly off the docs, it's called out in a comment
nearby (search for "NOTE:").

This is a one-time (or occasional) download, not something that needs to
run daily.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

# Load the secret keys from the .env file sitting next to this project.
# We NEVER type the actual key directly into this file - that's the whole
# point of keeping it in .env instead.
load_dotenv()

API_KEY = os.getenv("ONET_API_KEY")
if not API_KEY:
    raise SystemExit("Missing O*NET API key. Check your .env file (ONET_API_KEY).")

# Confirmed from https://services.onetcenter.org/reference/start/overview:
# O*NET Web Services v2.0 lives on a separate host from the documentation
# site (api-v2.onetcenter.org, not services.onetcenter.org), and every
# request must carry the key in an X-API-Key HTTP header. Keys are NOT
# accepted in the query string or as Basic Auth, and only GET requests are
# allowed.
API_BASE = "https://api-v2.onetcenter.org"
HEADERS = {
    "X-API-Key": API_KEY,
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (AlignED research project; educational use)",
}
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "taxonomy")

REQUEST_DELAY_SECONDS = 0.3  # be a polite, rate-limited citizen of a free public API

# Keyword phrases we search O*NET for, to *discover* the right O*NET-SOC
# occupation codes rather than guessing them ourselves. Each phrase maps
# to https://api-v2.onetcenter.org/online/search?keyword=<phrase> (see
# https://services.onetcenter.org/reference/online/search).
KEYWORD_SEARCHES = [
    "software developer",
    "software engineer",
    "software quality assurance",
    "computer programmer",
    "computer systems analyst",
    "computer and information research scientist",
    "data scientist",
    "database administrator",
    "database architect",
    "network and computer systems administrator",
    "computer network architect",
    "computer network support specialist",
    "computer user support specialist",
    "information security analyst",
    "web developer",
    "web and digital interface designer",
    "digital forensics analyst",
    "information technology project manager",
]

# O*NET's "Computer and Mathematical Occupations" major group (SOC 15-0000)
# covers the codes we want; within it, "15-1" is specifically computer
# occupations and "15-2" is mathematical occupations (which is where "Data
# Scientists", 15-2051.00, lives). We use this prefix check to filter out
# any loosely-related results a keyword search might still surface.
RELEVANT_SOC_PREFIXES = ("15-1", "15-2")


def _get_json(url, params=None):
    """Make one GET request to the O*NET API and return the parsed JSON.
    All O*NET Web Services calls are GET-only and must carry the
    X-API-Key header (see HEADERS above)."""
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return response.json()


def search_occupations(keyword):
    """Ask O*NET's keyword-search endpoint for occupations matching a
    phrase, e.g. "data scientist" -> "Data Scientists" (15-2051.00).
    Confirmed shape (from the docs' worked example):
        {
          "start": 1, "end": 20, "total": 63,
          "next": "https://api-v2.onetcenter.org/online/search?keyword=...",
          "occupation": [
            {"href": "...", "code": "17-1011.00", "title": "...", "tags": {}},
            ...
          ]
        }
    Results are paginated 20-at-a-time by default; we follow the "next"
    link (also returned by the API itself) until there isn't one."""
    results = []
    url = f"{API_BASE}/online/search"
    params = {"keyword": keyword, "start": 1, "end": 20}
    while url:
        data = _get_json(url, params)
        results.extend(data.get("occupation", []))
        url = data.get("next")
        params = None  # the "next" URL already carries its own query string
    return results


def get_all_summary_pages(path):
    """Generic pager for O*NET's occupation 'summary' endpoints (skills,
    knowledge, technology_skills). These only return 5 items per page by
    default (see the "start"/"end" query parameters in the docs), so we
    ask for a larger page up front and then keep following the API's own
    "next" link until every item has been collected.

    NOTE: asking for end=50 on the first request is an inference, not
    something the docs explicitly confirm works past an occupation's true
    total -- REST APIs that paginate this way conventionally just clamp to
    the real total rather than erroring, and the "next" link keeps this
    correct either way, but a human running this for the first time should
    keep an eye on the printed counts to make sure nothing looks truncated.
    """
    url = f"{API_BASE}{path}"
    params = {"start": 1, "end": 50}
    pages = []
    while url:
        data = _get_json(url, params)
        pages.append(data)
        url = data.get("next")
        params = None
    return pages


def get_occupation_skills(code):
    """Ask O*NET for one occupation's top "Skills" descriptors, e.g.
    "Active Listening", "Complex Problem Solving". Confirmed shape:
        {"element": [{"id": "2.A.1.b", "name": "...", "description": "...",
                       "related": "..."}, ...]}
    """
    pages = get_all_summary_pages(f"/online/occupations/{code}/summary/skills")
    elements = []
    for page in pages:
        elements.extend(page.get("element", []))
    return elements


def get_occupation_knowledge(code):
    """Ask O*NET for one occupation's "Knowledge" areas, e.g. "Design",
    "Engineering and Technology". Same response shape as Skills above."""
    pages = get_all_summary_pages(f"/online/occupations/{code}/summary/knowledge")
    elements = []
    for page in pages:
        elements.extend(page.get("element", []))
    return elements


def get_occupation_technology_skills(code):
    """Ask O*NET for one occupation's "Technology Skills" -- the named,
    concrete tools (this is the standout feature vs. ESCO). Confirmed
    shape (from the docs' worked example):
        {"category": [
            {"code": 43232604, "title": "Computer aided design CAD software",
             "related": "...",
             "example": [{"title": "Autodesk AutoCAD", "hot_technology": true,
                           "in_demand": true, "percentage": 22, "href": "..."}, ...],
             "example_more": [...]  # additional examples beyond the top 4
            }, ...
        ]}
    Each "category" is a broad tool category (e.g. "Object or component
    oriented development software"); "example"/"example_more" are the
    actual named products/tools within it (e.g. "Python", "Git")."""
    pages = get_all_summary_pages(
        f"/online/occupations/{code}/summary/technology_skills"
    )
    categories = []
    for page in pages:
        categories.extend(page.get("category", []))
    return categories


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Step 1: discover occupation codes by keyword search instead of
    # hardcoding them, per the O*NET-SOC 27.x taxonomy structure.
    discovered = {}  # code -> {"title": str, "keywords": set of str}

    for keyword in KEYWORD_SEARCHES:
        print(f"Searching O*NET for '{keyword}'...")
        try:
            found = search_occupations(keyword)
        except Exception as exc:
            print(f"  !! WARNING: search failed for '{keyword}': {exc}")
            continue

        kept = 0
        for occ in found:
            code = occ.get("code", "")
            if not code.startswith(RELEVANT_SOC_PREFIXES):
                continue
            if code not in discovered:
                discovered[code] = {"title": occ["title"], "keywords": set()}
                kept += 1
            discovered[code]["keywords"].add(keyword)
        print(f"  -> {len(found)} results, {kept} new computing occupations kept.")

    print(f"\nFound {len(discovered)} unique computing/tech occupations total.\n")

    all_occupations = {}
    all_skills = {}
    all_technologies = {}

    for code, info in sorted(discovered.items()):
        title = info["title"]
        print(f"Fetching details for {code} - {title}...")

        try:
            skills = get_occupation_skills(code)
        except Exception as exc:
            print(f"  !! WARNING: could not fetch skills for '{title}': {exc}")
            skills = []

        try:
            knowledge = get_occupation_knowledge(code)
        except Exception as exc:
            print(f"  !! WARNING: could not fetch knowledge for '{title}': {exc}")
            knowledge = []

        try:
            tech_categories = get_occupation_technology_skills(code)
        except Exception as exc:
            print(
                f"  !! WARNING: could not fetch technology skills for '{title}': {exc}"
            )
            tech_categories = []

        all_occupations[code] = {
            "code": code,
            "title": title,
            "matched_keywords": sorted(info["keywords"]),
            "skill_ids": [s["id"] for s in skills],
            "knowledge_ids": [k["id"] for k in knowledge],
            "technology_category_codes": [c["code"] for c in tech_categories],
        }

        # O*NET's "Skills" and "Knowledge" endpoints return the same shape
        # (id / name / description), so we merge both into one skills file,
        # the way ESCO's essential + optional skills get merged. We tag
        # each entry with which of the two it came from (O*NET's API
        # doesn't include this tag itself -- we add it ourselves here).
        for s in skills:
            sid = s["id"]
            if sid not in all_skills:
                all_skills[sid] = {
                    "id": sid,
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "onet_category": "skill",
                    "used_by_occupations": [],
                }
            all_skills[sid]["used_by_occupations"].append(title)

        for k in knowledge:
            kid = k["id"]
            if kid not in all_skills:
                all_skills[kid] = {
                    "id": kid,
                    "name": k["name"],
                    "description": k.get("description", ""),
                    "onet_category": "knowledge",
                    "used_by_occupations": [],
                }
            all_skills[kid]["used_by_occupations"].append(title)

        # Technology Skills get their own file (see module docstring), so
        # we build that structure separately: one entry per broad tool
        # category, each holding the de-duplicated list of named tools
        # ("examples") pulled from every occupation that uses it.
        for cat in tech_categories:
            cat_code = cat["code"]
            if cat_code not in all_technologies:
                all_technologies[cat_code] = {
                    "category_code": cat_code,
                    "category_title": cat["title"],
                    "examples": {},  # keyed by tool title, flattened before saving
                    "used_by_occupations": [],
                }
            all_technologies[cat_code]["used_by_occupations"].append(title)

            for example in cat.get("example", []) + cat.get("example_more", []):
                ex_title = example["title"]
                examples = all_technologies[cat_code]["examples"]
                if ex_title not in examples:
                    examples[ex_title] = {
                        "title": ex_title,
                        "hot_technology": example.get("hot_technology", False),
                        "in_demand": example.get("in_demand", False),
                    }

    # Flatten each category's examples dict into a plain list for clean JSON.
    technologies_list = []
    for tech in all_technologies.values():
        tech["examples"] = list(tech["examples"].values())
        technologies_list.append(tech)

    occupations_path = os.path.join(DATA_DIR, "onet_computing_occupations.json")
    skills_path = os.path.join(DATA_DIR, "onet_computing_skills.json")
    technologies_path = os.path.join(DATA_DIR, "onet_computing_technologies.json")

    with open(occupations_path, "w") as f:
        json.dump(list(all_occupations.values()), f, indent=2)
    with open(skills_path, "w") as f:
        json.dump(list(all_skills.values()), f, indent=2)
    with open(technologies_path, "w") as f:
        json.dump(technologies_list, f, indent=2)

    print(f"\nSaved {len(all_occupations)} occupations to: {occupations_path}")
    print(f"Saved {len(all_skills)} unique skills/knowledge areas to: {skills_path}")
    print(
        f"Saved {len(technologies_list)} technology categories "
        f"(with named tools) to: {technologies_path}"
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
