"""
import_heldout_labels.py: turn the filled-in labeling sheet into the answer key.

    python import_heldout_labels.py                    # strict: stops if any item is blank or any name is not in the vocabulary
    python import_heldout_labels.py --accept-unmatched # names outside the vocabulary are listed and left out of scoring

With --require-review (use it for AI-drafted labels) it refuses unless a human typed OK or FIXED in the review
column for every item.

Writes data/heldout/heldout_labeled.json in the same shape as the development gold set, and
data/heldout/label_review.txt listing every name that could not be matched to the vocabulary.
Names are matched with the same exact / alias / spelling-variant rules the extractors use.
"""

import argparse
import json
import os
import sys

from openpyxl import load_workbook

from extract_common import build_normalized_lookup, build_variant_index, ground_term, load_vocabulary
from heldout import HELDOUT_DIR, parse_skill_cell


def read_cells(path):
    ws = load_workbook(path, data_only=True)["Label"]
    return {row[0].value: row[5].value for row in ws.iter_rows(min_row=2) if row[0].value}


def read_reviews(path):
    """{item_id: text typed in the review column}. The column is optional (older sheets have none)."""
    ws = load_workbook(path, data_only=True)["Label"]
    return {row[0].value: (row[6].value if len(row) > 6 else None) for row in ws.iter_rows(min_row=2) if row[0].value}


def unreviewed(reviews):
    """Ids whose review cell is not OK or FIXED."""
    return sorted(i for i, v in reviews.items() if str(v or "").strip().upper() not in {"OK", "FIXED"})


def build_labels(items, cells, vocabulary):
    """Returns (labeled_items, blank_ids, unmatched) where unmatched maps item_id -> list of unrecognised names."""
    lookup = build_normalized_lookup(vocabulary)
    variants = build_variant_index(lookup)
    labeled, blank, unmatched = [], [], {}
    for item in items:
        names = parse_skill_cell(cells.get(item["id"]))
        if names is None:
            blank.append(item["id"])
            continue
        skills, techs, seen = [], [], set()
        for raw in names:
            entry, _ = ground_term(raw, vocabulary, lookup, variants)
            if entry is None:
                unmatched.setdefault(item["id"], []).append(raw)
                continue
            if entry["term"].lower() in seen:
                continue
            seen.add(entry["term"].lower())
            if entry["type"] == "technology":
                techs.append({"title": entry["term"]})
            else:
                skills.append({"name": entry["term"], "onet_category": entry["type"]})
        labeled.append({"id": item["id"], "source_type": item["source_type"], "identifying_info": item["title"],
                        "essential_skills_or_knowledge": skills, "essential_technologies": techs, "optional": []})
    return labeled, blank, unmatched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--accept-unmatched", action="store_true")
    parser.add_argument("--require-review", action="store_true",
                        help="for AI-drafted labels: refuse unless a human typed OK or FIXED for every item")
    args = parser.parse_args(argv)

    with open(os.path.join(HELDOUT_DIR, "heldout_items.json"), encoding="utf-8") as f:
        items = json.load(f)
    sheet = os.path.join(HELDOUT_DIR, "labeling_sheet.xlsx")
    cells = read_cells(sheet)
    if args.require_review:
        pending = unreviewed(read_reviews(sheet))
        if pending:
            print(f"{len(pending)} item(s) have not been checked by a human yet (column G must say OK or FIXED): {pending}")
            return 4
    labeled, blank, unmatched = build_labels(items, cells, load_vocabulary())

    if blank:
        print(f"{len(blank)} item(s) have no labels yet (type NONE if nothing applies): {blank}")
        return 2
    if unmatched:
        lines = [f"{item_id}: {', '.join(names)}" for item_id, names in unmatched.items()]
        with open(os.path.join(HELDOUT_DIR, "label_review.txt"), "w", encoding="utf-8") as f:
            f.write("Names that are not in the vocabulary (left out of scoring if you accept them):\n" + "\n".join(lines) + "\n")
        print(f"{sum(len(v) for v in unmatched.values())} name(s) are not in the vocabulary, see data/heldout/label_review.txt")
        if not args.accept_unmatched:
            print("Fix the spelling in the sheet, or re-run with --accept-unmatched to leave them out of scoring.")
            return 3
    with open(os.path.join(HELDOUT_DIR, "heldout_labeled.json"), "w", encoding="utf-8") as f:
        json.dump(labeled, f, indent=2)
    total = sum(len(i["essential_skills_or_knowledge"]) + len(i["essential_technologies"]) for i in labeled)
    print(f"Saved answer key: {len(labeled)} items, {total} labeled skills ({total / len(labeled):.1f} per item).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
