"""
services/reports_excel.py: plain-language .xlsx export for the Skill Gaps page.

Two sheets: "Skills to learn" (one row per skill with data bars so the gap
can be seen at a glance) and "How to read this" (what each column means and
what to do next). Numbers stay real numbers, so the sheet is still easy to
sort and filter. No statistics jargon in the visible columns.
"""

import datetime
import io

from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from utils.formatting import evidence_strength

NAVY = "1E3A8A"
TREND_WORDS = {"rising": "Rising", "falling": "Falling"}


def _header_cell(cell):
    cell.font = Font(bold=True, color="FFFFFF", size=11)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def build_excel_report(university, program_name, course_count, recs_df):
    wb = Workbook()
    ws = wb.active
    ws.title = "Skills to learn"

    ws.merge_cells("A1:H1")
    ws["A1"] = "Skills this program may be missing"
    ws["A1"].font = Font(size=18, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34

    ws.merge_cells("A2:H2")
    ws["A2"] = f"{university}, {program_name}"
    ws["A2"].font = Font(size=12, bold=True, color="334155")

    ws.merge_cells("A3:H3")
    ws["A3"] = (
        f"{course_count} courses compared with a sample of tech job postings  |  "
        f"Generated {datetime.date.today().isoformat()}"
    )
    ws["A3"].font = Font(size=9, color="64748B")

    ws.merge_cells("A4:H4")
    ws["A4"] = (
        "A skill listed here appears in job postings but is not named in this program's course descriptions. "
        "It may still be taught in class, so use this list to ask questions, not to judge the program."
    )
    ws["A4"].font = Font(size=10, italic=True, color="7C2D12")
    ws["A4"].fill = PatternFill("solid", fgColor="FFF7ED")
    ws["A4"].alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[4].height = 34

    headers = ["#", "Skill", "How common in jobs", "Named in courses", "Gap (points)",
               "Demand trend", "How sure are we", "What this means"]
    header_row = 6
    for col, h in enumerate(headers, start=1):
        _header_cell(ws.cell(row=header_row, column=col, value=h))
    ws.row_dimensions[header_row].height = 30

    thin = Side(style="thin", color="E2E8F0")
    for i, (_, row) in enumerate(recs_df.iterrows(), start=1):
        r = header_row + i
        values = [
            i,
            row["canonical_name"],
            row["market_demand_rate"],
            row["program_coverage_rate"],
            row["gap_value"] * 100,
            TREND_WORDS.get(row["trend_label"], "Steady"),
            evidence_strength(row["q_value"]) if "q_value" in row else "",
            row["rationale"] if "rationale" in row else "",
        ]
        for col, v in enumerate(values, start=1):
            cell = ws.cell(row=r, column=col, value=v)
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(vertical="center", wrap_text=(col == 8), horizontal="center" if col in (1, 5, 6, 7) else None)
        ws.cell(row=r, column=2).font = Font(bold=True, size=11)
        ws.cell(row=r, column=3).number_format = "0%"
        ws.cell(row=r, column=4).number_format = '[=0]"not named";0.0%'
        ws.cell(row=r, column=5).number_format = '0" pts"'
        ws.row_dimensions[r].height = 48

    last = header_row + len(recs_df)
    if len(recs_df):
        ws.conditional_formatting.add(f"C{header_row + 1}:C{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="4C7DFF"))
        ws.conditional_formatting.add(f"D{header_row + 1}:D{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="1F9D68"))
        ws.conditional_formatting.add(f"E{header_row + 1}:E{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="D94A4A"))

    for col, w in enumerate([5, 20, 22, 20, 15, 14, 16, 70], start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = f"C{header_row + 1}"
    ws.sheet_view.showGridLines = False

    # ---- Second sheet: how to read it ----
    guide = wb.create_sheet("How to read this")
    guide.sheet_view.showGridLines = False
    guide.column_dimensions["A"].width = 24
    guide.column_dimensions["B"].width = 95
    guide.merge_cells("A1:B1")
    guide["A1"] = "How to read this report"
    guide["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    guide["A1"].fill = PatternFill("solid", fgColor=NAVY)
    guide.row_dimensions[1].height = 30
    rows = [
        ("How common in jobs", "Share of the job postings we looked at that mention the skill."),
        ("Named in courses", "Share of this program's courses whose description mentions the skill. 'not named' means no description does."),
        ("Gap (points)", "How far apart those two numbers are. A bigger gap means a bigger mismatch."),
        ("Demand trend", "Whether the skill has been asked for more or less often recently. 'Steady' means no clear change."),
        ("How sure are we", "How unlikely the gap is to be a coincidence. Very strong, Strong and Moderate are all real differences."),
        ("Important", "Course descriptions are short. A skill that is not named may still be taught. Check the syllabus."),
        ("What to do next", "Ask the department about the top skills, look for electives, online courses or projects that cover them, and use the AlignED Match a Job page to compare your own skills with a real posting."),
        ("Where the data comes from", "Skills come from the US Department of Labor's O*NET list. Job postings are a fixed sample, not live data."),
    ]
    for i, (k, v) in enumerate(rows, start=3):
        guide.cell(row=i, column=1, value=k).font = Font(bold=True, color="1E3A8A")
        c = guide.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        guide.cell(row=i, column=1).alignment = Alignment(vertical="top")
        guide.row_dimensions[i].height = 36

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
