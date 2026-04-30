#!/usr/bin/env python3
"""Convert per-rater audit CSVs into formatted xlsx files.

Each xlsx has two tabs:
  1. "Instructions" — rubric, [NULL] handling, audit ground rules.
  2. "Audit"        — 200 rows, frozen header + ID columns, dropdown
                      validation on the rating column.

Robust to viewing in Excel / Numbers / Google Sheets — uses tab-level
separation rather than merged-cell-with-wrapped-instruction, which
Google Sheets renders inconsistently.
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent.parent
SHEETS_DIR = ROOT / "data" / "annotations"

RATERS = ("R1", "R2", "R3")

COL_WIDTHS = {
    "row_id": 6,
    "paper_id": 26,
    "field_id": 30,
    "system_id": 24,
    "gold_value": 70,
    "candidate_value": 70,
    "rating": 10,
    "notes": 40,
}

ESPRESSO = "3E2B20"
GOLD = "C9A24A"
PARCHMENT = "F8F2E4"
CREAM = "FFF5E0"
TEXT_DARK = "2B1E14"

HEADER_FILL = PatternFill("solid", fgColor=ESPRESSO)
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
ANSWER_FILL = PatternFill("solid", fgColor=CREAM)
SECTION_FILL = PatternFill("solid", fgColor=PARCHMENT)

THIN_BORDER = Border(
    left=Side(style="thin", color="A89A85"),
    right=Side(style="thin", color="A89A85"),
    top=Side(style="thin", color="A89A85"),
    bottom=Side(style="thin", color="A89A85"),
)


def write_instructions(ws):
    """Render the instructions tab. Single column, plenty of breathing room."""
    ws.column_dimensions["A"].width = 110

    rows = [
        ("CroissantMiner judge audit", "title"),
        ("", None),
        ("What you are doing", "h2"),
        (
            "You are scoring 200 (paper, field, system) cells on a 1-3 scale to calibrate "
            "the LLM judges we will use to score the full benchmark. Whichever LLM judge "
            "agrees most with the three of you wins the audit and goes to production. "
            "Your ratings effectively decide which judge we use.",
            "body",
        ),
        ("", None),
        ("Ground rule: gold is the reference, do NOT open the papers", "h2"),
        (
            "Rate the candidate (model output) by comparing it to the gold "
            "(human-validated reference). The LLM judges only see gold and candidate, "
            "no paper text — the audit must use the same inputs so we are measuring "
            "the same task. Going back to the source PDFs would change what we are "
            "calibrating against.",
            "body",
        ),
        ("", None),
        ("Rubric", "h2"),
        ("1 = Not correct.  Candidate is wrong, hallucinated, contradicts the gold, "
         "or invents content that is not in the gold.", "body"),
        ("2 = Partially correct.  Candidate captures part of the gold but misses "
         "important content, contains errors, or has the wrong scope.", "body"),
        ("3 = Correct.  Candidate conveys the same content as the gold. "
         "Stylistic and phrasing differences are fine.", "body"),
        ("", None),
        ("Special case: gold says '[NULL - not found in paper]'", "h2"),
        (
            "About a quarter of the audit cells have gold = '[NULL - not found in paper]', "
            "which means the human annotators looked for this field in the paper and "
            "decided it is absent. For these cells:",
            "body",
        ),
        ("• If the candidate is empty or also says 'not found' / null / 'unknown' → score 3 "
         "(correctly identified absence).", "body"),
        ("• If the candidate produces real content (a paragraph, names, numbers, etc.) → "
         "score 1 (hallucinated; the gold says the paper does not contain this).", "body"),
        ("• If the candidate produces something hedged or partial (e.g. 'unspecified, "
         "but the dataset uses crowdworkers') → score 2.", "body"),
        ("", None),
        ("Special case: candidate is empty but gold has content", "h2"),
        ("If the candidate is empty / null / 'unknown' and the gold has real content, "
         "score 1 (the model missed an answer that was present).", "body"),
        ("", None),
        ("Notes column (optional)", "h2"),
        ("Use it for anything that surprised you, edge cases that did not fit the "
         "rubric, or cells where you would have wanted to see the paper. Free text.", "body"),
        ("", None),
        ("Independence", "h2"),
        ("Do not discuss with the other raters until everyone has submitted. The "
         "agreement statistics rely on independent ratings.", "body"),
        ("", None),
        ("When you are done", "h2"),
        ("Save the file as audit_sheet_<your-name>_done.xlsx and send it back. "
         "If the rating column is blank for any row, please fill it before sending.", "body"),
    ]

    title_font = Font(name="Calibri", size=18, bold=True, color=ESPRESSO)
    h2_font = Font(name="Calibri", size=12, bold=True, color=ESPRESSO)
    body_font = Font(name="Calibri", size=11, color=TEXT_DARK)

    for r_idx, (text, kind) in enumerate(rows, start=1):
        cell = ws.cell(row=r_idx, column=1, value=text)
        if kind == "title":
            cell.font = title_font
            cell.fill = SECTION_FILL
            ws.row_dimensions[r_idx].height = 36
        elif kind == "h2":
            cell.font = h2_font
            ws.row_dimensions[r_idx].height = 22
        elif kind == "body":
            cell.font = body_font
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            # Estimate row height: ~60 chars per line, 15pt per line + 6 padding
            n_lines = max(1, len(text) // 95 + 1)
            ws.row_dimensions[r_idx].height = max(18, 15 * n_lines + 6)
        else:
            ws.row_dimensions[r_idx].height = 8


def write_audit(ws, df):
    # Quick reminder bar at the top
    reminder = ("Reminder: gold is the reference, do not open the papers. "
                "Rubric: 1 = wrong/hallucinated, 2 = partially correct, "
                "3 = correct. Special case: if gold says '[NULL - not found "
                "in paper]', score 3 if candidate is also empty/null, score "
                "1 if candidate hallucinates content. See the Instructions "
                "tab for the full guide.")
    ws.cell(row=1, column=1, value=reminder)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    c = ws.cell(row=1, column=1)
    c.alignment = Alignment(wrap_text=True, vertical="center")
    c.fill = SECTION_FILL
    c.font = Font(name="Calibri", size=10, italic=True, color=TEXT_DARK)
    ws.row_dimensions[1].height = 80

    header_row = 3

    # Header
    for col_idx, col in enumerate(df.columns, start=1):
        c = ws.cell(row=header_row, column=col_idx, value=col)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(col_idx)].width = COL_WIDTHS.get(col, 16)
    ws.row_dimensions[header_row].height = 30

    rating_col_idx = list(df.columns).index("rating") + 1

    # Data rows
    first_data_row = header_row + 1
    for r_offset, (_, row) in enumerate(df.iterrows()):
        r = first_data_row + r_offset
        for col_idx, col in enumerate(df.columns, start=1):
            cell = ws.cell(row=r, column=col_idx, value=row[col] if pd.notna(row[col]) else "")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = THIN_BORDER
            cell.font = Font(name="Calibri", size=10, color=TEXT_DARK)
            if col in ("rating", "notes"):
                cell.fill = ANSWER_FILL

        # Estimate row height from the longer of gold/candidate value text
        gold_str = str(row.get("gold_value", ""))
        cand_str = str(row.get("candidate_value", ""))
        max_chars = max(len(gold_str), len(cand_str))
        # Column width 70 chars, ~95 chars per wrapped line in Excel
        n_lines = max(3, max_chars // 95 + 2)
        ws.row_dimensions[r].height = min(360, 15 * n_lines + 8)

    # Dropdown validation on rating column
    last_data_row = first_data_row + len(df) - 1
    dv = DataValidation(type="list", formula1='"1,2,3"', allow_blank=True,
                       showDropDown=False, showErrorMessage=True,
                       errorTitle="Invalid rating",
                       error="Please enter 1, 2, or 3.")
    rating_letter = get_column_letter(rating_col_idx)
    dv.add(f"{rating_letter}{first_data_row}:{rating_letter}{last_data_row}")
    ws.add_data_validation(dv)

    # Freeze header row + first 4 ID columns
    ws.freeze_panes = ws.cell(row=first_data_row, column=5)


def build(rater: str) -> None:
    src = SHEETS_DIR / f"audit_sheet_{rater}.csv"
    dst = SHEETS_DIR / f"audit_sheet_{rater}.xlsx"

    df = pd.read_csv(src)
    expected = ["row_id", "paper_id", "field_id", "system_id",
                "gold_value", "candidate_value", "rating", "notes"]
    df = df[[c for c in expected if c in df.columns]]
    if "rating" not in df.columns:
        df["rating"] = ""
    if "notes" not in df.columns:
        df["notes"] = ""

    wb = Workbook()
    wb.remove(wb.active)
    ws_inst = wb.create_sheet("Instructions")
    write_instructions(ws_inst)
    ws_audit = wb.create_sheet("Audit")
    write_audit(ws_audit, df)

    # Instructions tab opens first
    wb.active = wb.index(ws_inst)

    wb.save(dst)
    print(f"  wrote {dst}")


def main():
    for rater in RATERS:
        build(rater)


if __name__ == "__main__":
    main()
