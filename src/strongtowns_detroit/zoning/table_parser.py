"""XML-level table parser for Word documents.

Extracts tables from .docx files by parsing the underlying XML directly,
bypassing python-docx's row.cells which crashes on complex merged-cell
tables (Article XIII dimensional standards).

Handles:
- gridSpan (horizontal merge)
- vMerge (vertical merge)
- Nested paragraphs within cells
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": WNS}


def _cell_text(tc: etree._Element) -> str:
    """Extract all text from a <w:tc> element, joining paragraphs with spaces."""
    parts = []
    for p in tc.findall(f".//{{{WNS}}}p"):
        runs = p.findall(f".//{{{WNS}}}r/{{{WNS}}}t")
        para_text = "".join(r.text or "" for r in runs)
        if para_text.strip():
            parts.append(para_text.strip())
    return " ".join(parts)


def _cell_grid_span(tc: etree._Element) -> int:
    """Return the horizontal span of a <w:tc> (default 1)."""
    vals = tc.xpath("./w:tcPr/w:gridSpan/@w:val", namespaces=NSMAP)
    return int(vals[0]) if vals else 1


def _cell_vmerge(tc: etree._Element) -> str | None:
    """Return vMerge status: 'restart' for start, 'continue' for continuation, None for normal."""
    vmerge_els = tc.xpath("./w:tcPr/w:vMerge", namespaces=NSMAP)
    if not vmerge_els:
        return None
    val = vmerge_els[0].get(f"{{{WNS}}}val")
    return "restart" if val == "restart" else "continue"


def _grid_col_count(tbl: etree._Element) -> int:
    """Determine the grid column count from <w:tblGrid> if present."""
    grid_cols = tbl.xpath("./w:tblGrid/w:gridCol", namespaces=NSMAP)
    return len(grid_cols) if grid_cols else 0


def expand_table_xml(tbl: etree._Element) -> list[list[str]]:
    """Expand a <w:tbl> element into a 2D string grid.

    Merged cells are expanded so every grid position has a value.
    """
    rows = tbl.xpath("./w:tr", namespaces=NSMAP)
    if not rows:
        return []

    nrows = len(rows)

    # Determine column count from tblGrid or by scanning first rows
    ncols = _grid_col_count(tbl)
    if ncols == 0:
        for row in rows:
            cells = row.xpath("./w:tc", namespaces=NSMAP)
            col_count = sum(_cell_grid_span(tc) for tc in cells)
            ncols = max(ncols, col_count)

    if ncols == 0:
        return []

    grid: list[list[str | None]] = [[None] * ncols for _ in range(nrows)]
    vmerge_starts: dict[tuple[int, int], tuple[str, int]] = {}

    for r, row_el in enumerate(rows):
        cells = row_el.xpath("./w:tc", namespaces=NSMAP)
        c = 0
        for tc in cells:
            # Skip past already-filled positions (from prior row merges)
            while c < ncols and grid[r][c] is not None:
                c += 1
            if c >= ncols:
                break

            text = _cell_text(tc)
            col_span = _cell_grid_span(tc)
            vmerge = _cell_vmerge(tc)

            if vmerge == "restart":
                vmerge_starts[(r, c)] = (text, col_span)
                for j in range(c, min(c + col_span, ncols)):
                    grid[r][j] = text
            elif vmerge == "continue":
                # Walk upward to find the merge start
                above_r = r - 1
                while above_r >= 0 and (above_r, c) not in vmerge_starts:
                    above_r -= 1
                if (above_r, c) in vmerge_starts:
                    text, col_span = vmerge_starts[(above_r, c)]
                for j in range(c, min(c + col_span, ncols)):
                    grid[r][j] = text
            else:
                # Normal cell
                for j in range(c, min(c + col_span, ncols)):
                    grid[r][j] = text

            c += col_span

    # Fill any remaining None with empty string
    for r in range(nrows):
        for c in range(ncols):
            if grid[r][c] is None:
                grid[r][c] = ""

    return grid  # type: ignore[return-value]


def extract_tables_xml(docx_path: Path) -> list[list[list[str]]]:
    """Extract all tables from a .docx as 2D string grids.

    Opens the .docx as a ZIP archive and parses the underlying XML
    directly, avoiding python-docx's table grid reconstruction which
    can crash on complex merged-cell layouts.
    """
    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = etree.fromstring(xml_bytes)
    tables = root.xpath("//w:tbl", namespaces=NSMAP)

    return [expand_table_xml(tbl) for tbl in tables]


# District code pattern for classification heuristic
_DISTRICT_PATTERN = re.compile(
    r"^(R[1-6]|SD[1-5]|B[1-6]|M[1-5]|W1|PC|PCA|TM|PD|PR|P1|MKT)$", re.IGNORECASE
)

_DIMENSIONAL_KEYWORDS = {
    "standard", "requirement", "minimum", "maximum", "setback", "height",
    "lot dimensions", "area", "width", "coverage", "far", "setbacks",
}


def classify_table(grid: list[list[str]]) -> str:
    """Classify a table grid as 'use_matrix', 'dimensional', 'lookup', or 'unknown'.

    Heuristics (checked against the first few rows, not just row 0):
    - use_matrix: a header row contains many district codes (R1, R2, etc.) and 20+ columns
    - dimensional: 3+ columns, header rows contain dimensional keywords
    - lookup: exactly 2 columns
    - unknown: anything else
    """
    if not grid or not grid[0]:
        return "unknown"

    ncols = len(grid[0])

    # Check up to the first 3 rows for district codes (real tables
    # have category labels in row 0 and district codes in row 1)
    rows_to_check = min(len(grid), 3)
    for r in range(rows_to_check):
        district_count = sum(
            1 for cell in grid[r] if _DISTRICT_PATTERN.match(cell.strip())
        )
        if district_count >= 5 and ncols >= 20:
            return "use_matrix"

    if ncols == 2:
        return "lookup"

    # Check for dimensional keywords across first few header rows.
    # Real dimensional tables (Article XIII) have 17-18 columns and
    # multi-row headers with keywords like "Minimum Lot Dimensions".
    if ncols >= 3:
        header_text = ""
        for r in range(min(len(grid), 4)):
            header_text += " " + " ".join(cell.lower() for cell in grid[r])
        if any(kw in header_text for kw in _DIMENSIONAL_KEYWORDS):
            return "dimensional"

    return "unknown"
