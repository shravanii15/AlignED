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


STATUS_FILL = {"Named": "D8F5E6", "Rarely named": "FEF0CC", "Not named": "FDE2E2"}


def _title_bar(ws, text, cols="A1:H1"):
    ws.merge_cells(cols)
    ws[cols.split(":")[0]] = text
    ws[cols.split(":")[0]].font = Font(size=18, bold=True, color="FFFFFF")
    ws[cols.split(":")[0]].fill = PatternFill("solid", fgColor=NAVY)
    ws[cols.split(":")[0]].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34


def _overview_sheet(wb, university, program_name, course_count, recs_df, picture, strengths, scope_name):
    ws = wb.active
    ws.title = "Overview"
    ws.sheet_view.showGridLines = False
    _title_bar(ws, "Does this program teach what employers want?", "A1:F1")
    ws.merge_cells("A2:F2")
    ws["A2"] = f"{university}, {program_name}"
    ws["A2"].font = Font(size=12, bold=True, color="334155")
    ws.merge_cells("A3:F3")
    ws["A3"] = f"{course_count} courses compared with job postings for: {scope_name}  |  Generated {datetime.date.today().isoformat()}"
    ws["A3"].font = Font(size=9, color="64748B")

    top10 = picture.head(10) if picture is not None else None
    lines = []
    if top10 is not None and len(top10):
        named_any = int((top10["coverage"] > 0).sum())
        named_well = int((top10["coverage"] >= 0.05).sum())
        lines.append(f"Of the {len(top10)} skills employers ask for most, this program's course descriptions name {named_any}, and name {named_well} in 5% or more of courses.")
        missing = [str(n) for n in top10[top10["coverage"] == 0]["canonical_name"].head(5)]
        if missing:
            lines.append("Not named in any course description: " + ", ".join(missing) + ".")
    lines.append(
        f"{len(recs_df)} skill gap{'s' if len(recs_df) != 1 else ''} passed a check that rules out coincidence."
        if len(recs_df) else "No single skill gap was strong enough to pass the check that rules out coincidence, so use the full list on the next sheet."
    )
    if strengths:
        lines.append("Most often named in course descriptions: " + ", ".join(f"{n} ({c})" for n, c in strengths) + ".")
    lines.append("A skill that is not named may still be taught in class. Descriptions are short, so ask the department.")
    for i, text in enumerate(lines, start=5):
        ws.merge_cells(f"A{i}:F{i}")
        c = ws[f"A{i}"]
        c.value = text
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.font = Font(size=11, bold=(i == 5))
        ws.row_dimensions[i].height = 36
    for col, w in enumerate([18, 18, 18, 18, 18, 18], start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.merge_cells(f"A{5 + len(lines) + 1}:F{5 + len(lines) + 1}")
    nav = ws[f"A{5 + len(lines) + 1}"]
    nav.value = "Next sheets: Top skills employers want  |  Confirmed gaps  |  How to read this"
    nav.font = Font(size=10, italic=True, color="1E3A8A")


def _picture_sheet(wb, picture):
    ws = wb.create_sheet("Top skills employers want")
    ws.sheet_view.showGridLines = False
    _title_bar(ws, "The skills employers ask for most, and where this program stands", "A1:F1")
    ws.merge_cells("A2:F2")
    ws["A2"] = "Sorted by how often the skill appears in job postings. Green = named in many courses, amber = rarely, red = not named."
    ws["A2"].font = Font(size=10, italic=True, color="64748B")
    headers = ["#", "Skill", "How common in jobs", "Named in courses", "Gap (points)", "Where the program stands"]
    for col, h in enumerate(headers, start=1):
        _header_cell(ws.cell(row=4, column=col, value=h))
    ws.row_dimensions[4].height = 30
    thin = Side(style="thin", color="E2E8F0")
    for i, (_, r) in enumerate(picture.iterrows(), start=1):
        row = 4 + i
        vals = [i, r["canonical_name"], r["demand"], r["coverage"], r["gap"] * 100, r["status"]]
        for col, v in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=col, value=v)
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(vertical="center", horizontal="center" if col in (1, 5, 6) else None)
        ws.cell(row=row, column=2).font = Font(bold=True)
        ws.cell(row=row, column=3).number_format = "0%"
        ws.cell(row=row, column=4).number_format = '[=0]"not named";0.0%'
        ws.cell(row=row, column=5).number_format = '0" pts"'
        status_cell = ws.cell(row=row, column=6)
        status_cell.fill = PatternFill("solid", fgColor=STATUS_FILL.get(r["status"], "E2E8F0"))
        status_cell.font = Font(bold=True)
        ws.row_dimensions[row].height = 26
    last = 4 + len(picture)
    if len(picture):
        ws.conditional_formatting.add(f"C5:C{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="4C7DFF"))
        ws.conditional_formatting.add(f"D5:D{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="1F9D68"))
    for col, w in enumerate([5, 22, 22, 20, 15, 26], start=1):
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.freeze_panes = "C5"


def build_excel_report(university, program_name, course_count, recs_df, picture=None, strengths=None, scope_name="all jobs"):
    wb = Workbook()
    _overview_sheet(wb, university, program_name, course_count, recs_df, picture, strengths, scope_name)
    if picture is not None and len(picture):
        _picture_sheet(wb, picture)
    ws = wb.create_sheet("Confirmed gaps")

    ws.merge_cells("A1:H1")
    ws["A1"] = "Confirmed gaps: skills this program may be missing"
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

    if len(recs_df) == 0:
        ws.merge_cells("A7:H7")
        ws["A7"] = "No single skill gap was strong enough to pass the check. See the 'Top skills employers want' sheet for the full picture."
        ws["A7"].font = Font(italic=True, color="64748B")
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
        ("Where the program stands", "Named = 5% or more of courses name the skill. Rarely named = some courses do. Not named = no course description does."),
        ("Confirmed gaps", "The subset of gaps that passed a check ruling out coincidence. There can be few or none even when many skills are not named."),
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

    for sheet in wb.worksheets:  # print each sheet one page wide, landscape
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        from openpyxl.worksheet.properties import PageSetupProperties
        sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
