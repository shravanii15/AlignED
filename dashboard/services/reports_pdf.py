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


NAVY = (30, 58, 138)
INK = (16, 24, 40)
MUTED = (102, 112, 133)
BLUE = (49, 92, 245)
GREEN = (31, 157, 104)
RED = (217, 74, 74)
STATUS_STYLE = {  # status -> (pill fill, text color)
    "Named": ((216, 245, 230), (14, 94, 61)),
    "Rarely named": ((254, 240, 204), (138, 90, 0)),
    "Not named": ((253, 226, 226), (168, 38, 31)),
}


def build_pdf_report(university, program_name, course_count, recs_df, scope_display_name="the overall market",
                     scope_total_postings=None, true_gap_count=None, strengths=None, picture=None):
    """Plain-language skill gap report: a stat-card summary, a clear row-by-row
    view of the skills employers ask for most, the confirmed gaps as cards, and
    what to do next. Two clean pages, 10 to 11 pt text, no statistics jargon."""
    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    pdf = AlignEDReport()
    pdf.set_auto_page_break(auto=False)
    L, W = 15, 180  # left margin and content width (A4 = 210 wide)
    pdf.set_margins(L, 15, L)
    pdf.add_page()

    def txt(x, y, text, size=10, bold=False, color=INK, w=None, align="L", h=6):
        pdf.set_xy(x, y)
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.cell(w if w is not None else pdf.get_string_width(text) + 1, h, text, align=align)

    def paragraph(x, y, w, text, size=10.5, color=INK, bold=False, h=5.6):
        pdf.set_xy(x, y)
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(w, h, text)
        return pdf.get_y()

    def section(y, title, note=None):
        pdf.set_fill_color(*BLUE)
        pdf.rect(L, y + 1, 2.2, 7, style="F")
        txt(L + 5, y, title, size=14, bold=True, color=INK, h=9)
        if note:
            txt(L + 5, y + 9, note, size=9, color=MUTED)
            return y + 17
        return y + 13

    def pill(x, y, text, fill, color, w=None, size=8.5):
        pdf.set_font("Helvetica", "B", size)
        w = w or pdf.get_string_width(text) + 8
        pdf.set_fill_color(*fill)
        pdf.rect(x, y, w, 6.2, style="F", round_corners=True, corner_radius=3)
        txt(x, y, text, size=size, bold=True, color=color, w=w, align="C", h=6.2)
        return w

    gap_count = true_gap_count if true_gap_count is not None else len(recs_df)
    top10 = picture.head(10) if picture is not None else None
    n_named = int((top10["coverage"] > 0).sum()) if top10 is not None and len(top10) else None

    # ---- Header band ----
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 44, style="F")
    txt(L, 10, "Skill Gap Report", size=24, bold=True, color=(255, 255, 255), h=11)
    txt(L, 24, clean(f"{university}, {program_name}"), size=12, color=(220, 228, 255), w=W, h=7)
    txt(L, 32, clean(f"Compared with job postings for: {scope_display_name}   |   {datetime.date.today():%B %d, %Y}"),
        size=9, color=(170, 186, 235), w=W, h=6)

    # ---- Stat cards ----
    cards = []
    if n_named is not None:
        cards.append((f"{n_named} of {len(top10)}", "most-requested skills are named\nin this program's courses"))
    cards.append((str(gap_count), "confirmed skill gap" + ("" if gap_count == 1 else "s")))
    cards.append((str(course_count), "courses compared"))
    cw, gap = (W - 6 * (len(cards) - 1)) / len(cards), 6
    y = 52
    for i, (big, label) in enumerate(cards):
        x = L + i * (cw + gap)
        pdf.set_fill_color(244, 246, 252)
        pdf.rect(x, y, cw, 28, style="F", round_corners=True, corner_radius=3)
        pdf.set_fill_color(*BLUE)
        pdf.rect(x, y, 2.2, 28, style="F")
        txt(x + 7, y + 3, big, size=20, bold=True, color=NAVY, w=cw - 8, h=10)
        pdf.set_xy(x + 7, y + 15)
        pdf.set_text_color(*MUTED)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(cw - 9, 4.2, label)
    y += 36

    # ---- In short box ----
    if top10 is not None and len(top10):
        missing = [clean(n) for n in top10[top10["coverage"] == 0]["canonical_name"].head(5)]
        short = f"Of the {len(top10)} skills employers ask for most, this program's course descriptions name {n_named}."
        if missing:
            short += " Not named at all: " + ", ".join(missing) + "."
    elif gap_count == 0 or recs_df.empty:
        short = "No clear skill gaps were found for this program against this set of jobs."
    else:
        short = f"{gap_count} skills that employers ask for are not named in this program's course descriptions."
    pdf.set_fill_color(234, 240, 255)
    pdf.rect(L, y, W, 30, style="F", round_corners=True, corner_radius=3)
    txt(L + 6, y + 3, "IN SHORT", size=8.5, bold=True, color=BLUE, h=5)
    yy = paragraph(L + 6, y + 9, W - 12, clean(short), size=11, bold=True)
    paragraph(L + 6, yy + 1, W - 12,
              "A skill that is not named may still be taught in class. Course descriptions are short, so use this as a question to ask.",
              size=9, color=MUTED, h=4.6)
    y += 38

    # ---- Row-by-row view ----
    if picture is not None and len(picture):
        y = section(y, "The skills employers ask for most")
        # legend
        pdf.set_fill_color(*BLUE); pdf.rect(L + 5, y + 1.4, 3, 3, style="F")
        txt(L + 10, y, "In job postings", size=9, color=MUTED, h=5.5)
        pdf.set_fill_color(*GREEN); pdf.rect(L + 42, y + 1.4, 3, 3, style="F")
        txt(L + 47, y, "Named in this program's courses", size=9, color=MUTED, h=5.5)
        y += 8
        top = max(float(picture["demand"].max()), float(picture["coverage"].max()), 0.01)
        row_h = 10.5
        bar_x, bar_w = L + 52, 62
        for i, (_, r) in enumerate(picture.head(12).iterrows()):
            if i % 2 == 0:
                pdf.set_fill_color(248, 249, 252)
                pdf.rect(L, y, W, row_h, style="F")
            txt(L + 3, y + 2, clean(r["canonical_name"]), size=11, bold=True, w=46, h=6.5)
            for k, (value, rgb) in enumerate(((r["demand"], BLUE), (r["coverage"], GREEN))):
                by = y + 2 + k * 3.4
                pdf.set_fill_color(226, 231, 243)
                pdf.rect(bar_x, by, bar_w, 2.8, style="F")
                pdf.set_fill_color(*rgb)
                pdf.rect(bar_x, by, max(bar_w * value / top, 0.7 if value > 0 else 0), 2.8, style="F")
            txt(bar_x + bar_w + 4, y + 2, f"{r['demand']*100:.0f}% of jobs", size=9.5, color=MUTED, w=26, h=6.5)
            fill, color = STATUS_STYLE.get(r["status"], ((235, 235, 235), MUTED))
            pill(L + W - 29, y + 2.2, r["status"], fill, color, w=29)
            y += row_h

    # ---- Page 2 ----
    pdf.add_page()
    y = 20
    if len(recs_df):
        y = section(y, "Confirmed gaps", "Big enough to rule out coincidence. These are the strongest places to ask questions.")
        for rank, (_, row) in enumerate(recs_df.head(4).iterrows(), start=1):
            cov, dem = row["program_coverage_rate"] * 100, row["market_demand_rate"] * 100
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(220, 227, 242)
            pdf.rect(L, y, W, 22, style="DF", round_corners=True, corner_radius=3)
            pdf.set_fill_color(*NAVY)
            pdf.ellipse(L + 5, y + 6, 10, 10, style="F")
            txt(L + 5, y + 8, str(rank), size=11, bold=True, color=(255, 255, 255), w=10, align="C", h=6)
            txt(L + 20, y + 3, clean(row["canonical_name"]), size=13, bold=True, w=70, h=7)
            cov_phrase = "no course description names it" if cov == 0 else (
                "fewer than 1% of course descriptions name it" if cov < 1 else f"{cov:.0f}% of course descriptions name it")
            trend = {"rising": "  Demand is rising.", "falling": "  Demand is falling."}.get(row["trend_label"], "")
            txt(L + 20, y + 11, clean(f"In {dem:.0f}% of job postings, but {cov_phrase}.{trend}"), size=9.5, color=MUTED, w=W - 55, h=6)
            pill(L + W - 33, y + 8, f"{dem - cov:.0f}-point gap", (253, 226, 226), (168, 38, 31), w=29)
            y += 26
        y += 4

    if strengths:
        y = section(y, "What this program does name")
        x = L
        for name, count in strengths:
            label = clean(f"{name}  ({count} of {course_count})")
            pdf.set_font("Helvetica", "B", 9.5)
            w = pdf.get_string_width(label) + 10
            if x + w > L + W:
                x, y = L, y + 9
            pill(x, y, label, (216, 245, 230), (14, 94, 61), w=w, size=9.5)
            x += w + 4
        y += 14

    y = section(y, "What to do with this")
    steps = (
        ("Ask the department.", "Is each top skill taught but just not named in the course description?"),
        ("Fill real gaps.", "Look for electives, online courses or projects that cover the skills that are truly missing."),
        ("Check your own fit.", "Use the AlignED Match a Job page to compare your skills with a real job posting."),
    )
    for i, (lead, detail) in enumerate(steps, start=1):
        pdf.set_fill_color(*BLUE)
        pdf.ellipse(L + 2, y + 0.5, 7, 7, style="F")
        txt(L + 2, y + 1, str(i), size=9.5, bold=True, color=(255, 255, 255), w=7, align="C", h=6)
        pdf.set_xy(L + 13, y)
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(pdf.get_string_width(lead) + 2, 7, lead)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(W - 13 - pdf.get_string_width(lead) - 2, 7, detail, align="L")
        y = max(pdf.get_y(), y + 7) + 4

    y += 4
    pdf.set_fill_color(244, 246, 250)
    pdf.rect(L, y, W, 28, style="F", round_corners=True, corner_radius=3)
    txt(L + 6, y + 3, "HOW THIS WAS MADE", size=8, bold=True, color=MUTED, h=5)
    paragraph(
        L + 6, y + 9, W - 12,
        "Skills come from about 250 tools and technologies in the US Department of Labor's O*NET list. A skill counts as present "
        "when its name appears in a course description or job posting. The job postings are a fixed sample, not live data. "
        "Full details are on the AlignED Methodology page.",
        size=8.5, color=MUTED, h=4.4,
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
