"""Parse Word document zoning use tables into expanded grids."""


def get_cell_spans(cell):
    """Return (row_span, col_span) for a docx cell by parsing its XML.

    row_span values:
        1    = normal cell
        None = start of vertical merge (caller resolves actual span)
        0    = continuation of vertical merge
    """
    tableCell = cell._element
    tableCellProps = tableCell.tcPr

    row_span = 1
    col_span = 1

    # Horizontal merge
    grid_span = tableCellProps.xpath("./w:gridSpan/@w:val")
    if grid_span:
        col_span = int(grid_span[0])

    # Vertical merge
    v_merge = tableCellProps.xpath("./w:vMerge/@w:val")
    if v_merge:
        if v_merge[0] == "restart":
            row_span = None  # Start of vertical merge
        else:
            row_span = 0  # Continuation cell
    elif tableCellProps.xpath("./w:vMerge"):
        # w:vMerge without val means continuation too
        row_span = 0

    return row_span, col_span


def expand_table(table):
    """Expand a Word table into a full 2D grid (list of lists),
    filling merged cells (horizontal and vertical) appropriately.
    """
    nrows = len(table.rows)

    # Calculate actual number of columns accounting for merged cells
    ncols = 0
    for row in table.rows:
        col_count = 0
        for cell in row.cells:
            _, col_span = get_cell_spans(cell)
            col_count += col_span
        ncols = max(ncols, col_count)

    grid = [[None for _ in range(ncols)] for _ in range(nrows)]
    vmerge_starts = {}  # (row, col): (text, col_span)

    for r, row in enumerate(table.rows):
        c = 0
        for cell in row.cells:
            while c < ncols and grid[r][c] is not None:
                c += 1

            text = cell.text.strip().replace("\n", " ").replace("\r", " ")
            row_span, col_span = get_cell_spans(cell)

            if row_span is None:
                # Start of vertical merge
                vmerge_starts[(r, c)] = (text, col_span)
                for j in range(c, c + col_span):
                    if j < ncols:
                        grid[r][j] = text
            elif row_span == 0:
                # Continuation of vertical merge
                above_r = r - 1
                while (above_r, c) not in vmerge_starts and above_r >= 0:
                    above_r -= 1
                if (above_r, c) in vmerge_starts:
                    text, col_span = vmerge_starts[(above_r, c)]
                    for j in range(c, c + col_span):
                        if j < ncols:
                            grid[r][j] = text
            else:
                # Normal cell
                for i in range(r, r + row_span):
                    for j in range(c, c + col_span):
                        if i < nrows and j < ncols:
                            grid[i][j] = text
            c += col_span

    # Fill any remaining None cells with ""
    for i in range(nrows):
        for j in range(ncols):
            if grid[i][j] is None:
                grid[i][j] = ""

    return grid
