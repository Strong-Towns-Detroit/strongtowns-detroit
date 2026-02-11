"""Parse zoning use table CSV into structured JSON data."""

import csv


def parse_zoning_csv(csv_file):
    """Parse Detroit zoning use table CSV into structured JSON.

    Returns
    -------
    result : dict
        Nested dict: category -> specific_use -> {by_right, conditional, ...}
    use_categories : list[str]
        Ordered list of category names found.
    specific_uses : list[str]
        Ordered list of specific land use names found.
    """
    result = {}

    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Find all table starts (rows where first column is "Use Category")
    table_starts = []
    for i, row in enumerate(rows):
        if row and row[0] == "Use Category" and i + 1 < len(rows) and rows[i + 1][0] != "Use Category":
            table_starts.append(i)

    use_categories = []
    specific_uses = []

    # Process each table
    for table_idx, start_row_idx in enumerate(table_starts):
        header_row = rows[start_row_idx]

        # Extract zoning district columns (skip first 2: Use Category, Specific Land Use)
        districts = []
        district_indices = []

        for idx, cell in enumerate(header_row[2:], start=2):
            cell = cell.strip()
            if cell and not cell.startswith("Standards"):
                districts.append(cell)
                district_indices.append(idx)

        # Process data rows until next table or end
        end_row_idx = table_starts[table_idx + 1] if table_idx + 1 < len(table_starts) else len(rows)

        for row_idx in range(start_row_idx, end_row_idx):
            row = rows[row_idx]

            use_category = row[0].strip()
            if not row or not use_category or use_category == "Use Category":
                continue

            specific_use = row[1].strip() if len(row) > 1 else ""
            if not specific_use or specific_use == "Specific Land Use":
                continue
            specific_uses.append(specific_use)

            use_category = use_category.removesuffix(" (cont'd)")
            use_category = use_category.removesuffix(",")

            if use_category not in result:
                result[use_category] = {}
                use_categories.append(use_category)

            # Parse permissions for each district
            by_right = []
            conditional = []
            mixed = []

            for dist_idx, district in enumerate(districts):
                if district_indices[dist_idx] >= len(row):
                    continue

                permission = row[district_indices[dist_idx]].strip()

                if permission == 'R':
                    by_right.append(district)
                elif permission == 'C':
                    conditional.append(district)
                elif permission in ['C/R', 'R/C']:
                    mixed.append(district)

            if by_right or conditional or mixed:
                result[use_category][specific_use] = {}
                if by_right:
                    result[use_category][specific_use]["by_right"] = by_right
                if conditional:
                    result[use_category][specific_use]["conditional"] = conditional
                if mixed:
                    result[use_category][specific_use]["by_right_subject_to_conditions"] = mixed

    return result, use_categories, specific_uses
