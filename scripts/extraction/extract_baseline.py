"""
extract_baseline.py

What this script does, in plain terms:
This is our "dumb but honest" extractor -- the classical, non-AI baseline
that the LLM extractor (extract_llm.py) has to beat in order for us to be
able to claim "the AI approach is actually worth the extra cost/complexity."
It does nothing clever: for each of the 104 gold-set items, it scans the
raw text for every term in our O*NET vocabulary (57 skills/knowledge areas
+ ~1,569 named technologies) using plain case-insensitive phrase matching,
and records every term that literally appears in the text.

Why build this at all, if it's "dumb"?
Because the whole point of this project phase is a *comparison*. Anyone
can say "I built an AI extractor." A much stronger claim is "I built an
AI extractor and proved, on a hand-labeled gold set, that it beats simple
keyword matching by X points of F1." This script is what makes that
second, stronger claim possible -- it's the yardstick, not the product.

How the matching works:
We look for each vocabulary term as a whole phrase inside the text,
ignoring case, using a regex with boundaries on both sides so that (for
example) the term "Java" does not incorrectly match inside the word
"JavaScript", but a term containing symbols like "C++" or "C#" is still
matched correctly (Python's built-in \\b word-boundary marker gets
confused by symbol characters, so we build our own boundary check instead
-- see build_match_pattern() below for exactly why). Multi-word terms
like "Complex Problem Solving" or "Amazon Web Services AWS SageMaker" are
matched as one continuous phrase, not as separate words that happen to
both appear somewhere in the text.

What this baseline deliberately does NOT do:
- No stemming, no plural-handling, no synonym recognition (e.g. it will
  not connect "JS" with "JavaScript" unless "JS" is itself a vocabulary
  term).
- No understanding of context -- if the text mentions a term only in
  passing, or even in a negated sense ("no Python experience required"),
  the baseline still counts it as "found." This is exactly the kind of
  shallow behavior we expect the LLM to improve on, and is the whole
  reason the comparison is interesting.
- No essential/optional distinction -- the gold-standard labels split
  skills into essential vs. optional, but a keyword scanner has no way to
  judge importance, so this script only reports "found in text" vs. "not
  found."
"""

import json
import os
import re

from extract_common import load_vocabulary, normalize_term

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gold_set")
GOLD_SET_PATH = os.path.join(DATA_DIR, "gold_set_combined.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "baseline_extractions.json")


def build_combined_pattern(vocabulary_terms):
    """Compile ALL vocabulary terms into a single regex with alternation,
    instead of one separate compiled pattern per term. This is functionally
    identical to calling build_match_pattern() + .search() once per term --
    same boundary rules, same case-insensitivity -- but roughly 10x faster
    in practice, because Python's regex engine only has to scan across the
    text once per document instead of once per document *per vocabulary
    term* (with ~1,600 terms, that's the difference between ~1,600 passes
    over the text and 1 pass). This matters once we're scanning thousands
    of documents (courses + job postings) instead of just the 104-item
    gold set, where the per-term overhead was small enough not to matter.

    Longer terms are placed first in the alternation so that, for
    overlapping options, the regex engine prefers matching the longer,
    more specific phrase at a given position (Python's alternation tries
    options left-to-right and uses the first that matches)."""
    terms_sorted = sorted(vocabulary_terms, key=len, reverse=True)
    escaped = [re.escape(t) for t in terms_sorted]
    pattern = r"(?<![A-Za-z0-9_])(" + "|".join(escaped) + r")(?![A-Za-z0-9_])"
    return re.compile(pattern, re.IGNORECASE)


def extract_terms_from_text_fast(text, combined_pattern, term_lookup):
    """Faster equivalent of extract_terms_from_text() using a single
    combined regex (see build_combined_pattern()) instead of one pattern
    per vocabulary term. term_lookup maps a normalized matched string back
    to its {"term", "type"} vocabulary entry."""
    found = {}
    for m in combined_pattern.finditer(text):
        key = normalize_term(m.group(0))
        entry = term_lookup.get(key)
        if entry is not None:
            found[key] = entry
    return list(found.values())


def build_match_pattern(term):
    """Compile a case-insensitive regex that matches `term` as a whole
    phrase inside a larger block of text.

    We can't just use Python's \\b ("word boundary") marker on both sides
    of the term, because \\b is defined in terms of "word characters"
    (letters, digits, underscore) -- it breaks down for vocabulary terms
    that start or end with symbols, e.g. "C++", "C#", "Node.js", or
    ".NET". For "C++", a trailing \\b would actually land right after the
    "C" (since neither "+" character counts as a word character), so
    "C++" would wrongly match inside a larger word like "Concurrency" but
    also might not require a real boundary after the "++".

    Instead we build our own boundary check with lookaround assertions:
    "the character immediately before/after the match, if any, must NOT
    be a letter, digit, or underscore." That correctly treats symbols,
    spaces, and punctuation as valid boundaries on both sides, so "C++"
    matches whole in "expertise in C++ programming" but "Java" does not
    incorrectly match inside "JavaScript"."""
    escaped = re.escape(term)
    pattern = r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])"
    return re.compile(pattern, re.IGNORECASE)


def extract_terms_from_text(text, vocabulary_with_patterns):
    """Scan one piece of text and return every vocabulary entry whose
    term appears literally in it (case-insensitive whole-phrase match)."""
    found = []
    for entry, pattern in vocabulary_with_patterns:
        if pattern.search(text):
            found.append({"term": entry["term"], "type": entry["type"]})
    return found


def main():
    print("Loading O*NET vocabulary (skills, knowledge, technologies)...")
    vocabulary = load_vocabulary()
    print(f"  -> {len(vocabulary)} vocabulary terms loaded.")

    # Longer, more specific multi-word terms are compiled the same way as
    # short ones -- regex boundary matching already prevents a short term
    # from accidentally matching inside a longer word, so no extra
    # "longest match wins" sorting is needed here. We do de-duplicate by
    # normalized term first though, in case the taxonomy files ever ended
    # up with the exact same term listed twice under different types.
    seen = set()
    vocabulary_with_patterns = []
    for entry in vocabulary:
        key = normalize_term(entry["term"])
        if key in seen:
            continue
        seen.add(key)
        vocabulary_with_patterns.append((entry, build_match_pattern(entry["term"])))

    print(f"Loading gold-set items from: {GOLD_SET_PATH}")
    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_items = json.load(f)
    print(f"  -> {len(gold_items)} items to process.")

    results = []
    total_predictions = 0
    for item in gold_items:
        text = item.get("text", "")
        predicted = extract_terms_from_text(text, vocabulary_with_patterns)
        total_predictions += len(predicted)
        results.append({"id": item["id"], "predicted_skills": predicted})

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    avg = total_predictions / len(gold_items) if gold_items else 0
    print(f"\nSaved baseline predictions for {len(results)} items to: {OUTPUT_PATH}")
    print(f"Total terms matched across all items: {total_predictions}")
    print(f"Average matched terms per item: {avg:.1f}")
    print("\nDone.")


if __name__ == "__main__":
    main()
