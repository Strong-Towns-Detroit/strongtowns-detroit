"""Tests for get_cell_spans() and expand_table() from extract_tables_from_docx.py."""
from unittest.mock import MagicMock
from lxml import etree
import pytest

from strongtowns_detroit.parcels.docx_parser import get_cell_spans, expand_table

# Word Open XML namespace
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_NSMAP = {"w": W_NS}


class NsAwareElement:
    """Wrapper around an lxml element that auto-passes namespaces to xpath().

    python-docx's BaseOxmlElement overrides xpath() to include Word namespace
    mappings automatically. This wrapper replicates that behavior for testing.
    """

    def __init__(self, el):
        self._el = el

    def xpath(self, expr, **kwargs):
        kwargs.setdefault("namespaces", W_NSMAP)
        return self._el.xpath(expr, **kwargs)

    def __getattr__(self, name):
        return getattr(self._el, name)


def _build_tc_xml(grid_span=None, v_merge=None):
    """Build a <w:tc> XML string and parse it."""
    children = ""
    if grid_span is not None:
        children += f'<w:gridSpan w:val="{grid_span}"/>'
    if v_merge is not None:
        if v_merge == "":
            children += "<w:vMerge/>"  # continuation: no val attribute
        else:
            children += f'<w:vMerge w:val="{v_merge}"/>'

    xml = f'<w:tc xmlns:w="{W_NS}"><w:tcPr>{children}</w:tcPr></w:tc>'
    return etree.fromstring(xml.encode())


class FakeTableCell:
    """Mimics python-docx's CT_Tc with XPath-compatible namespace handling."""

    def __init__(self, grid_span=None, v_merge=None):
        self._el = _build_tc_xml(grid_span, v_merge)

    @property
    def tcPr(self):
        raw = self._el.find(f"{{{W_NS}}}tcPr")
        return NsAwareElement(raw)


def _make_mock_cell(text="", grid_span=None, v_merge=None):
    """Create a mock cell with ._element pointing to FakeTableCell."""
    cell = MagicMock()
    cell.text = text
    cell._element = FakeTableCell(grid_span, v_merge)
    return cell


class TestGetCellSpans:
    def test_normal_cell(self):
        cell = _make_mock_cell()
        row_span, col_span = get_cell_spans(cell)
        assert row_span == 1
        assert col_span == 1

    def test_horizontal_merge(self):
        cell = _make_mock_cell(grid_span=3)
        row_span, col_span = get_cell_spans(cell)
        assert col_span == 3
        assert row_span == 1

    def test_vertical_merge_start(self):
        cell = _make_mock_cell(v_merge="restart")
        row_span, col_span = get_cell_spans(cell)
        assert row_span is None  # Start of merge; expand_table resolves later
        assert col_span == 1

    def test_vertical_merge_continuation(self):
        cell = _make_mock_cell(v_merge="")  # continuation = no val attr
        row_span, col_span = get_cell_spans(cell)
        assert row_span == 0

    def test_combined_horizontal_and_vertical(self):
        cell = _make_mock_cell(grid_span=2, v_merge="restart")
        row_span, col_span = get_cell_spans(cell)
        assert col_span == 2
        assert row_span is None


class TestExpandTable:
    def _make_mock_table(self, rows_data):
        """Create a mock table from a list of lists of (text, grid_span, v_merge) tuples."""
        table = MagicMock()
        mock_rows = []
        for row_data in rows_data:
            row = MagicMock()
            cells = [_make_mock_cell(text=t, grid_span=gs, v_merge=vm) for t, gs, vm in row_data]
            row.cells = cells
            mock_rows.append(row)
        table.rows = mock_rows
        return table

    def test_simple_2x2(self):
        table = self._make_mock_table([
            [("A", None, None), ("B", None, None)],
            [("C", None, None), ("D", None, None)],
        ])
        grid = expand_table(table)
        assert grid == [["A", "B"], ["C", "D"]]

    def test_horizontal_span(self):
        """Cell spanning 2 columns should fill both cells."""
        table = self._make_mock_table([
            [("Header", 2, None)],
            [("C", None, None), ("D", None, None)],
        ])
        grid = expand_table(table)
        assert grid[0] == ["Header", "Header"]
        assert grid[1] == ["C", "D"]

    def test_vertical_merge(self):
        """Vertical merge: first row starts, second row continues."""
        table = self._make_mock_table([
            [("Merged", None, "restart"), ("B", None, None)],
            [("", None, ""), ("D", None, None)],
        ])
        grid = expand_table(table)
        assert grid[0] == ["Merged", "B"]
        assert grid[1] == ["Merged", "D"]  # continuation gets parent text

    def test_none_cells_filled_with_empty(self):
        """Any remaining None cells should become empty strings."""
        table = self._make_mock_table([
            [("A", None, None)],
        ])
        grid = expand_table(table)
        assert all(cell is not None for row in grid for cell in row)
