"""
services/reports_excel.py: .xlsx export for the Skill Gaps page.

An Excel file should be something you work in, so it opens straight onto a
sortable, filterable table, and adds a side-by-side view of all programs.
Prose explanations belong in the PDF; this file keeps notes to a few lines.

Sheets:
  Skills        the skills employers ask for most, for the selected program
  All programs  the same skills across every program (a heatmap)
  Notes         what each column means
"""

import datetime
import io

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from utils.formatting import evidence_strength

NAVY = "1E3A8A"
STATUS_FILL = {"Named": "D8F5E6", "Rarely named": "FEF0CC", "Not named": "FDE2E2"}
THIN = Side(style="thin", color="E2E8F0")
TREND_WORDS = {"rising": "Rising", "falling": "Falling"}


def _header(cell, fill=NAVY):
    cell.font = Font(bold=True, color="FFFFFF", size=11)
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _title(ws, text, last_col):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    ws["A1"] = text
    ws["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30


def _skills_sheet(wb, university, program_name, course_count, recs_df, picture, scope_name):
    ws = wb.active
    ws.title = "Skills"
    ws.sheet_view.showGridLines = False
    _title(ws, f"{university}, {program_name}", 8)
    ws.merge_cells("A2:H2")
    ws["A2"] = (
        f"{course_count} courses vs job postings for: {scope_name}. Generated {datetime.date.today().isoformat()}. "
        "A skill that is not named may still be taught, so check the syllabus."
    )
    ws["A2"].font = Font(size=9, italic=True, color="64748B")

    headers = ["#", "Skill", "Asked for in jobs", "Named in courses", "Gap (points)",
               "Where the program stands", "Confirmed gap?", "Demand trend"]
    for col, h in enumerate(headers, start=1):
        _header(ws.cell(row=4, column=col, value=h))
    ws.row_dimensions[4].height = 32

    confirmed = {r["canonical_name"]: r for _, r in recs_df.iterrows()} if len(recs_df) else {}
    for i, (_, r) in enumerate(picture.iterrows(), start=1):
        row = 4 + i
        rec = confirmed.get(r["canonical_name"])
        vals = [
            i, r["canonical_name"], r["demand"], r["coverage"], r["gap"] * 100, r["status"],
            "Yes" if rec is not None else "No",
            TREND_WORDS.get(rec["trend_label"], "Steady") if rec is not None else "",
        ]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = Border(bottom=THIN)
            c.alignment = Alignment(vertical="center", horizontal="center" if col in (1, 5, 6, 7, 8) else None)
        ws.cell(row=row, column=2).font = Font(bold=True)
        ws.cell(row=row, column=3).number_format = "0%"
        ws.cell(row=row, column=4).number_format = '[=0]"not named";0.0%'
        ws.cell(row=row, column=5).number_format = '0" pts"'
        ws.cell(row=row, column=6).fill = PatternFill("solid", fgColor=STATUS_FILL.get(r["status"], "E2E8F0"))
        ws.cell(row=row, column=6).font = Font(bold=True)
        if rec is not None:
            ws.cell(row=row, column=7).font = Font(bold=True, color="A8261F")
        ws.row_dimensions[row].height = 24

    last = 4 + len(picture)
    ws.conditional_formatting.add(f"C5:C{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="4C7DFF"))
    ws.conditional_formatting.add(f"D5:D{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="1F9D68"))
    ws.auto_filter.ref = f"A4:H{last}"
    ws.freeze_panes = "C5"
    for col, w in enumerate([5, 22, 20, 20, 15, 26, 16, 15], start=1):
        ws.column_dimensions[get_column_letter(col)].width = w


def _programs_sheet(wb, picture, matrix, courses, selected_label):
    ws = wb.create_sheet("All programs")
    ws.sheet_view.showGridLines = False
    labels = list(matrix.columns)
    _title(ws, "How often each program's courses name the skills employers ask for most", len(labels) + 2)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(labels) + 2)
    ws["A2"] = "Each cell is the share of that program's courses whose description names the skill. The selected program is highlighted."
    ws["A2"].font = Font(size=9, italic=True, color="64748B")

    _header(ws.cell(row=4, column=1, value="Skill"))
    _header(ws.cell(row=4, column=2, value="Asked for in jobs"))
    for j, label in enumerate(labels, start=3):
        _header(ws.cell(row=4, column=j, value=label), fill="C2410C" if label == selected_label else NAVY)
    ws.row_dimensions[4].height = 118

    ws.cell(row=5, column=1, value="Courses analyzed").font = Font(italic=True, color="64748B")
    for j, label in enumerate(labels, start=3):
        c = ws.cell(row=5, column=j, value=int(courses.get(label, 0)))
        c.alignment = Alignment(horizontal="center")
        c.font = Font(italic=True, color="64748B")

    for i, (_, r) in enumerate(picture.iterrows(), start=6):
        ws.cell(row=i, column=1, value=r["canonical_name"]).font = Font(bold=True)
        d = ws.cell(row=i, column=2, value=r["demand"])
        d.number_format = "0%"
        d.alignment = Alignment(horizontal="center")
        for j, label in enumerate(labels, start=3):
            v = matrix.loc[r["skill_id"], label] if r["skill_id"] in matrix.index else 0.0
            c = ws.cell(row=i, column=j, value=float(v))
            c.number_format = '[=0]"-";0%'
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = Border(bottom=THIN)
        ws.row_dimensions[i].height = 22
    last_row = 5 + len(picture)
    last_col = get_column_letter(len(labels) + 2)
    ws.conditional_formatting.add(
        f"C6:{last_col}{last_row}",
        ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="num", end_value=0.2, end_color="1F9D68"),
    )
    ws.conditional_formatting.add(f"B6:B{last_row}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="4C7DFF"))
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 16
    for j in range(3, len(labels) + 3):
        ws.column_dimensions[get_column_letter(j)].width = 16
    ws.freeze_panes = "C6"


def _notes_sheet(wb):
    ws = wb.create_sheet("Notes")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 90
    _title(ws, "Notes", 2)
    rows = [
        ("Asked for in jobs", "Share of the sampled job postings that mention the skill."),
        ("Named in courses", "Share of the program's courses whose description mentions the skill. 'not named' means none does."),
        ("Gap (points)", "Asked for in jobs minus named in courses."),
        ("Where the program stands", "Named: 5% or more of courses. Rarely named: some courses. Not named: no course."),
        ("Confirmed gap?", "Yes means the gap also passed a statistical check that rules out coincidence."),
        ("Important", "Course descriptions are short. A skill that is not named may still be taught."),
        ("Data", "Skills come from the US Department of Labor's O*NET list. Job postings are a fixed sample, not live data."),
    ]
    for i, (k, v) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True, color=NAVY)
        c = ws.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[i].height = 30


def build_excel_report(university, program_name, course_count, recs_df, picture=None, strengths=None,
                       scope_name="all jobs", matrix=None, courses=None, selected_label=None):
    """`picture` is the skills table from services.skill_picture.market_picture.
    `matrix` and `courses` (from program_matrix) add the all-programs sheet."""
    wb = Workbook()
    if picture is None or not len(picture):
        raise ValueError("picture is required: the Excel report is built from the skills table")
    _skills_sheet(wb, university, program_name, course_count, recs_df, picture, scope_name)
    if matrix is not None and courses is not None:
        _programs_sheet(wb, picture, matrix, courses, selected_label)
    _notes_sheet(wb)
    for sheet in wb.worksheets:
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
