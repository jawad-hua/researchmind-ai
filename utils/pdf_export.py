"""
PDF Export — converts the markdown report into a downloadable PDF.

v2: uses a bundled Unicode TTF font (DejaVu Sans) instead of the core
Helvetica font, so curly quotes, dashes, and other punctuation the LLM
commonly outputs render correctly instead of being replaced with '?'.
Also renders markdown pipe-tables as real PDF tables instead of raw text.
"""

import os
import re
from fpdf import FPDF, XPos, YPos
from fpdf.fonts import FontFace

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
_FONT_REGULAR = os.path.join(_FONT_DIR, "DejaVuSans.ttf")
_FONT_BOLD = os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf")

_TABLE_SEP_RE = re.compile(r"^\|?[\s:\-|]+\|?$")


class ReportPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _strip_markdown_inline(text: str) -> str:
    """Strip markdown link syntax and bold markers, keep the visible text."""
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text.replace("**", "")


def _parse_table_block(lines: list[str]) -> list[list[str]]:
    """Turn a block of '| a | b |' lines into rows of cell strings."""
    rows = []
    for line in lines:
        if _TABLE_SEP_RE.match(line):
            continue  # the |---|---| separator row
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append([_strip_markdown_inline(c) for c in cells])
    return rows


def markdown_to_pdf(markdown_text: str, title: str, output_path: str) -> str:
    """
    Convert a markdown report to a PDF file. Handles #-style headers,
    bullet lists, pipe-tables, and plain paragraphs, with full Unicode
    text support. Returns the output_path.
    """
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", _FONT_REGULAR)
    pdf.add_font("DejaVu", "B", _FONT_BOLD)
    pdf.add_page()

    def _cell(text: str, size: int, bold: bool = False, height: int = 7):
        pdf.set_font("DejaVu", "B" if bold else "", size)
        pdf.multi_cell(0, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def _render_table(rows: list[list[str]]):
        if not rows:
            return
        pdf.set_font("DejaVu", "", 10)
        header_style = FontFace(family="DejaVu", emphasis="BOLD")
        with pdf.table(text_align="LEFT") as table:
            for i, row_data in enumerate(rows):
                row = table.row()
                for datum in row_data:
                    row.cell(datum, style=header_style if i == 0 else None)
        pdf.ln(3)

    _cell(title, size=18, bold=True)
    pdf.ln(4)

    lines = markdown_text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = raw_line.strip()

        if not line:
            pdf.ln(3)
            i += 1
            continue

        # Table block: a run of consecutive lines starting with '|'
        if line.startswith("|"):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            rows = _parse_table_block(table_lines)
            _render_table(rows)
            continue

        # Headers: #, ##, ### etc.
        header_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if header_match:
            level = len(header_match.group(1))
            heading_text = _strip_markdown_inline(header_match.group(2))
            pdf.ln(2)
            size = {1: 16, 2: 14, 3: 12, 4: 11, 5: 11, 6: 11}.get(level, 11)
            _cell(heading_text, size=size, bold=True)
            i += 1
            continue

        if line.startswith("- ") or line.startswith("* "):
            clean = _strip_markdown_inline(line[2:])
            _cell(f"  \u2022 {clean}", size=11)
            i += 1
            continue

        # Plain paragraph
        clean = _strip_markdown_inline(line)
        _cell(clean, size=11)
        i += 1

    pdf.output(output_path)
    return output_path
