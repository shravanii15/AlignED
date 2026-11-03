"""
build_heldout_set.py: sample fresh items and make the labeling spreadsheet.

    python build_heldout_set.py                      # 30 courses + 20 postings, seed 2026

Writes data/heldout/heldout_items.json (what the extractors read) and
data/heldout/labeling_sheet.xlsx (what a human fills in). The sample excludes every item in the
104-item development set. Re-running with the same seed gives the same items; it refuses to
overwrite a sheet that already exists, so labels are never lost by accident (use --force).
"""

import argparse
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.protection import SheetProtection  # noqa: F401  (kept for future locking of read-only columns)

from extract_common import load_vocabulary
from heldout import HELDOUT_DIR, sample_items

INSTRUCTIONS = [
    "How to label (about 1 to 1.5 hours for 50 items)",
    "",
    "1. For each row on the 'Label' sheet, read the text in column E.",
    "2. In the yellow column F, type the skills, knowledge areas and tools the text REALLY requires or teaches.",
    "   Separate them with semicolons, for example:  Python; SQL; Machine Learning; Statistics",
    "3. Only include something if the text is genuinely about it, not a passing mention.",
    "4. Use the standard name. The 'Vocabulary' sheet lists every name the project recognises (use Ctrl+F).",
    "   If the exact name is not in the list, type it anyway; it will be reported and left out of scoring.",
    "5. If nothing applies, type NONE.",
    "6. Do NOT look at what the keyword method or the AI method produced. Label from the text alone.",
    "7. Do not edit columns A to E. Save the file, then tell Claude it is done.",
    "",
    "Why this matters: these labels become the answer key for a fair test of the extraction methods, so they",
    "must be written before anyone sees the methods' answers.",
]


def write_sheet(items, vocabulary, path):
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Instructions"
    for i, line in enumerate(INSTRUCTIONS, start=1):
        ws0.cell(row=i, column=1, value=line)
    ws0["A1"].font = Font(bold=True, size=14)
    ws0.column_dimensions["A"].width = 110

    ws = wb.create_sheet("Label")
    headers = ["item_id", "type", "context", "title", "text", "Skills you find (separate with ;)"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F2A44")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    yellow = PatternFill("solid", fgColor="FFF4C2")
    for r, item in enumerate(items, start=2):
        for c, key in enumerate(["id", "source_type", "context", "title", "text"], start=1):
            cell = ws.cell(row=r, column=c, value=item[key])
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        answer = ws.cell(row=r, column=6)
        answer.fill = yellow
        answer.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = min(409, max(60, 15 * (len(item["text"]) // 95 + 1)))
    for col, width in zip("ABCDEF", (9, 9, 28, 28, 95, 40)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"

    wv = wb.create_sheet("Vocabulary")
    wv.append(["term", "type"])
    for entry in sorted(vocabulary, key=lambda e: e["term"].lower()):
        wv.append([entry["term"], entry["type"]])
    wv.column_dimensions["A"].width = 50
    wb.save(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--courses", type=int, default=30)
    parser.add_argument("--postings", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--force", action="store_true", help="overwrite an existing sheet (destroys any labels in it)")
    args = parser.parse_args(argv)

    os.makedirs(HELDOUT_DIR, exist_ok=True)
    sheet_path = os.path.join(HELDOUT_DIR, "labeling_sheet.xlsx")
    if os.path.exists(sheet_path) and not args.force:
        print(f"{sheet_path} already exists. Refusing to overwrite it (it may contain labels). Use --force to replace it.")
        return 1
    items = sample_items(n_courses=args.courses, n_postings=args.postings, seed=args.seed)
    with open(os.path.join(HELDOUT_DIR, "heldout_items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    write_sheet(items, load_vocabulary(), sheet_path)
    print(f"Wrote {len(items)} items ({args.courses} courses, {args.postings} postings) and {sheet_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
