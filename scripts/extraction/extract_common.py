"""
extract_common.py

What this script does, in plain terms:
This is a *library*, not something you run directly, it holds the pieces
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
other, which would quietly wreck the whole point of this phase of the
project (proving the LLM beats the baseline on the *same* yardstick).
Keeping one shared copy here means a fix or tweak only has to happen once.

Where the vocabulary comes from:
- data/taxonomy/onet_computing_skills.json, 57 O*NET "Skills" and
  "Knowledge" entries (e.g. "Programming", "Computers and Electronics").
  Each entry already carries an onet_category field telling us which of
  the two it is, so we just pass that straight through.
- data/taxonomy/onet_computing_technologies.json, 98 broad technology
  *categories* (e.g. "Development environment software"), each with a list
  of concrete, named tools under "examples" (e.g. "Python", "Git",
  "AWS SageMaker"). We don't care about the category grouping here, we
  just want the flat list of ~1,569 named tools, each tagged as type
  "technology".
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "taxonomy")
SKILLS_PATH = os.path.join(DATA_DIR, "onet_computing_skills.json")
TECHNOLOGIES_PATH = os.path.join(DATA_DIR, "onet_computing_technologies.json")


def normalize_term(term):
    """Turn a term string into a consistent form for comparison purposes
    only (never for display, always show the user the original,
    nicely-cased term). We lowercase and collapse/strip surrounding
    whitespace so that trivial differences like "Python " vs "python"
    or extra spaces don't cause a real match to be missed. This is
    intentionally simple: we are NOT trying to handle plurals, synonyms,
    or abbreviations here (e.g. "JS" vs "JavaScript"), that kind of
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


# Explicit aliases for abbreviations and common spoken forms that a model
# (or a person) uses but the O*NET vocabulary spells differently. The value
# is the exact vocabulary term to ground to. An alias is only applied when
# that term really exists in the vocabulary passed in, so a stale alias can
# never invent a term.
ALIAS_MAP = {
    "sql": "Structured query language SQL",
    "aws": "Amazon Web Services AWS software",
    "amazon web services": "Amazon Web Services AWS software",
    "kafka": "Apache Kafka",
    "airflow": "Apache Airflow",
    "t-sql": "Microsoft transact-structural query language T-SQL",
    "tsql": "Microsoft transact-structural query language T-SQL",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "js": "JavaScript",
}

# Pairs a similarity-based matcher must never convert between, even when
# the scores are high. "SQL"/"NoSQL"/"MySQL" are three different skills,
# "Machine Learning" is not "Active Learning", and "statistics" is not the
# STATISTICA software. Keys are (normalized raw term, normalized candidate).
BLOCKED_PAIRS = {
    ("sql", "nosql"), ("sql", "mysql"), ("sql", "postgresql"),
    ("machine learning", "active learning"),
    ("statistics", "statistica"),
    ("java", "javascript"),
}


def is_lexical_conflict(raw_norm, candidate_norm):
    """True when a similarity-based match between these two normalized
    strings must be rejected: it is an explicitly blocked pair, or a word of
    the raw term only appears inside a longer, different word of the
    candidate (sql inside nosql or mysql, java inside javascript) and is
    never a whole word of the candidate. A whole-word match such as
    'azure' inside 'microsoft azure software' is fine."""
    if (raw_norm, candidate_norm) in BLOCKED_PAIRS:
        return True
    raw_toks = _tokens(raw_norm)
    cand_toks = _tokens(candidate_norm)
    for tok in raw_toks:
        if len(tok) < 2 or tok in cand_toks:
            continue
        if any(tok in ct and ct != tok for ct in cand_toks):
            return True
    return False


# Last-resort "variant" matching. Character-similarity matching (difflib)
# was removed on purpose: it scores "SQL" vs "NoSQL", "Machine Learning" vs
# "Active Learning" and "statistics" vs "STATISTICA" as near-identical
# because they share most letters, but they are different skills, and one
# wrong grounding silently turns a correct prediction into a false positive
# plus a missed true positive. A variant match instead requires the terms to
# be identical after removing case, punctuation and plural endings, which
# catches "pythons" or "machine-learning" but nothing that changes meaning.

# Every grounding decision made by ground_term() is appended here as
# (raw_term, matched_term_or_None, method) so a run can be audited, e.g.
# printing how many terms were grounded by alias or variant and to what.
GROUNDING_LOG = []


def _tokens(normalized):
    return normalized.replace("-", " ").replace("/", " ").split()


def _variant_key(normalized):
    """Canonical key used for variant matching: lowercase alphanumerics
    (keeping + and # so C++ and C# stay distinct), with a trailing plural
    's' removed from each word of length > 3."""
    cleaned = "".join(ch if (ch.isalnum() or ch in "+#") else " " for ch in normalized)
    tokens = []
    for tok in cleaned.split():
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return " ".join(tokens)


def build_variant_index(normalized_lookup):
    """{variant_key: [entries]} so variant matching can detect ambiguity
    (two vocabulary terms that collapse to the same key)."""
    index = {}
    for norm_term, entry in normalized_lookup.items():
        index.setdefault(_variant_key(norm_term), []).append(entry)
    return index


def ground_term(raw_term, vocabulary, normalized_lookup, variant_index=None):
    """Ground a free-text term to a real vocabulary entry. Returns
    (entry_or_None, method) where method is 'exact', 'alias', 'variant',
    or 'none'.

    Order of trust:
      1. exact normalized match
      2. explicit alias (ALIAS_MAP), only if its target is in the vocabulary
      3. variant match (case/punctuation/plural only), rejected when more
         than one vocabulary term shares the key
    Anything else is dropped rather than force-fit to the nearest string."""
    normalized_raw = normalize_term(raw_term)
    if not normalized_raw:
        return None, "none"

    exact = normalized_lookup.get(normalized_raw)
    if exact is not None:
        GROUNDING_LOG.append((raw_term, exact["term"], "exact"))
        return exact, "exact"

    alias_target = ALIAS_MAP.get(normalized_raw)
    if alias_target is not None:
        entry = normalized_lookup.get(normalize_term(alias_target))
        if entry is not None:
            GROUNDING_LOG.append((raw_term, entry["term"], "alias"))
            return entry, "alias"

    if variant_index is None:
        variant_index = build_variant_index(normalized_lookup)
    candidates = variant_index.get(_variant_key(normalized_raw), [])
    if len(candidates) == 1:
        GROUNDING_LOG.append((raw_term, candidates[0]["term"], "variant"))
        return candidates[0], "variant"

    GROUNDING_LOG.append((raw_term, None, "ambiguous" if candidates else "none"))
    return None, "none"


def fuzzy_match_term(raw_term, vocabulary, normalized_lookup, variant_index=None):
    """Backwards-compatible wrapper around ground_term() that returns just
    the matched vocabulary entry (or None). Despite the historical name,
    this no longer does character-similarity matching; see ground_term()."""
    entry, _method = ground_term(raw_term, vocabulary, normalized_lookup, variant_index)
    return entry
