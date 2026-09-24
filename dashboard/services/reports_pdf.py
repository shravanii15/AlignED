"""
services/reports_pdf.py -- branded PDF exports (program-level and
personalized profile reports).

Both reports share the same AlignEDReport base class (so every page
gets a consistent branded footer for free) and the same general layout
style: a navy title block, an executive summary, a real data table, an
"explained + evidence" callout section, and a closing methodology/
sources note -- built to look like something you'd actually hand to a
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


def build_pdf_report(university, program_name, course_count, recs_df, scope_display_name="the overall market", scope_total_postings=None, true_gap_count=None):
    """Build a proper report-style PDF: a colored title block, an
    executive summary, a clean data table (not a wall of repeated
    sentences), a "top priorities, explained" section with the real
    evidence behind each one, and a closing methodology/sources note --
    meant to look like something you'd actually hand to a curriculum
    committee, not a boring text dump, and to stand on its own without
    requiring the dashboard to interpret."""
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

    # Title block: a filled navy header bar.
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, pdf.w, 32, style="F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "AlignED -- Curriculum Gap Report")
    pdf.set_xy(pdf.l_margin, 20)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, clean(f"{university} -- {program_name}"))
    pdf.set_y(40)

    n_high = (recs_df["priority_tier"] == "high").sum()
    n_rising = (recs_df["trend_label"] == "rising").sum()
    postings_note = f"{scope_total_postings} postings analyzed in this scope" if scope_total_postings else "postings analyzed"
    # true_gap_count is the actual count of significant rows in gap_scores;
    # recs_df is capped at MAX_RECOMMENDATIONS_PER_PROGRAM (10) per
    # program+scope in generate_recommendations.py, so the two can differ
    # for programs with more than 10 significant gaps. Fall back to
    # len(recs_df) only if the caller didn't pass the real count.
    gap_count = true_gap_count if true_gap_count is not None else len(recs_df)
    capped = gap_count > len(recs_df)

    # Executive summary -- a plain-English paragraph stating exactly what
    # this report measures and how, so it stands on its own even if
    # printed and handed to someone who's never seen the dashboard.
    write_line("Executive summary", size=13, bold=True, color=(30, 58, 138))
    write_line(
        clean(
            f"This report compares {university} -- {program_name}'s curriculum ({course_count} courses) "
            f"against {scope_display_name} ({postings_note}). Of the skills tested, {gap_count} showed a "
            f"statistically significant gap after a Benjamini-Hochberg false discovery rate (FDR) correction "
            f"for running many comparisons at once -- meaning these differences are unlikely to be due to "
            f"chance alone." + (f" The {len(recs_df)} highest-priority gaps are detailed below; the report "
            f"doesn't list all {gap_count} individually." if capped else "") +
            f" \"Coverage\" and \"demand\" measure how often a skill's name appears in course "
            f"descriptions and job postings respectively -- a text-coverage signal, not a direct measurement "
            f"of instructional depth or strict job requirements. Full methodology on the live dashboard."
        ),
        size=9.5,
    )
    pdf.ln(2)
    write_line(
        f"{course_count} courses analyzed   |   {gap_count} significant gaps found   |   "
        f"{n_high} high-priority   |   {n_rising} trending upward   |   Generated {datetime.date.today().isoformat()}",
        size=9, color=(90, 90, 90),
    )
    pdf.ln(6)
    pdf.set_x(pdf.l_margin)

    # A real data table instead of repeated paragraphs -- far quicker to
    # scan, and it's what a curriculum committee would actually expect.
    table_title = f"Top {len(recs_df)} ranked gap signals" if capped else "All significant gaps"
    write_line(table_title, size=13, bold=True, color=(30, 58, 138))
    pdf.set_font("Helvetica", "", 9)
    # Reset fill color to white before the table -- otherwise the navy
    # fill_color left over from the header banner above silently bleeds
    # into the table's data-row backgrounds, making the text unreadable
    # (caught by actually rendering the PDF to an image and looking at
    # it, not just checking that the code ran without error).
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(20, 20, 20)
    col_widths = (16, 44, 22, 24, 18, 22, 22)
    headers = ["Priority", "Skill", "Coverage", "Demand", "Gap", "Trend", "q-value"]
    with pdf.table(col_widths=col_widths, text_align="LEFT", line_height=6,
                   headings_style=FontFace(emphasis="BOLD", fill_color=(30, 58, 138), color=(255, 255, 255))) as table:
        header_row = table.row()
        for h in headers:
            header_row.cell(h)
        for _, row in recs_df.iterrows():
            data_row = table.row()
            data_row.cell(row["priority_tier"].upper())
            data_row.cell(clean(row["canonical_name"]))
            data_row.cell(f"{row['program_coverage_rate']*100:.0f}%")
            data_row.cell(f"{row['market_demand_rate']*100:.0f}%")
            data_row.cell(f"+{row['gap_value']*100:.0f} pt")
            data_row.cell(row["trend_label"].replace("no clear trend", "flat").title())
            data_row.cell(f"{row['q_value']:.4f}" if "q_value" in row and row["q_value"] is not None else "--")

    # A short, readable "top priorities" callout with genuinely varied
    # phrasing per row -- reusing the exact same sentence template three
    # times in a row (as the raw database rationale does) reads robotic
    # and repetitive once you actually read them back to back. Each item
    # also gets its exact evidence (counts + p/q-value), matching what
    # the dashboard's "Why am I seeing this?" drill-down shows, so the
    # PDF doesn't make a weaker claim than the live page does.
    def punchy_summary(row, variant):
        skill = clean(row["canonical_name"])
        cov = row["program_coverage_rate"] * 100
        dem = row["market_demand_rate"] * 100
        trend_bit = {
            "rising": " Demand is climbing, so this gap is only getting more urgent.",
            "falling": " Demand has cooled recently, though the gap is still real today.",
        }.get(row["trend_label"], "")
        templates = [
            f"{skill} shows up in {dem:.0f}% of job postings we sampled, but almost none of this program's courses ({cov:.0f}%) cover it.{trend_bit}",
            f"Employers ask for {skill} constantly -- {dem:.0f}% of postings -- yet the curriculum barely touches it ({cov:.0f}% coverage).{trend_bit}",
            f"A clear blind spot: {skill} is expected in {dem:.0f}% of real postings, but this program teaches it in only {cov:.0f}% of its courses.{trend_bit}",
        ]
        return templates[variant % len(templates)]

    pdf.ln(6)
    pdf.set_x(pdf.l_margin)
    write_line("Top priorities, explained", size=13, bold=True, color=(30, 58, 138))
    top_3 = recs_df[recs_df["priority_tier"] == "high"].head(3)
    for i, (_, row) in enumerate(top_3.iterrows()):
        rgb = TIER_RGB.get(row["priority_tier"], (100, 100, 100))
        start_y = pdf.get_y()
        pdf.set_fill_color(*rgb)
        pdf.rect(pdf.l_margin, start_y, 2.5, 20, style="F")
        pdf.set_x(pdf.l_margin + 5)
        write_line(clean(row["canonical_name"]), size=11, bold=True, color=rgb)
        pdf.set_x(pdf.l_margin + 5)
        write_line(punchy_summary(row, i), size=9.5, color=(60, 60, 60))
        pdf.set_x(pdf.l_margin + 5)
        if "p_value" in row and "q_value" in row and row["p_value"] is not None:
            write_line(
                clean(f"Evidence: raw p-value {row['p_value']:.4f}, FDR-adjusted q-value {row['q_value']:.4f} (decides significance)."),
                size=8.5, color=(120, 120, 120),
            )
            pdf.set_x(pdf.l_margin + 5)
        pdf.ln(3)
        pdf.set_x(pdf.l_margin)

    # Closing methodology/sources note -- so this PDF is honest and
    # self-contained even printed on its own, without requiring the
    # reader to already know how AlignED works.
    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    write_line("Methodology & sources", size=12, bold=True, color=(30, 58, 138))
    write_line(
        clean(
            "Skill taxonomy: U.S. Department of Labor O*NET. Significance: two-proportion z-test per skill, "
            "Benjamini-Hochberg FDR-corrected across every skill tested for this program+scope together (not "
            "individually) to control for the multiple-comparisons problem. Data: a fixed, dated sample of "
            "job postings and scraped course catalogs -- not a continuously live labor market. Full honest "
            "limitations, including single-annotator evaluation caveats, are on the dashboard's Methodology page."
        ),
        size=8.5, color=(100, 100, 100),
    )

    return bytes(pdf.output())


def build_profile_pdf_report(role_matches_df, top_role_label, have_df, missing_df, sample_postings_df):
    """A personalized career-style PDF: which real roles best fit this
    person's background, their strengths and gaps for the top match, and
    real example job postings pulled from that role -- built with the
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
    pdf.cell(0, 10, "AlignED -- Your Personalized Career Report")
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
            "\"Covered\" means your pasted text matched that many of a role's most in-demand tracked skills -- "
            "a simple overlap count against real job-posting data, not a validated fit score or probability."
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
    strengths_text = ", ".join(have_df["canonical_name"].head(10)) if not have_df.empty else "None matched yet -- add more detail to your profile text."
    write_line(clean(strengths_text), size=10)

    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    write_line(f"Skills to prioritize for {top_role_label}", size=13, bold=True, color=(220, 38, 38))
    gaps_text = ", ".join(missing_df["canonical_name"].head(10)) if not missing_df.empty else "No major gaps found -- strong match!"
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
            "How this was matched: simple keyword matching against your pasted text -- the same fast "
            "method used for the full-scale program analysis elsewhere in AlignED, benchmarked against an "
            "AI extraction method on a 104-item test set. It can miss skills phrased differently than "
            "expected. Full methodology on the live dashboard."
        ),
        size=8, color=(130, 130, 130),
    )

    return bytes(pdf.output())
