"""Parse Type C 2-column lookup tables into ZoningDefinition records.

Article XVI and Appendix A contain definition/lookup tables — simple
2-column tables where column 1 is a term and column 2 is its definition.
"""

from __future__ import annotations

from pathlib import Path

from strongtowns_detroit.zoning.models import ZoningDefinition
from strongtowns_detroit.zoning.table_parser import classify_table, extract_tables_xml


def parse_definition_table(
    grid: list[list[str]], section_ref: str = ""
) -> list[ZoningDefinition]:
    """Convert a 2-column lookup grid into ZoningDefinition records.

    Skips rows where the term is empty.  The first row is treated as
    a header and skipped if it looks like a column label (e.g., "Term",
    "Definition", "Use", "Meaning").
    """
    if not grid or not grid[0]:
        return []

    # Detect header row
    header_words = {"term", "definition", "use", "meaning", "word", "phrase", "description"}
    first_cell = grid[0][0].strip().lower()
    start = 1 if first_cell in header_words else 0

    if start >= len(grid):
        return []  # Header only, no data rows

    records: list[ZoningDefinition] = []
    for row in grid[start:]:
        term = row[0].strip() if len(row) > 0 else ""
        definition = row[1].strip() if len(row) > 1 else ""

        if not term:
            continue

        records.append(
            ZoningDefinition(
                term=term,
                definition=definition,
                section_ref=section_ref,
            )
        )
    return records


def extract_all_definitions(docx_path: Path) -> list[ZoningDefinition]:
    """Extract all definitions from an Article XVI or Appendix A .docx file.

    Classifies each table and parses those identified as 2-column
    lookup tables.
    """
    tables = extract_tables_xml(docx_path)
    records: list[ZoningDefinition] = []
    for grid in tables:
        if classify_table(grid) == "lookup":
            records.extend(parse_definition_table(grid))
    return records
