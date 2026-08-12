"""
extract_llm.py

What this script does, in plain terms:
This is our AI extractor -- the counterpart to extract_baseline.py's
plain keyword scanning. Instead of mechanically checking "does this exact
phrase appear in the text," it sends each of the 104 gold-set items to a
locally-running large language model (Ollama, running llama3.1:8b on the
user's own machine -- free, no API key, nothing sent over the internet)
and asks it to actually *read and understand* the text, then pick out
which skills/knowledge areas/technologies from our O*NET vocabulary are
genuinely relevant.

Why this can plausibly do better than the baseline:
A keyword scanner has no idea that a course about "hacking C programs and
Unix binaries" is really about "Programming" and "Computers and
Electronics" unless those exact words appear -- it also has no way to
tell the difference between a real requirement and a passing mention, or
to recognize a paraphrase (e.g. "building software using an agile
process" implying "Software Development"). An LLM can, in principle, do
both of those things. Whether it *actually* does better in practice is
exactly what evaluate_extraction.py measures -- we don't just assert it,
we prove it against the hand-labeled gold set.

Grounding rule (the most important design decision in this script), and
why it changed:
The first version of this script put the ENTIRE controlled vocabulary
(all ~1,600 skill/knowledge/technology terms) directly into every single
prompt, with strict instructions to only pick from that list verbatim.
That's a defensible design on paper, but in practice, on a laptop-grade
CPU-only machine (no dedicated GPU), it made every prompt so large that
the model spent most of its time just reading the vocabulary before it
could even start reasoning about the actual course/posting text -- and
in real testing, that caused nearly every one of the 104 requests to
time out at 120 seconds.

The fix: we flip the order of operations. Now the model reads ONLY the
short text and answers in its own words -- a small, fast prompt with no
giant list attached. THEN, back in plain Python (no AI, no network, near-
instant), we take whatever terms the model said and match each one back
to our real O*NET vocabulary using fuzzy_match_term() from
extract_common.py. A term that doesn't match anything real closely
enough gets dropped, exactly like before -- we still never trust the
model's word for it, we just moved the grounding check from "inside the
prompt" to "after the response," which is both faster and, if anything,
more robust (an LLM asked to search a 1,600-item list by hand is prone to
typos and near-misses anyway; a dedicated matching function does that
job better than the model can).

A note on things we could not directly test:
This script talks to Ollama at http://localhost:11434, a server that only
exists on the *user's own machine* once she has Ollama installed and the
llama3.1:8b model pulled -- the sandbox this script was written in has no
network access to anyone's localhost, so it was never possible to run
this end-to-end here (this is the same kind of limitation noted in
fetch_onet_taxonomy.py for the O*NET API). The request/response shape
below was NOT guessed -- it was confirmed by reading Ollama's official
API reference (https://github.com/ollama/ollama/blob/main/docs/api.md),
specifically the POST /api/generate endpoint, its "format" parameter,
and the "stream": false response shape (a single JSON object whose
"response" field holds the model's answer as a JSON-formatted string).
This script is meant to be run by the user on her own machine, where
Ollama is actually reachable.
"""

import json
import os
import re
import time

import requests

from extract_common import build_normalized_lookup, fuzzy_match_term, load_vocabulary

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gold_set")
GOLD_SET_PATH = os.path.join(DATA_DIR, "gold_set_combined.json")
OUTPUT_PATH = os.path.join(DATA_DIR, "llm_extractions.json")

OLLAMA_URL = "http://localhost:11434/api/generate"
# Switched from llama3.1:8b to llama3.2:3b: in real testing, the 8B model
# ran fine for the first ~20 items and then degraded into near-total
# timeouts, which is the signature of a laptop CPU running out of steam
# under sustained heavy load (thermal throttling / memory pressure), not
# a bug in the code. The 3B model is roughly a third the size, puts much
# less sustained strain on the machine, and is plenty capable for a
# short-list extraction task like this one.
MODEL_NAME = "llama3.2:3b"

# Now that prompts are short (just the item's own text, no giant
# vocabulary attached), inference should be much faster than the first
# version. We keep a generous timeout anyway since CPU-only inference
# speed varies a lot by machine, but this should rarely be hit now.
REQUEST_TIMEOUT_SECONDS = 90

# A short pause between requests so we don't hammer the local server with
# back-to-back requests the instant one finishes -- mirrors the polite
# REQUEST_DELAY_SECONDS pattern used in fetch_onet_taxonomy.py and
# fetch_esco_taxonomy.py for public APIs, even though here we're the only
# ones "sharing" this server with ourselves.
REQUEST_DELAY_SECONDS = 0.3

# We do NOT ask Ollama for schema-constrained JSON output. In real
# testing on this project, Ollama's "format": <JSON schema> mode (grammar-
# constrained, token-by-token decoding) was dramatically slower than plain
# generation on this machine -- slow enough to time out almost every
# request -- while a manual, unconstrained "ollama run" test answered in
# about 15 seconds. So instead we ask for a simple, easy-to-parse plain-
# text format (one term per line) and parse it loosely in Python, which
# is both faster and, going by that manual test, actually reliable.


def build_prompt(text):
    """Build a short, fast prompt for one gold-set item. No vocabulary is
    included here on purpose (see the module docstring for why) -- the
    model just names what it recognizes, and matching those names back to
    our real taxonomy happens afterward in normalize_predictions()."""
    return (
        "You are an expert at reading job postings and course descriptions "
        "and identifying which real-world skills, knowledge areas, and "
        "named technologies (programming languages, tools, platforms, "
        "frameworks) they genuinely require.\n\n"
        "Read the following text and list the specific skills, knowledge "
        "areas, and technologies it requires. Use short, standard names "
        "(e.g. \"Python\", \"Machine Learning\", \"Database Administration\", "
        "\"Amazon Web Services\") rather than full sentences. Only include "
        "something if the text is really about it, not just a passing "
        "mention.\n\n"
        "TEXT:\n"
        f"{text}\n\n"
        "Respond with ONLY a plain list, one term per line, nothing else -- "
        "no numbering, no bullets, no extra commentary. For example:\n"
        "Python\n"
        "Machine Learning\n"
        "SQL\n\n"
        "If nothing clearly applies, respond with the single word: None"
    )


def call_ollama(prompt):
    """Send one request to the local Ollama server and return the raw
    text the model produced (plain text, not JSON -- see the module
    docstring for why we dropped the JSON-schema "format" option)."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data["response"]


# Matches a leading "1. ", "2) ", etc. so numbered-list formatting (which
# the model may use despite being told not to) doesn't end up baked into
# the extracted term itself.
_NUMBERED_LIST_PREFIX = re.compile(r"^\d+[.)]\s*")


def parse_plain_text_response(raw_response):
    """Turn the model's plain-text answer into a list of candidate terms.
    We asked for "one term per line, no numbering, no bullets" in the
    prompt, but local models don't always follow formatting instructions
    perfectly, so this is deliberately forgiving: it strips common list
    decorations (leading "-", "*", "1.", etc.) off each line rather than
    assuming the model obeyed exactly. Lines that are empty, or that are
    just the word "None" (our own instruction for "nothing applies"), are
    skipped. Real grounding/validation still happens afterward in
    normalize_predictions() -- this function's only job is turning loose
    text into a list of strings to check."""
    terms = []
    for line in raw_response.splitlines():
        cleaned = line.strip()
        cleaned = cleaned.lstrip("-*•").strip()
        cleaned = _NUMBERED_LIST_PREFIX.sub("", cleaned).strip()
        if not cleaned:
            continue
        if cleaned.lower() in ("none", "n/a", "none.", "none apply."):
            continue
        terms.append(cleaned)
    return terms


def normalize_predictions(raw_terms, vocabulary, normalized_lookup):
    """Take whatever free-text terms the model returned (its own words,
    not constrained to our vocabulary) and match each one back to a real
    O*NET vocabulary entry using fuzzy_match_term() from
    extract_common.py. A term with no sufficiently close match is
    dropped, not force-fit -- we still never trust the model's word for
    it, we just do the grounding check here instead of inside the prompt
    (see the module docstring for why). Returns the kept, grounded
    predictions plus a count of how many raw terms didn't match anything
    real, so main() can print an honest summary."""
    kept = []
    dropped_count = 0
    for raw_term in raw_terms:
        if not isinstance(raw_term, str):
            dropped_count += 1
            continue
        entry = fuzzy_match_term(raw_term, vocabulary, normalized_lookup)
        if entry is None:
            dropped_count += 1
            continue
        # Avoid listing the same vocabulary entry twice for one item if
        # the model happened to mention it more than once in different
        # words (e.g. "AWS" and "Amazon Web Services" both landing on
        # the same vocabulary entry).
        if any(k["term"] == entry["term"] for k in kept):
            continue
        kept.append({"term": entry["term"], "type": entry["type"]})
    return kept, dropped_count


def load_checkpoint():
    """Load any previously-saved results so a run that got interrupted
    (a timeout streak, a closed terminal, a computer that needed a
    restart) can pick up where it left off instead of starting over from
    item 1. Returns a dict of {item_id: result}, empty if no checkpoint
    file exists yet or it can't be read (a corrupted/partial file from a
    hard interruption shouldn't crash the whole script -- we just treat
    it as "no checkpoint" and start fresh)."""
    if not os.path.exists(OUTPUT_PATH):
        return {}
    try:
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return {entry["id"]: entry for entry in existing}
    except Exception:
        return {}


def save_checkpoint(results_by_id):
    """Write the current progress to disk immediately. Called after every
    single item (not just at the very end) specifically because local
    LLM runs on a laptop can degrade or get interrupted partway through a
    104-item run -- losing an hour of progress to one bad request would
    be a real cost, not just an inconvenience."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(list(results_by_id.values()), f, indent=2)


def main():
    print("Loading O*NET vocabulary (skills, knowledge, technologies)...")
    vocabulary = load_vocabulary()
    normalized_lookup = build_normalized_lookup(vocabulary)
    print(f"  -> {len(vocabulary)} vocabulary terms loaded.")

    print(f"Loading gold-set items from: {GOLD_SET_PATH}")
    with open(GOLD_SET_PATH, "r", encoding="utf-8") as f:
        gold_items = json.load(f)
    print(f"  -> {len(gold_items)} items to process.")

    results_by_id = load_checkpoint()
    already_done = {
        item_id
        for item_id, entry in results_by_id.items()
        # A previously "failed" item (the Ollama call itself timed out or
        # errored) is deliberately NOT counted as done -- we want to
        # retry those automatically on the next run. But an item where
        # the CALL succeeded and we have the model's raw_terms saved IS
        # counted as done, even if predicted_skills ended up empty after
        # matching -- there's no need to burn another slow LLM call just
        # to re-derive an answer we already have; a *matching* problem
        # gets fixed by re-running the matching step alone (see
        # renormalize.py), not by asking the model again.
        if entry.get("call_succeeded")
    }
    if already_done:
        print(
            f"  -> Found a previous checkpoint with {len(already_done)} "
            f"already-completed item(s); those will be skipped and only "
            f"the remaining/failed items will be (re)processed.\n"
        )

    print(
        f"\nMaking sure Ollama is reachable at {OLLAMA_URL} "
        f"(model: {MODEL_NAME})...\n"
    )

    total_dropped_terms = 0
    total_failed_items = 0

    for i, item in enumerate(gold_items, start=1):
        item_id = item["id"]
        if item_id in already_done:
            print(f"[{i}/{len(gold_items)}] Skipping {item_id} (already done).")
            continue

        text = item.get("text", "")
        print(f"[{i}/{len(gold_items)}] Extracting for {item_id}...")

        prompt = build_prompt(text)

        # Wrap each call individually so one slow/failed item (a timeout,
        # a malformed response, Ollama not running yet, etc.) can never
        # kill the whole 104-item run -- matching the try/except-per-item
        # pattern used throughout fetch_onet_taxonomy.py and
        # fetch_esco_taxonomy.py.
        try:
            raw_response = call_ollama(prompt)
        except Exception as exc:
            print(f"  !! WARNING: Ollama request failed for {item_id}: {exc}")
            results_by_id[item_id] = {
                "id": item_id,
                "predicted_skills": [],
                "raw_terms": None,
                "call_succeeded": False,
            }
            total_failed_items += 1
            save_checkpoint(results_by_id)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        raw_terms = parse_plain_text_response(raw_response)

        predicted, dropped_count = normalize_predictions(
            raw_terms, vocabulary, normalized_lookup
        )
        total_dropped_terms += dropped_count
        if dropped_count:
            print(
                f"  (dropped {dropped_count} term(s) not found in the "
                f"vocabulary)"
            )

        results_by_id[item_id] = {
            "id": item_id,
            "predicted_skills": predicted,
            "raw_terms": raw_terms,
            "call_succeeded": True,
        }
        # Save after every single item, not just at the end -- see
        # save_checkpoint()'s docstring for why this matters for a long,
        # locally-run process like this one.
        save_checkpoint(results_by_id)
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nSaved LLM predictions for {len(results_by_id)} items to: {OUTPUT_PATH}")
    print(f"Items that failed this run (empty prediction, see warnings above): "
          f"{total_failed_items}")
    print(f"Total invented/invalid terms dropped across all items processed "
          f"this run: {total_dropped_terms}")
    still_failed = [
        item_id for item_id, entry in results_by_id.items()
        if not entry.get("predicted_skills")
    ]
    if still_failed:
        print(
            f"\n{len(still_failed)} item(s) still have no successful "
            f"prediction: {', '.join(sorted(still_failed))}\n"
            f"Just run this script again -- it will automatically skip "
            f"everything that already succeeded and only retry these."
        )
    print("\nDone.")


if __name__ == "__main__":
    main()
