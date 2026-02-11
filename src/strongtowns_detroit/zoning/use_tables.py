"""Parse Type A use-permission matrices into UsePermission records.

Article XII of Detroit's Zoning Ordinance contains ~49 tables, each
a matrix with land use names as rows and zoning district codes as
columns.  Each cell contains a permission code: R (by-right),
C (conditional), C/R or R/C (mixed), L (limited), or — (not permitted).

Real tables have a two-row header:
- Row 0: category labels ("Residential", "Business", "Industrial", ...)
- Row 1: district codes  (R1, R2, ..., B1, B2, ..., M1, ...)
And two label columns:
- Column 0: Use Category (broad group)
- Column 1: Specific Land Use (actual use name)
"""

from __future__ import annotations

import re
from pathlib import Path

from strongtowns_detroit.zoning.models import UsePermission
from strongtowns_detroit.zoning.table_parser import (
    _DISTRICT_PATTERN,
    classify_table,
    extract_tables_xml,
)


def _find_district_row(grid: list[list[str]], max_rows: int = 3) -> int:
    """Find which row contains district codes.

    Returns the row index with the highest count of district-code
    matches, checking up to *max_rows* rows.
    """
    best_row = 0
    best_count = 0
    for r in range(min(len(grid), max_rows)):
        count = sum(1 for c in grid[r] if _DISTRICT_PATTERN.match(c.strip()))
        if count > best_count:
            best_count = count
            best_row = r
    return best_row


def _find_use_name_col(grid: list[list[str]], district_row: int) -> int:
    """Determine which column holds use names.

    If column 1 has a label like "Specific Land Use" in the header,
    use column 1.  Otherwise default to column 0.
    """
    if len(grid[0]) < 2:
        return 0
    header_val = grid[district_row][1].strip().lower() if district_row < len(grid) else ""
    # Also check the category-header row (row 0) if district_row > 0
    if district_row > 0 and len(grid[0]) > 1:
        cat_header = grid[0][1].strip().lower()
        if "use" in cat_header or "land" in cat_header:
            return 1
    if "use" in header_val or "land" in header_val:
        return 1
    return 0


def parse_use_table(
    grid: list[list[str]], section_ref: str = ""
) -> list[UsePermission]:
    """Convert a Type A use-matrix grid into UsePermission records.

    Detects the district-code row (may be row 0 or row 1) and the
    use-name column (may be column 0 or column 1).  Each interior
    cell becomes one UsePermission record.
    """
    if len(grid) < 2 or len(grid[0]) < 2:
        return []

    district_row = _find_district_row(grid)
    use_col = _find_use_name_col(grid, district_row)
    header = grid[district_row]

    # Identify district columns: those whose header cell is a district code
    districts: list[tuple[int, str]] = []
    for i in range(len(header)):
        code = header[i].strip()
        if _DISTRICT_PATTERN.match(code):
            districts.append((i, code))

    if not districts:
        # Fallback: treat all non-label columns as districts
        districts = [(i, header[i].strip()) for i in range(use_col + 1, len(header))
                     if header[i].strip()]

    # Data rows start after the district-code row
    data_start = district_row + 1

    records: list[UsePermission] = []
    for row in grid[data_start:]:
        use_name = row[use_col].strip() if use_col < len(row) else ""
        if not use_name:
            continue
        for col_idx, district in districts:
            if col_idx >= len(row):
                continue
            permission = row[col_idx].strip()
            if not permission or permission == "—" or permission == "-":
                permission = "—"
            records.append(
                UsePermission(
                    use_name=use_name,
                    district=district,
                    permission=permission,
                    conditions=section_ref,
                )
            )
    return records


def extract_all_use_permissions(docx_path: Path) -> list[UsePermission]:
    """Extract all use permissions from an Article XII .docx file.

    Classifies each table in the document and parses those identified
    as use matrices.
    """
    tables = extract_tables_xml(docx_path)
    records: list[UsePermission] = []
    for grid in tables:
        if classify_table(grid) == "use_matrix":
            records.extend(parse_use_table(grid))
    return records
