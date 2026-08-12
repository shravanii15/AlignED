"""
fetch_esco_taxonomy.py

What this script does, in plain terms:
Before we can ask an AI model to pull skills out of a job posting or course
description, we need a trustworthy, pre-existing list of what "skills"
even are -- otherwise the model could invent categories that sound
reasonable but aren't grounded in anything real. This script downloads
that list from ESCO (European Skills, Competences, Qualifications and
Occupations), a free, public skills taxonomy maintained by the European
Commission. It's a placeholder for O*NET (the equivalent US taxonomy)
until our O*NET account gets approved -- at that point we can add a
similar script for O*NET and compare/merge the two.

We don't download the *entire* ESCO taxonomy (it covers every occupation
that exists, from florists to pilots). Instead, we walk just the
computing/technology branch: software development, web development,
database and network professionals, and ICT technicians -- the occupation
families our 13 university programs actually map to.

How it works, step by step:
1. Start from a curated list of ISCO occupation-group codes that cover
   computing/tech roles (e.g. "2512" = Software developers).
2. For each group, ask ESCO's API for every specific occupation inside it
   (e.g. "software developer", "web developer", "software architect").
3. For each of those occupations, ask ESCO for its "essential" and
   "optional" skills -- these come straight from the API, no guessing.
4. Combine everything into one de-duplicated skill list and save it,
   along with the occupation list, so later scripts (the LLM skill
   extraction pipeline) can check their output against this real,
   government-grade taxonomy instead of trusting the AI blindly.

This is a one-time (or occasional) download, not something that needs to
run daily.
"""

import json
import os
import time

import requests

API_BASE = "https://ec.europa.eu/esco/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (AlignED research project; educational use)"}
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "taxonomy")

# ISCO-08 occupation-group codes covering computing/technology roles.
# Each maps to a real branch of ESCO's classification tree -- see
# https://esco.ec.europa.eu/en/classification/occupation_main for the
# full tree if we ever want to widen this list.
ISCO_GROUPS = {
    "1330": "ICT service managers",
    "2511": "Systems analysts",
    "2512": "Software developers",
    "2513": "Web and multimedia developers",
    "2514": "Applications programmers",
    "2519": "Software and applications developers and analysts not elsewhere classified",
    "2521": "Database designers and administrators",
    "2522": "Systems administrators",
    "2523": "Computer network professionals",
    "2529": "Database and network professionals not elsewhere classified",
    "3511": "ICT operations technicians",
    "3512": "ICT user support technicians",
    "3513": "Computer network and systems technicians",
    "3514": "Web technicians",
}

REQUEST_DELAY_SECONDS = 0.3  # be a polite, rate-limited citizen of a free public API


def _get_json(url, params):
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return response.json()


def get_occupations_in_group(isco_code):
    """Ask ESCO for every specific occupation inside one ISCO group,
    e.g. "2512" (Software developers) -> "software developer",
    "user interface developer", "software analyst", "software architect"."""
    uri = f"http://data.europa.eu/esco/isco/C{isco_code}"
    data = _get_json(f"{API_BASE}/resource/concept", {"uri": uri, "language": "en"})
    narrower = data.get("_links", {}).get("narrowerOccupation", [])
    return [{"uri": item["uri"], "title": item["title"]} for item in narrower]


def get_occupation_skills(occupation_uri):
    """Ask ESCO for one occupation's essential and optional skills."""
    data = _get_json(
        f"{API_BASE}/resource/occupation", {"uri": occupation_uri, "language": "en"}
    )
    links = data.get("_links", {})
    essential = links.get("hasEssentialSkill", [])
    optional = links.get("hasOptionalSkill", [])
    description = data.get("description", {}).get("en", {}).get("literal", "")
    return description, essential, optional


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    all_occupations = {}
    all_skills = {}

    for isco_code, group_name in ISCO_GROUPS.items():
        print(f"Fetching occupation group {isco_code} - {group_name}...")
        try:
            occupations = get_occupations_in_group(isco_code)
        except Exception as exc:
            print(f"  !! WARNING: could not fetch group {isco_code}: {exc}")
            continue
        print(f"  -> Found {len(occupations)} occupations.")

        for occ in occupations:
            occ_uri = occ["uri"]
            if occ_uri in all_occupations:
                # Some occupations legitimately sit under more than one
                # group; just note the extra group instead of re-fetching.
                all_occupations[occ_uri]["isco_groups"].append(isco_code)
                continue

            try:
                description, essential, optional = get_occupation_skills(occ_uri)
            except Exception as exc:
                print(f"  !! WARNING: could not fetch skills for '{occ['title']}': {exc}")
                continue

            essential_uris = [s["uri"] for s in essential]
            optional_uris = [s["uri"] for s in optional]

            all_occupations[occ_uri] = {
                "uri": occ_uri,
                "title": occ["title"],
                "isco_groups": [isco_code],
                "isco_group_name": group_name,
                "description": description,
                "essential_skill_uris": essential_uris,
                "optional_skill_uris": optional_uris,
            }

            for skill in essential + optional:
                skill_uri = skill["uri"]
                if skill_uri not in all_skills:
                    all_skills[skill_uri] = {
                        "uri": skill_uri,
                        "preferred_label": skill["title"],
                        "skill_type": skill.get("skillType", "").rsplit("/", 1)[-1],
                        "used_by_occupations": [],
                    }
                all_skills[skill_uri]["used_by_occupations"].append(occ["title"])

    occupations_path = os.path.join(DATA_DIR, "esco_computing_occupations.json")
    skills_path = os.path.join(DATA_DIR, "esco_computing_skills.json")

    with open(occupations_path, "w") as f:
        json.dump(list(all_occupations.values()), f, indent=2)
    with open(skills_path, "w") as f:
        json.dump(list(all_skills.values()), f, indent=2)

    print(f"\nSaved {len(all_occupations)} occupations to: {occupations_path}")
    print(f"Saved {len(all_skills)} unique skills to: {skills_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
