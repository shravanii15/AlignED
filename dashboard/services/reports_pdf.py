"""
services/reports_pdf.py: branded PDF exports (program-level and
personalized profile reports).

Both reports share the same AlignEDReport base class (so every page
gets a consistent branded footer for free) and the same general layout
style: a navy title block, an executive summary, a real data table, an
"explained + evidence" callout section, and a closing methodology/
sources note, built to look like something you'd actually hand to a
curriculum committee or keep for yourself, not a plain text dump, and
auditable rather than just a list of numbers to trust blindly.
"""

import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from utils.constants import TIER_RGB


class AlignEDReport(FPDF):
    """A small FPDF subclass so every page automatically gets the same
    branded footer (page number + generation date), instead of hand-adding
    it after every add_page() call."""

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"AlignED  |  Generated {datetime.date.today().isoformat()}  |  Page {self.page_no()}", align="C")


def build_pdf_report(university, program_name, course_count, recs_df, scope_display_name="the overall market",
                     scope_total_postings=None, true_gap_count=None, strengths=None, picture=None):
    """Plain-language skill gap report for one program.

    Written for students, parents and faculty, not statisticians: it opens
    with the answer, shows the top skills with simple bars, lists the rest
    in a small table, says what to do next, and keeps the method to one
    short note. `strengths` is an optional list of (skill, n_courses)
    naming what the program's course descriptions do mention."""
    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    def write_line(text, size=10, bold=False, color=(20, 20, 20), h=6):
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(0, h, text)
        pdf.set_x(pdf.l_margin)

    def heading(text):
        if pdf.get_y() > pdf.h - 50:  # keep a heading together with its content
            pdf.add_page()
            pdf.set_y(20)
        pdf.ln(4)
        write_line(text, size=13, bold=True, color=(30, 58, 138))
        pdf.ln(1)

    pdf = AlignEDReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title block
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, pdf.w, 34, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, "Does this program teach what employers want?")
    pdf.set_xy(pdf.l_margin, 21)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, clean(f"{university}, {program_name}"))
    pdf.set_y(42)

    gap_count = true_gap_count if true_gap_count is not None else len(recs_df)
    postings_n = scope_total_postings or 0
    write_line(
        f"Generated {datetime.date.today().isoformat()}  |  {course_count} courses compared with "
        f"{postings_n or 'a sample of'} tech job postings ({clean(scope_display_name)})",
        size=9, color=(90, 90, 90),
    )

    # ---- The short answer ----
    heading("The short answer")
    top10 = picture.head(10) if picture is not None else None
    if top10 is not None and len(top10):
        named_any = int((top10["coverage"] > 0).sum())
        write_line(
            f"Of the {len(top10)} skills employers ask for most, this program's course descriptions name {named_any}.",
            size=13, bold=True,
        )
        missing = [clean(n) for n in top10[top10["coverage"] == 0]["canonical_name"].head(5)]
        if missing:
            pdf.ln(1)
            write_line("Not named in any course description: " + ", ".join(missing) + ".", size=10.5)
    elif gap_count == 0 or recs_df.empty:
        write_line("No clear skill gaps were found for this program against this set of jobs.", size=12, bold=True)
    else:
        write_line(f"{gap_count} skills that employers ask for are not named in this program's course descriptions.", size=12, bold=True)
    pdf.ln(1)
    write_line(
        "Important: a skill missing from a course description may still be taught in class. Descriptions are short, "
        "so treat each gap as a question to ask, not a verdict.",
        size=9.5, color=(90, 90, 90),
    )

    # ---- Where the program stands on the most requested skills ----
    if picture is not None and len(picture):
        heading("The skills employers ask for most")
        write_line(
            "Blue is how often the skill appears in job postings. Green is how often it is named in this program's course descriptions.",
            size=9, color=(100, 100, 100),
        )
        pdf.ln(2)
        label_x = pdf.l_margin
        bar_x = pdf.l_margin + 34
        bar_w = 78
        status_rgb = {"Named": (22, 120, 80), "Rarely named": (176, 110, 0), "Not named": (190, 50, 50)}
        top = max(float(picture["demand"].max()), float(picture["coverage"].max()), 0.01)
        for _, r in picture.head(12).iterrows():
            if pdf.get_y() > pdf.h - 30:
                pdf.add_page()
                pdf.set_y(20)
            y = pdf.get_y()
            pdf.set_xy(label_x, y)
            pdf.set_text_color(20, 20, 20)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(33, 6, clean(r["canonical_name"]))
            for k, (value, rgb) in enumerate(((r["demand"], (49, 92, 245)), (r["coverage"], (31, 157, 104)))):
                by = y + 0.8 + k * 3.4
                pdf.set_fill_color(227, 232, 244)
                pdf.rect(bar_x, by, bar_w, 2.7, style="F")
                pdf.set_fill_color(*rgb)
                pdf.rect(bar_x, by, max(bar_w * value / top, 0.6 if value > 0 else 0), 2.7, style="F")
            pdf.set_xy(bar_x + bar_w + 3, y)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(22, 6, f"{r['demand']*100:.0f}% of jobs")
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*status_rgb.get(r["status"], (60, 60, 60)))
            pdf.cell(26, 6, r["status"])
            pdf.set_y(y + 8)
        pdf.set_x(pdf.l_margin)

    # ---- Confirmed gaps with simple bars ----
    if len(recs_df):
        heading("Confirmed gaps: skills to look for first")
        write_line(
            "These gaps are big enough to rule out coincidence. Blue is jobs, green is courses.",
            size=9, color=(100, 100, 100),
        )
        pdf.ln(2)
    bar_x = pdf.l_margin + 38
    bar_w = 90
    for rank, (_, row) in enumerate(recs_df.head(5).iterrows(), start=1):
        if pdf.get_y() > pdf.h - 55:
            pdf.add_page()
            pdf.set_y(20)
        cov = row["program_coverage_rate"] * 100
        dem = row["market_demand_rate"] * 100
        top = max(dem, cov, 1)
        y = pdf.get_y()
        pdf.set_fill_color(30, 58, 138)
        pdf.ellipse(pdf.l_margin, y + 1, 7, 7, style="F")
        pdf.set_xy(pdf.l_margin, y + 2)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(7, 5, str(rank), align="C")
        pdf.set_xy(pdf.l_margin + 11, y + 1)
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(60, 7, clean(row["canonical_name"]))
        y += 10
        for label, value, rgb in (("In job postings", dem, (49, 92, 245)), ("In courses", cov, (31, 157, 104))):
            pdf.set_xy(pdf.l_margin + 11, y)
            pdf.set_text_color(90, 90, 90)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.cell(27, 5, label)
            pdf.set_fill_color(227, 232, 244)
            pdf.rect(bar_x, y + 0.8, bar_w, 3.4, style="F")
            pdf.set_fill_color(*rgb)
            pdf.rect(bar_x, y + 0.8, max(bar_w * value / top, 0.8 if value > 0 else 0), 3.4, style="F")
            pdf.set_xy(bar_x + bar_w + 3, y)
            pdf.set_text_color(20, 20, 20)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.cell(30, 5, "not named" if cov == 0 and label == "In courses" else (f"{value:.0f}%" if value >= 1 or value == 0 else "<1%"))
            y += 5.5
        pdf.set_xy(pdf.l_margin + 11, y + 0.5)
        pdf.set_text_color(90, 90, 90)
        pdf.set_font("Helvetica", "", 8.5)
        trend = {"rising": " Demand has been rising.", "falling": " Demand has been falling."}.get(row["trend_label"], "")
        pdf.multi_cell(0, 4.5, clean(f"{dem - cov:.0f}-point gap.{trend}"))
        pdf.set_x(pdf.l_margin)
        pdf.ln(4)

    # ---- What the program does name ----
    if strengths:
        heading("What this program does name")
        names = ", ".join(f"{clean(n)} ({c} of {course_count} courses)" for n, c in strengths)
        write_line(names, size=10)

    # ---- Full list ----
    if len(recs_df) > 5:
        heading(f"The other {len(recs_df) - 5} gaps" + (f" (of {gap_count} found)" if gap_count > len(recs_df) else ""))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(20, 20, 20)
        with pdf.table(col_widths=(60, 40, 40, 30), text_align="LEFT", line_height=6,
                       headings_style=FontFace(emphasis="BOLD", fill_color=(30, 58, 138), color=(255, 255, 255))) as table:
            header = table.row()
            for h in ("Skill", "In job postings", "In courses", "Gap"):
                header.cell(h)
            for _, row in recs_df.iloc[5:].iterrows():
                r = table.row()
                r.cell(clean(row["canonical_name"]))
                r.cell(f"{row['market_demand_rate']*100:.0f}%")
                r.cell("not named" if row["program_coverage_rate"] == 0 else f"{row['program_coverage_rate']*100:.1f}%")
                r.cell(f"{row['gap_value']*100:.0f} points")

    # ---- Next steps ----
    heading("What to do with this")
    for step in (
        "Check the syllabus or ask the department: is each top skill taught but not named in the description?",
        "For skills that are really missing, look for electives, online courses or projects that cover them.",
        "Use the AlignED Match a Job page to compare your own skills with a specific job posting.",
    ):
        write_line(clean(f"-  {step}"), size=10, color=(40, 40, 40))

    # ---- One short note on method ----
    pdf.ln(4)
    write_line(
        "How this was made: skills come from a list of about 250 tools and technologies in the US Department of Labor's O*NET "
        "database. A skill counts as present when its name appears in a course description or job posting. "
        "Differences shown passed a statistical check that rules out chance. The job postings are a fixed sample, "
        "not live data. Full details are on the AlignED Methodology page.",
        size=8, color=(130, 130, 130), h=4.5,
    )

    return bytes(pdf.output())


def build_profile_pdf_report(role_matches_df, top_role_label, have_df, missing_df, sample_postings_df):
    """A personalized career-style PDF: which real roles best fit this
    person's background, their strengths and gaps for the top match, and
    real example job postings pulled from that role, built with the
    same branded report style as the program-level PDF, so the two feel
    like the same product."""
    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    def write_line(text, size=10, bold=False, color=(20, 20, 20)):
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(0, 6, text)
        pdf.set_x(pdf.l_margin)

    pdf = AlignEDReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, pdf.w, 32, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "AlignED: Your Personalized Career Report")
    pdf.set_xy(pdf.l_margin, 20)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, clean(f"Best-matching role: {top_role_label}"))
    pdf.set_y(40)

    write_line(f"Generated {datetime.date.today().isoformat()}", size=9, color=(90, 90, 90))
    pdf.ln(6)
    pdf.set_x(pdf.l_margin)

    write_line("How your background matches real job roles", size=13, bold=True, color=(30, 58, 138))
    write_line(
        clean(
            "\"Covered\" means your pasted text matched that many of a role's most in-demand tracked skills. "
            "It is a simple overlap count against job-posting data, not a fit score or probability."
        ),
        size=8.5, color=(100, 100, 100),
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(20, 20, 20)
    has_counts = "skills_covered" in role_matches_df.columns and "n_core_skills" in role_matches_df.columns
    with pdf.table(col_widths=(80, 40), text_align="LEFT", line_height=6,
                   headings_style=FontFace(emphasis="BOLD", fill_color=(30, 58, 138), color=(255, 255, 255))) as table:
        header_row = table.row()
        header_row.cell("Role")
        header_row.cell("Skills Covered")
        for _, row in role_matches_df.head(6).iterrows():
            data_row = table.row()
            data_row.cell(clean(row["role_label"]))
            if has_counts:
                data_row.cell(f"{row['skills_covered']} of {row['n_core_skills']}")
            else:
                data_row.cell(f"{row['match_score']*100:.0f}%")

    pdf.ln(6)
    pdf.set_x(pdf.l_margin)
    write_line(f"Your strengths for {top_role_label}", size=13, bold=True, color=(22, 163, 74))
    strengths_text = ", ".join(have_df["canonical_name"].head(10)) if not have_df.empty else "None matched yet. Add more detail to your profile text."
    write_line(clean(strengths_text), size=10)

    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    write_line(f"Skills to prioritize for {top_role_label}", size=13, bold=True, color=(220, 38, 38))
    gaps_text = ", ".join(missing_df["canonical_name"].head(10)) if not missing_df.empty else "No major gaps found."
    write_line(clean(gaps_text), size=10)

    if not sample_postings_df.empty:
        pdf.ln(6)
        pdf.set_x(pdf.l_margin)
        write_line("Example real job openings matching this role", size=13, bold=True, color=(30, 58, 138))
        for _, row in sample_postings_df.head(6).iterrows():
            write_line(clean(f"-  {row['title']} ({row['company']})"), size=9.5, color=(60, 60, 60))

    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    write_line(
        clean(
            "How this was matched: simple keyword matching against your pasted text, the same fast "
            "method used for the full-scale program analysis elsewhere in AlignED, benchmarked against an "
            "AI extraction method on a 104-item test set. It can miss skills phrased differently than "
            "expected. Full methodology on the live dashboard."
        ),
        size=8, color=(130, 130, 130),
    )

    return bytes(pdf.output())


def build_match_pdf_report(have, missing, n_total):
    """One-page learning plan for a pasted job posting.

    `have` is a list of skill names the person already has. `missing` is a
    list of (skill_name, demand_rate) tuples, already ordered with the
    most common first."""
    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    def write_line(text, size=10, bold=False, color=(20, 20, 20)):
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(0, 6, text)
        pdf.set_x(pdf.l_margin)

    pdf = AlignEDReport()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, pdf.w, 32, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "AlignED: Your Job Match Plan")
    pdf.set_xy(pdf.l_margin, 20)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"You have {len(have)} of the {n_total} skills this job asks for")
    pdf.set_y(40)

    write_line(f"Generated {datetime.date.today().isoformat()}", size=9, color=(90, 90, 90))
    pdf.ln(4)
    write_line("Skills you already have", size=13, bold=True, color=(22, 163, 74))
    write_line(clean(", ".join(have)) if have else "None detected yet.", size=10)

    pdf.ln(4)
    write_line("Learn these first", size=13, bold=True, color=(220, 38, 38))
    write_line(
        "Ordered by how often each skill appears across the 1,660 tech job postings in the AlignED sample, "
        "so the first ones help with the most jobs.",
        size=8.5, color=(100, 100, 100),
    )
    if missing:
        for rank, (name, demand) in enumerate(missing, start=1):
            write_line(clean(f"{rank}.  {name}  (in {demand * 100:.0f}% of postings)"), size=10.5)
    else:
        write_line("Nothing missing. You cover every skill we detected in this posting.", size=10)

    pdf.ln(6)
    write_line(
        "Skills are matched by name against about 250 tools and technologies from the US Department of Labor's "
        "O*NET database. Soft skills and skills phrased in other words can be missed.",
        size=8, color=(130, 130, 130),
    )
    return bytes(pdf.output())
