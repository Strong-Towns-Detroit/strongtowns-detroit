"""Parse Type B dimensional-standards tables into DimensionalStandard records.

Article XIII tables have complex merged cells that produce a consistent
structure after XML-level expansion:

- 18 columns (duplicate columns from merged-cell expansion)
- 4 header rows:
  - Row 0: top-level categories ("Use", "Minimum Lot Dimensions", "Minimum Setbacks", ...)
  - Row 1: sub-categories ("Area (sq. ft.)", "Width (feet)", "Front", "Side*", "Rear", ...)
  - Row 2: section references
  - Row 3: formula footnotes (spanning row)
- Data rows from row 4 onward, with use name in column 0

Columns pair up due to merged cells: cols 0-1 = "Use", cols 2-3 = "Area", etc.
This module builds composite standard names from the multi-row headers and
de-duplicates adjacent identical columns.
"""

from __future__ import annotations

from pathlib import Path

from strongtowns_detroit.zoning.models import DimensionalStandard
from strongtowns_detroit.zoning.table_parser import classify_table, extract_tables_xml


def _is_spanning_row(row: list[str]) -> bool:
    """Check if a row is a category header (all cells identical or all but first empty)."""
    if not row:
        return False
    non_empty = [c.strip() for c in row if c.strip()]
    if len(non_empty) <= 1:
        return True  # All-empty or single value spanning
    # All cells have the same text (merged spanning row)
    return len(set(c.strip() for c in row)) == 1


def _find_data_start(grid: list[list[str]]) -> int:
    """Find where data rows begin by skipping header/footnote rows.

    Header rows are identified by:
    - Spanning rows (all cells identical)
    - Rows containing "Sec. Reference" or "Section 50-" text
    - Rows starting with "*Formula"
    """
    for r in range(len(grid)):
        if _is_spanning_row(grid[r]):
            continue
        row_text = " ".join(c.strip() for c in grid[r])
        if "sec. reference" in row_text.lower():
            continue
        if "section 50-" in row_text.lower() and grid[r][0].strip().lower().startswith("sec"):
            continue
        if row_text.strip().startswith("*Formula"):
            continue
        # Check if this looks like a header row (mostly category labels)
        first_cell = grid[r][0].strip().lower()
        if first_cell in ("use", "use category", ""):
            continue
        # Some specialized tables use two header rows whose first cell is
        # repeated while the second row supplies column scenarios (for
        # example, service-bay counts in §§50-13-174--176).
        if (
            r + 1 < len(grid)
            and grid[r + 1]
            and first_cell == grid[r + 1][0].strip().lower()
        ):
            continue
        if (
            r > 0
            and grid[r - 1]
            and first_cell == grid[r - 1][0].strip().lower()
        ):
            continue
        # This looks like a data row
        return r
    return len(grid)


def _build_column_map(grid: list[list[str]]) -> list[tuple[int, str]]:
    """Build a mapping of (column_index, standard_name) from header rows.

    Combines row 0 (category) and row 1 (sub-category) into composite
    names like "Minimum Lot Dimensions - Area (sq. ft.)".
    De-duplicates adjacent columns that have identical headers.
    """
    if len(grid) < 2:
        return []

    row0 = [c.strip() for c in grid[0]]
    row1 = [c.strip() for c in grid[1]] if len(grid) > 1 else row0

    # The principal Article XIII tables expand to 18 visual grid columns, but
    # their first merged "Use" cell occupies two header columns and only one
    # data column. Values therefore begin one index left of their expanded
    # headers. Encode the reviewed physical layout explicitly; deriving it
    # from repeated header strings mislabeled rear setback as height.
    if len(row0) == 18 and row0[0].lower() == "use":
        return [
            (1, "Minimum Lot Dimensions - Area (sq. ft.)"),
            (3, "Minimum Lot Dimensions - Width (feet)"),
            (5, "Minimum Setbacks (feet) - Front"),
            (7, "Minimum Setbacks (feet) - Side*"),
            (8, "Minimum Setbacks (feet) - Rear"),
            (10, "Max. Height (feet)"),
            (12, "Max. Lot Coverage (%)"),
            (13, "Max FAR"),
            (15, "Add'l. Regs."),
        ]

    columns: list[tuple[int, str]] = []
    seen_names: set[str] = set()

    for col in range(len(row0)):
        if col == 0:
            continue
        cat = row0[col]
        sub = row1[col] if col < len(row1) else ""

        # Skip "Use" columns and empty headers
        if cat.lower() in ("use", "") and sub.lower() in ("use", ""):
            continue

        # Build composite name
        if sub and sub != cat and cat.lower() not in ("", "use"):
            name = f"{cat} - {sub}"
        elif sub:
            name = sub
        elif cat:
            name = cat
        else:
            continue

        # De-duplicate adjacent identical columns
        if name in seen_names:
            continue
        seen_names.add(name)
        columns.append((col, name))

    return columns


def parse_dimensional_table(
    grid: list[list[str]], section_ref: str = ""
) -> list[DimensionalStandard]:
    """Convert a Type B dimensional-standards grid into records.

    Handles both simple single-row headers and the multi-row header
    structure of Article XIII tables.  The use name from column 0 is
    stored in the 'district' field since these tables are organized
    per-district (the district identity comes from the section context).
    """
    if len(grid) < 2 or len(grid[0]) < 2:
        return []

    data_start = _find_data_start(grid)
    if data_start >= len(grid):
        return []

    # Use multi-row column map only when there are multiple header rows
    if data_start >= 2:
        col_map = _build_column_map(grid)
    else:
        col_map = []

    if not col_map:
        # Simple single-row header
        header = [c.strip() for c in grid[0]]
        col_map = [(i, header[i]) for i in range(1, len(header)) if header[i]]
        data_start = max(data_start, 1)

    records: list[DimensionalStandard] = []
    for row in grid[data_start:]:
        if _is_spanning_row(row):
            continue

        use_name = row[0].strip() if row else ""
        if not use_name:
            continue

        for col_idx, standard_name in col_map:
            if col_idx >= len(row):
                continue
            value = row[col_idx].strip()
            if not value or value == "—":
                continue
            # Vertically/row-merged use labels sometimes occupy the first
            # apparent value cell. They are structural repetition, not a lot
            # area or other dimensional value.
            if value.casefold() == use_name.casefold():
                continue

            records.append(
                DimensionalStandard(
                    district=use_name,
                    standard_name=standard_name,
                    value=value,
                    section_ref=section_ref,
                )
            )

    return records


def extract_all_dimensional_standards(docx_path: Path) -> list[DimensionalStandard]:
    """Extract all dimensional standards from an Article XIII .docx file.

    Classifies each table and parses those identified as dimensional
    standards tables.
    """
    tables = extract_tables_xml(docx_path)
    records: list[DimensionalStandard] = []
    for grid in tables:
        table_type = classify_table(grid)
        if table_type == "dimensional":
            records.extend(parse_dimensional_table(grid))
    return records
