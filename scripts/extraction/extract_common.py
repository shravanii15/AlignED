"""
extract_common.py

What this script does, in plain terms:
This is a *library*, not something you run directly -- it holds the pieces
that are shared between our two skill-extraction methods
(extract_baseline.py, the keyword-matching approach, and extract_llm.py,
the local-AI approach). Both of those scripts need the exact same two
things: (1) a single, flat, de-duplicated list of every valid skill/
knowledge/technology term we're allowed to extract, and (2) a consistent
way to compare two term strings and decide "is this the same skill?".

Why this lives in its own file instead of being copied into both scripts:
if the matching logic (e.g. how we normalize "  Python " vs "python") were
written twice and one copy got tweaked later without updating the other,
the two extraction methods would silently stop being comparable to each
other -- which would quietly wreck the whole point of this phase of the
project (proving the LLM beats the baseline on the *same* yardstick).
Keeping one shared copy here means a fix or tweak only has to happen once.

Where the vocabulary comes from:
- data/taxonomy/onet_computing_skills.json -- 57 O*NET "Skills" and
  "Knowledge" entries (e.g. "Programming", "Computers and Electronics").
  Each entry already carries an onet_category field telling us which of
  the two it is, so we just pass that straight through.
- data/taxonomy/onet_computing_technologies.json -- 98 broad technology
  *categories* (e.g. "Development environment software"), each with a list
  of concrete, named tools under "examples" (e.g. "Python", "Git",
  "AWS SageMaker"). We don't care about the category grouping here -- we
  just want the flat list of ~1,569 named tools, each tagged as type
  "technology".
"""

import difflib
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "taxonomy")
SKILLS_PATH = os.path.join(DATA_DIR, "onet_computing_skills.json")
TECHNOLOGIES_PATH = os.path.join(DATA_DIR, "onet_computing_technologies.json")


def normalize_term(term):
    """Turn a term string into a consistent form for comparison purposes
    only (never for display -- always show the user the original,
    nicely-cased term). We lowercase and collapse/strip surrounding
    whitespace so that trivial differences like "Python " vs "python"
    or extra spaces don't cause a real match to be missed. This is
    intentionally simple: we are NOT trying to handle plurals, synonyms,
    or abbreviations here (e.g. "JS" vs "JavaScript") -- that kind of
    fuzzy matching is exactly the sort of judgment call we want the LLM
    to make, and it would be unfair to bake it into the baseline too."""
    if term is None:
        return ""
    return " ".join(term.strip().lower().split())


def load_vocabulary():
    """Load and flatten the full controlled vocabulary into one clean list
    of {"term": str, "type": str} dicts, where type is "skill",
    "knowledge", or "technology".

    This is the single source of truth both extraction methods are
    grounded against: the baseline scans text for these exact terms, and
    the LLM is told "you may only pick from this list, verbatim." Neither
    method is allowed to invent a skill name that isn't in here.
    """
    vocabulary = []

    with open(SKILLS_PATH, "r", encoding="utf-8") as f:
        skills_and_knowledge = json.load(f)
    for entry in skills_and_knowledge:
        vocabulary.append(
            {
                "term": entry["name"],
                # onet_category on the source entry is already exactly
                # "skill" or "knowledge", so we pass it straight through.
                "type": entry["onet_category"],
            }
        )

    with open(TECHNOLOGIES_PATH, "r", encoding="utf-8") as f:
        technology_categories = json.load(f)
    seen_tech_terms = set()
    for category in technology_categories:
        for example in category.get("examples", []):
            title = example["title"]
            # The same named tool can legitimately appear under more than
            # one broad category (e.g. a tool useful for both "database
            # management" and "development environment" software), so we
            # de-duplicate on the normalized title to keep one clean entry
            # per real-world tool.
            key = normalize_term(title)
            if key in seen_tech_terms:
                continue
            seen_tech_terms.add(key)
            vocabulary.append({"term": title, "type": "technology"})

    return vocabulary


def build_normalized_lookup(vocabulary):
    """Build a dict mapping normalize_term(entry["term"]) -> the original
    vocabulary entry, so callers can take a messy/differently-cased string
    (e.g. something an LLM returned) and cheaply check "does this match a
    real vocabulary term, and if so, which one?" without re-scanning the
    whole list every time."""
    lookup = {}
    for entry in vocabulary:
        lookup[normalize_term(entry["term"])] = entry
    return lookup


def fuzzy_match_term(raw_term, vocabulary, normalized_lookup, cutoff=0.70):
    """Take a free-text term (something the LLM said in its own words,
    NOT constrained to our vocabulary) and find the closest real
    vocabulary entry, if any is close enough to trust.

    Why this exists: the original design fed the entire ~1,600-term
    vocabulary into every LLM prompt and demanded exact, verbatim
    matches. On a laptop-grade, CPU-only machine that made every prompt
    huge, and the model spent most of its time just *reading* the
    vocabulary rather than reasoning about the actual text -- in
    practice this caused near-total request timeouts. This function is
    the fix: the LLM now answers in its own words from a short prompt
    (fast), and normalization -- matching "AWS" or "amazon web services"
    back to our real vocabulary entry -- happens here afterward, cheaply,
    in plain Python.

    We try an exact (normalized) match first since that's the strongest,
    most trustworthy signal. Only if there's no exact match do we fall
    back to difflib's sequence-similarity scoring, and only accept a
    fuzzy match if it clears `cutoff` (0.0-1.0 similarity). 0.82 was
    chosen deliberately conservative: high enough to catch minor
    casing/spacing/pluralization differences ("Python" vs "python ") and
    close paraphrases, but not so loose that unrelated terms get matched
    to each other just because they share a few letters. Returns the
    matched vocabulary entry dict, or None if nothing was close enough --
    a term with no good match is dropped, not force-fit to the nearest
    (and possibly wrong) vocabulary entry."""
    normalized_raw = normalize_term(raw_term)
    if not normalized_raw:
        return None

    exact = normalized_lookup.get(normalized_raw)
    if exact is not None:
        return exact

    all_normalized_terms = list(normalized_lookup.keys())
    close = difflib.get_close_matches(
        normalized_raw, all_normalized_terms, n=1, cutoff=cutoff
    )
    if not close:
        return None
    return normalized_lookup[close[0]]
