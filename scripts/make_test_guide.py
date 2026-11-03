"""Build the client-facing test guide PDF.

    python scripts/make_test_guide.py
    python scripts/make_test_guide.py --client "Acme Coaching" --contact "WhatsApp +91 98765 43210"

Run from the project root. Writes docs/Client-Test-Guide.pdf.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageChops
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "Client-Test-Guide.pdf"

parser = argparse.ArgumentParser(description="Build the client test guide PDF.")
parser.add_argument("--client", help="client company name for the cover")
parser.add_argument("--contact", help="contact line shown on the cover and at the end")
args = parser.parse_args()

CLIENT: str | None = (args.client or "").strip() or None
CONTACT = (args.contact or "").strip() or "Questions? Reply to the message that came with this guide."

NAVY = colors.HexColor("#1F3864")
TEXT = colors.HexColor("#16202C")
GREY = colors.HexColor("#5A6B7B")
LIGHT = colors.HexColor("#F4F6FA")
BORDER = colors.HexColor("#D8DEE7")
GREEN = colors.HexColor("#1E7B34")

PAGE_W, PAGE_H = A4
MARGIN_X = 1.8 * cm
USABLE = PAGE_W - 2 * MARGIN_X

styles = getSampleStyleSheet()
body = ParagraphStyle(
    "body", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5,
    leading=14, textColor=TEXT, alignment=TA_LEFT,
)
small = ParagraphStyle(
    "small", parent=body, fontSize=8, leading=11, textColor=GREY,
)
h1 = ParagraphStyle(
    "h1", parent=body, fontName="Helvetica-Bold", fontSize=16, leading=20,
    textColor=NAVY, spaceBefore=6, spaceAfter=8,
)
h2 = ParagraphStyle(
    "h2", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    textColor=NAVY, spaceBefore=10, spaceAfter=4,
)
cover_title = ParagraphStyle(
    "cover", parent=body, fontName="Helvetica-Bold", fontSize=32, leading=38,
    textColor=colors.white,
)
cover_sub = ParagraphStyle(
    "coversub", parent=body, fontSize=12, leading=16, textColor=colors.HexColor("#C9D4E5"),
)
cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10.5)
cell_bold = ParagraphStyle("cellb", parent=cell, fontName="Helvetica-Bold")


def picture(path: Path, width: float, margin: int = 28, trim_bottom: float = 0.0) -> Image:
    """Embed a screenshot trimmed of white space, with its real proportions.

    reportlab stretches an image when both width and height are given, and the
    app screenshots carry a lot of empty page below the content.
    """
    source = PILImage.open(path).convert("RGB")
    background = PILImage.new("RGB", source.size, (255, 255, 255))
    box = ImageChops.difference(source, background).getbbox()
    if box:
        left, top, right, bottom = box
        source = source.crop((
            max(0, left - margin), max(0, top - margin),
            min(source.width, right + margin), min(source.height, bottom + margin),
        ))
    if trim_bottom:
        # The page's own footer line is not part of the screen being shown.
        source = source.crop((0, 0, source.width, int(source.height * (1 - trim_bottom))))
    temp = Path(tempfile.mkdtemp()) / (path.stem + "_fit.png")
    source.save(temp)
    flow = Image(str(temp), width=width, height=width * source.height / source.width)
    flow.hAlign = "CENTER"
    return flow


class CoverBand(Flowable):
    def __init__(self, width: float, height: float):
        super().__init__()
        self.width = width
        self.height = height

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 30)
        canvas.drawString(22, self.height - 54, "Client test guide")
        canvas.setFont("Helvetica", 13)
        canvas.setFillColor(colors.HexColor("#C9D4E5"))
        canvas.drawString(22, self.height - 78, "Contact list cleanup service")
        canvas.setFont("Helvetica", 9)
        canvas.drawString(22, 26, "Every feature, every test case, and what to expect")


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_X, 1.35 * cm, PAGE_W - MARGIN_X, 1.35 * cm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN_X, 1.0 * cm, "Contact list cleanup - client test guide")
    canvas.drawRightString(PAGE_W - MARGIN_X, 1.0 * cm, f"Page {doc.page}")
    canvas.restoreState()


def table(data, widths, header=True, zebra=True, font_size=8):
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), font_size),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ]
    if zebra:
        for row in range(1 if header else 0, len(data)):
            if row % 2 == 0:
                style.append(("BACKGROUND", (0, row), (-1, row), LIGHT))
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style))
    return t


def bullets(items) -> list:
    return [Paragraph(f"<bullet>&bull;</bullet> {text}", body) for text in items]


def build() -> None:
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Contact list cleanup - client test guide",
        author="Nexora Tech",
        subject="Feature walkthrough and acceptance test cases",
    )
    frame = Frame(MARGIN_X, 1.8 * cm, USABLE, PAGE_H - 3.6 * cm, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=footer)])

    story: list = []

    # ---------------- cover ----------------
    story.append(CoverBand(USABLE, 7.2 * cm))
    story.append(Spacer(1, 1.1 * cm))
    story.append(Paragraph("What this document is", h1))
    story.append(Paragraph(
        "A walkthrough of every feature and a set of test cases you can run "
        "yourself. Each case lists the steps, the result you should see, and a "
        "box to tick. If a case fails, note it on the last page - that is the "
        "only place we need to look.",
        body,
    ))
    story.append(Spacer(1, 0.8 * cm))

    meta = []
    if CLIENT:
        meta.append([Paragraph("Prepared for", cell_bold), Paragraph(CLIENT, cell)])
    meta += [
        [Paragraph("Prepared by", cell_bold), Paragraph("Nexora Tech", cell)],
        [Paragraph("Version", cell_bold), Paragraph("2.0", cell)],
        [Paragraph("Date", cell_bold), Paragraph(date.today().strftime("%d %B %Y"), cell)],
        [Paragraph("Time to run all tests", cell_bold), Paragraph("About 20 minutes", cell)],
    ]
    story.append(table(meta, [5 * cm, USABLE - 5 * cm], header=False, zebra=False, font_size=9))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(CONTACT, small))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph("What is inside", h2))
    for line in [
        "1. What this service does",
        "2. Before you start",
        "3. How to use it, step by step",
        "4. What you get back - the five sheets",
        "5. How each feature works",
        "6. Test cases (18 checks)",
        "7. Known limits",
        "8. Troubleshooting",
        "9. Sign-off",
    ]:
        story.append(Paragraph(line, body))
    story.append(PageBreak())

    # ---------------- 1. what it does ----------------
    story.append(Paragraph("1. What this service does", h1))
    story.append(Paragraph(
        "It takes a messy Excel or CSV contact list and gives you back a clean "
        "one, plus a report of everything it changed and everything it removed. "
        "Your original file is never modified.",
        body,
    ))
    story.append(Spacer(1, 0.3 * cm))
    for item in bullets([
        "Removes duplicate contacts - the same person entered more than once.",
        "Fixes email addresses: trims spaces, lowercases, rejects broken ones.",
        "Fixes phone numbers: removes +91, dashes, spaces and leading zeros.",
        "Checks Indian GSTIN, PAN and pincode formats when those columns exist.",
        "Points out contacts that look like duplicates but were left alone.",
        "Writes a report you can keep as proof of the work.",
    ]):
        story.append(item)

    story.append(Paragraph("What it does not do", h2))
    for item in bullets([
        "It does not verify that an email inbox exists - only that the format is valid.",
        "It does not check GSTIN against the government portal - format only.",
        "It does not invent missing data, merge rows, or edit anything by itself.",
    ]):
        story.append(item)

    # ---------------- 2. before you start ----------------
    story.append(Paragraph("2. Before you start", h1))
    requirements = [
        [Paragraph("You need", cell_bold), Paragraph("A web browser (Chrome, Edge, Safari or Firefox). Nothing to install.", cell)],
        [Paragraph("File types", cell_bold), Paragraph("Excel .xlsx or .xlsm, or .csv. Older .xls files must be re-saved as .xlsx.", cell)],
        [Paragraph("File size", cell_bold), Paragraph("Up to 15 MB per file. Up to 20 files in one ZIP, 60 MB total.", cell)],
        [Paragraph("Privacy", cell_bold), Paragraph("Files are processed on the machine running the app. Nothing is sent to a third party or stored by us.", cell)],
    ]
    story.append(table(requirements, [4 * cm, USABLE - 4 * cm], header=False, zebra=False, font_size=8.5))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Your provider will send you a link. Open it and keep this document beside "
        "you while you test.",
        body,
    ))
    story.append(PageBreak())

    # ---------------- 3. how to use ----------------
    story.append(Paragraph("3. How to use it, step by step", h1))
    steps = [
        ("Step 1 - Open the link",
         "The page is titled \"Clean my Excel list\". You will see an upload box and a short "
         "\"How it works\" card."),
        ("Step 2 - Upload your file",
         "Click Upload and choose your Excel or CSV file. For several files at once, put them "
         "in a ZIP and upload the ZIP. The page immediately tells you how many rows and columns "
         "it read."),
        ("Step 3 - Check the columns",
         "The tool guesses which column holds emails, phone numbers and names by reading the "
         "cells. If a guess is wrong, change it from the dropdown. This is the only step that "
         "needs your attention."),
        ("Step 4 - Click \"Clean this file\"",
         "Nothing is downloaded yet. The page shows you what it found: clean rows, duplicates, "
         "bad emails, bad phones. You can open the lists before deciding."),
        ("Step 5 - Download",
         "Click \"Download cleaned file\". You get one Excel workbook with the clean rows and a "
         "full report. Your original file is untouched."),
    ]
    for title, text in steps:
        story.append(Paragraph(title, h2))
        story.append(Paragraph(text, body))

    image_path = DOCS / "screenshot-upload.png"
    if image_path.exists():
        story.append(Spacer(1, 0.3 * cm))
        story.append(picture(image_path, USABLE))
        story.append(Paragraph("The page you land on.", small))

    story.append(PageBreak())

    # ---------------- 4. output ----------------
    story.append(Paragraph("4. What you get back - the five sheets", h1))
    sheets = [
        [Paragraph("Sheet", cell_bold), Paragraph("What is in it", cell_bold)],
        [Paragraph("Report", cell_bold),
         Paragraph("One screen: rows read, kept and rejected; duplicates removed; invalid emails, "
                   "phones and GSTIN/PAN/pincodes; how many cells were cleaned; why rows were "
                   "rejected. Start here.", cell)],
        [Paragraph("Cleaned", cell_bold),
         Paragraph("The rows that passed every check, with emails and phone numbers normalised. "
                   "This is the list you import or upload to your CRM.", cell)],
        [Paragraph("Rejected", cell_bold),
         Paragraph("Every row that was removed, with its original row number and the reason. "
                   "Nothing is deleted silently.", cell)],
        [Paragraph("Changes", cell_bold),
         Paragraph("Every cell that was altered, shown as Before and After, with the kind of fix. "
                   "This is your proof that the work was done.", cell)],
        [Paragraph("Possible duplicates", cell_bold),
         Paragraph("Pairs that look like the same person but were NOT removed - for example "
                   "\"Rahul Sharma\" and \"Rahul S.\". You decide. This sheet appears only when "
                   "such a pair is found.", cell)],
    ]
    story.append(table(sheets, [3.4 * cm, USABLE - 3.4 * cm], font_size=8.5))
    story.append(Spacer(1, 0.4 * cm))

    results_path = DOCS / "screenshot-mobile-results.png"
    if results_path.exists():
        story.append(Spacer(1, 0.2 * cm))
        story.append(picture(results_path, 7.6 * cm, trim_bottom=0.12))
        story.append(Paragraph("The result screen, on a phone or a laptop.", small))

    story.append(Paragraph("How duplicates are decided", h2))
    story.append(Paragraph(
        "Two rows are treated as duplicates if their email address matches, or their phone "
        "number matches - after normalising both. Values are cleaned before comparing, so all "
        "of these count as the same person:",
        body,
    ))
    story.append(Spacer(1, 0.2 * cm))
    example = [
        [Paragraph("Rahul Sharma", cell), Paragraph("rahul.sharma@gmail.com", cell), Paragraph("9876543210", cell)],
        [Paragraph("Rahul S", cell), Paragraph("RAHUL.SHARMA@GMAIL.COM", cell), Paragraph("+91 98765 43210", cell)],
        [Paragraph("Rahul", cell), Paragraph("rahul.sharma@gmail.com", cell), Paragraph("09876543210", cell)],
    ]
    story.append(table(
        [[Paragraph("Name", cell_bold), Paragraph("Email", cell_bold), Paragraph("Phone", cell_bold)]] + example,
        [4 * cm, 7.4 * cm, 5 * cm],
        font_size=8.5,
    ))
    story.append(Paragraph(
        "The first row is kept; the others are listed on the Rejected sheet as duplicates of it.",
        small,
    ))
    story.append(PageBreak())

    # ---------------- 5. features ----------------
    story.append(Paragraph("5. How each feature works", h1))

    story.append(Paragraph("Validation rules", h2))
    rules = [
        [Paragraph("Field", cell_bold), Paragraph("Accepted", cell_bold), Paragraph("Rejected", cell_bold)],
        [Paragraph("Email", cell_bold),
         Paragraph("One @, a domain, a real ending: name@company.com", cell),
         Paragraph("karan@gmail, divya@@gmail.com, arjun@", cell)],
        [Paragraph("Phone (India)", cell_bold),
         Paragraph("9876543210, +91 98765 43210, 09876543210, 98765-43210", cell),
         Paragraph("12345, 1234567890, 98765abcde", cell)],
        [Paragraph("Phone (US)", cell_bold),
         Paragraph("(415) 555-2671, +1 415 555 2671", cell),
         Paragraph("Anything shorter or with letters", cell)],
        [Paragraph("GSTIN", cell_bold),
         Paragraph("27AAPFU0939F1ZV (15 characters, valid state code)", cell),
         Paragraph("00AAPFU0939F1ZV, 27AAPFU0939F1Z", cell)],
        [Paragraph("PAN", cell_bold),
         Paragraph("AAPFU0939F", cell),
         Paragraph("AAPF0939F, 1234567890", cell)],
        [Paragraph("Pincode", cell_bold),
         Paragraph("400001, 400 001", cell),
         Paragraph("040001, 40001", cell)],
    ]
    story.append(table(rules, [3 * cm, 7.4 * cm, USABLE - 10.4 * cm], font_size=8))

    story.append(Paragraph("Options on the page", h2))
    options = [
        [Paragraph("Email / Phone column", cell_bold),
         Paragraph("Which column to check. Guessed automatically; change it if wrong.", cell)],
        [Paragraph("Columns that must never be empty", cell_bold),
         Paragraph("Rows missing these are moved to Rejected. Leave empty to allow blanks.", cell)],
        [Paragraph("Phone numbers are from", cell_bold),
         Paragraph("India, United States, or Any country. Changes the validation rule.", cell)],
        [Paragraph("Write phone numbers as", cell_bold),
         Paragraph("Local (9876543210), International (+919876543210), or Digits only.", cell)],
        [Paragraph("Indian business fields", cell_bold),
         Paragraph("Optional GSTIN, PAN and pincode columns. Checked when selected.", cell)],
        [Paragraph("Only report duplicates", cell_bold),
         Paragraph("When ticked, duplicates are listed but kept instead of removed.", cell)],
        [Paragraph("My column headers are not on row 1", cell_bold),
         Paragraph("For files with a title or logo row above the headers. Set the header row number.", cell)],
    ]
    story.append(table(options, [6 * cm, USABLE - 6 * cm], font_size=8.5))
    story.append(PageBreak())

    # ---------------- 6. test cases ----------------
    story.append(Paragraph("6. Test cases", h1))
    story.append(Paragraph(
        "Run these in order. Every expected number below comes from the sample file the page "
        "offers, so your results should match exactly. Tick Pass or Fail for each.",
        body,
    ))
    story.append(Spacer(1, 0.3 * cm))

    def cases(rows):
        data = [[
            Paragraph("#", cell_bold), Paragraph("What to do", cell_bold),
            Paragraph("What you should see", cell_bold),
            Paragraph("Pass", cell_bold), Paragraph("Fail", cell_bold),
        ]]
        for number, todo, expect in rows:
            data.append([
                Paragraph(number, cell), Paragraph(todo, cell), Paragraph(expect, cell), "", "",
            ])
        return table(data, [1.1 * cm, 5.6 * cm, 8.2 * cm, 1.25 * cm, 1.25 * cm], font_size=7.8)

    story.append(Paragraph("A. Getting started", h2))
    story.append(cases([
        ("A1", "Open the link you were sent.",
         "Page titled \"Clean my Excel list\", an upload box, and a \"How it works\" card."),
        ("A2", "Click \"Try it with a sample messy file\".",
         "A file named sample_dirty.xlsx downloads."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("B. Upload and column detection", h2))
    story.append(cases([
        ("B1", "Upload sample_dirty.xlsx.",
         "Green message: Read 49 rows and 5 columns. Email column shows Email Address, phone shows Mobile No."),
        ("B2", "Open \"Look at the first rows\".",
         "Five rows with their headers, starting with Rahul Sharma."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("C. Cleaning and the output file", h2))
    story.append(cases([
        ("C1", "Click \"Clean this file\".",
         "Clean rows 39, Duplicates 2, Bad emails 3, Bad phones 3."),
        ("C2", "Click \"Download cleaned file\".",
         "An .xlsx file downloads and opens in Excel."),
        ("C3", "Look at the tabs at the bottom.",
         "Report, Cleaned, Rejected, Changes. No Possible duplicates tab for this file."),
        ("C4", "Open the Report sheet.",
         "Rows read 49, kept 39, rejected 8, duplicates 2, blank rows 2, cells cleaned 8."),
        ("C5", "Open the Rejected sheet.",
         "Exactly 8 rows, each with a reason such as invalid email or duplicate of row 2."),
        ("C6", "Open the Changes sheet.",
         "8 rows showing Before and After, e.g. +91 98765 43211 becomes 9876543211."),
        ("C7", "Open your original sample_dirty.xlsx.",
         "Unchanged - still 49 rows and the same messy values."),
    ]))
    story.append(PageBreak())

    story.append(Paragraph("D. Options", h2))
    story.append(cases([
        ("D1", "Clean the sample with phone format \"International\".",
         "Mobile numbers in the Cleaned sheet start with +91."),
        ("D2", "Tick \"Only report duplicates\" and clean again.",
         "Duplicates 2 is still reported, but the Cleaned sheet keeps all 41 usable rows."),
        ("D3", "Add Name to \"Columns that must never be empty\" using your own file with an empty name.",
         "That row appears on Rejected as missing required field: Name."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("E. Indian business fields", h2))
    story.append(cases([
        ("E1", "Upload a file with a GSTIN column containing one bad value.",
         "GSTIN is detected automatically; the bad row is Rejected as invalid GSTIN."),
        ("E2", "Open \"Indian business fields\" on the same file.",
         "The GSTIN dropdown is already set to your GSTIN column."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("F. Batch mode (a ZIP of files)", h2))
    story.append(cases([
        ("F1", "Put 2 or 3 spreadsheets in a ZIP and upload it.",
         "Blue note says Batch mode; a \"Clean all files\" button appears."),
        ("F2", "Click \"Clean all files\".",
         "Files cleaned shows 2 / 2 (or 3 / 3) and a table lists each file separately."),
        ("F3", "Click \"Download all ... cleaned files\".",
         "A ZIP downloads containing one workbook per input file plus batch_summary.csv."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("G. Near-duplicates", h2))
    story.append(cases([
        ("G1", "Upload a file with Rahul Sharma and Rahul S. as separate rows.",
         "\"1 possible duplicates to review\" appears; no row is removed."),
        ("G2", "Open the Possible duplicates sheet.",
         "Both rows listed with a score of about 92 and the reason."),
    ]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("H. Edge cases", h2))
    story.append(cases([
        ("H1", "Try to upload a PDF or Word file.",
         "The page refuses it. Nothing crashes."),
        ("H2", "Upload a CSV with a stray quote, e.g. \"Rahul\" Sharma.",
         "It either cleans normally or shows one plain sentence with a fix. No error trace."),
    ]))

    story.append(PageBreak())

    # ---------------- batch picture + limits ----------------
    batch_path = DOCS / "screenshot-batch.png"
    if batch_path.exists():
        story.append(Paragraph("Batch mode at a glance", h1))
        story.append(picture(batch_path, USABLE))
        story.append(Paragraph(
            "One ZIP in, one ZIP out. Each file is cleaned with the same rules and listed separately.",
            small,
        ))
        story.append(Spacer(1, 0.5 * cm))

    story.append(PageBreak())

    story.append(Paragraph("7. Known limits", h1))
    for item in bullets([
        "Email checking is format only. A well-formed address that does not exist will pass.",
        "GSTIN checking is format only. The check digit is not recalculated and nothing is looked up on the GST portal.",
        "Near-duplicate matching understands English and Latin names. Names in other scripts are not matched.",
        "Very common first-three-letter groups are skipped in near-duplicate matching to keep large files fast.",
        "Files over 15 MB, or more than 20 files in one ZIP, are refused. Split them and run again.",
        "Legacy .xls files must be re-saved as .xlsx first.",
    ]):
        story.append(item)

    story.append(Paragraph("8. Troubleshooting", h1))
    fixes = [
        [Paragraph("Symptom", cell_bold), Paragraph("What to do", cell_bold)],
        [Paragraph("The page will not open", cell),
         Paragraph("Check the link. If it still fails, tell your provider - the app may need restarting.", cell)],
        [Paragraph("\"That file could not be read\"", cell),
         Paragraph("Open the file in Excel and use File > Save As > Excel Workbook (.xlsx), then upload again.", cell)],
        [Paragraph("A column was not detected", cell),
         Paragraph("Pick it manually from the dropdown. The list shows every column in your file.", cell)],
        [Paragraph("Phone numbers look wrong", cell),
         Paragraph("Check \"Phone numbers are from\". Choosing the wrong country rejects good numbers.", cell)],
        [Paragraph("Too many rows rejected", cell),
         Paragraph("Look at the Rejected sheet. Usually the wrong column was chosen, or a required column was set too strict.", cell)],
        [Paragraph("Numbers show as 9.87654E+09", cell),
         Paragraph("The cell is numeric, not text. Format that column as Text in your file before uploading.", cell)],
    ]
    story.append(table(fixes, [6 * cm, USABLE - 6 * cm], font_size=8.5))
    story.append(PageBreak())

    # ---------------- sign off ----------------
    story.append(Paragraph("9. Sign-off", h1))
    story.append(Paragraph(
        "When all the cases above pass, sign below. If any case failed, write the case number "
        "and what happened - that is all that is needed to fix it.",
        body,
    ))
    story.append(Spacer(1, 0.6 * cm))

    signoff = [
        [Paragraph("Tested by", cell_bold), Paragraph("", cell)],
        [Paragraph("Company", cell_bold), Paragraph("", cell)],
        [Paragraph("Date", cell_bold), Paragraph("", cell)],
        [Paragraph("Cases passed", cell_bold), Paragraph("", cell)],
        [Paragraph("Cases failed", cell_bold), Paragraph("", cell)],
        [Paragraph("Case numbers that failed", cell_bold), Paragraph("", cell)],
        [Paragraph("Signature", cell_bold), Paragraph("", cell)],
    ]
    story.append(table(signoff, [6 * cm, USABLE - 6 * cm], header=False, zebra=False, font_size=9))
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("Notes", h2))
    story.append(table(
        [[""], [""], [""], [""]],
        [USABLE],
        header=False,
        zebra=False,
    ))
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph(CONTACT, small))

    doc.build(story)
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
