"""Tests for strongtowns_detroit.zoning.table_parser."""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from lxml import etree

from strongtowns_detroit.zoning.table_parser import (
    WNS,
    NSMAP,
    _cell_text,
    _cell_grid_span,
    _cell_vmerge,
    classify_table,
    expand_table_xml,
    extract_tables_xml,
)


def _tc(text="", grid_span=None, v_merge=None):
    """Build a <w:tc> element with optional merge attributes."""
    tcPr_children = ""
    if grid_span is not None:
        tcPr_children += f'<w:gridSpan w:val="{grid_span}"/>'
    if v_merge is not None:
        if v_merge == "restart":
            tcPr_children += '<w:vMerge w:val="restart"/>'
        else:
            tcPr_children += "<w:vMerge/>"

    xml = (
        f'<w:tc xmlns:w="{WNS}">'
        f"<w:tcPr>{tcPr_children}</w:tcPr>"
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        f"</w:tc>"
    )
    return etree.fromstring(xml.encode())


def _tbl(*rows, grid_cols=None):
    """Build a <w:tbl> element from rows of <w:tc> elements.

    Each row is a list of (text, grid_span, v_merge) tuples.
    """
    parts = [f'<w:tbl xmlns:w="{WNS}">']
    if grid_cols:
        parts.append("<w:tblGrid>")
        for _ in range(grid_cols):
            parts.append("<w:gridCol/>")
        parts.append("</w:tblGrid>")
    for row_cells in rows:
        parts.append("<w:tr>")
        for text, gs, vm in row_cells:
            tcPr = ""
            if gs is not None:
                tcPr += f'<w:gridSpan w:val="{gs}"/>'
            if vm is not None:
                if vm == "restart":
                    tcPr += '<w:vMerge w:val="restart"/>'
                else:
                    tcPr += "<w:vMerge/>"
            parts.append(
                f"<w:tc><w:tcPr>{tcPr}</w:tcPr>"
                f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"
            )
        parts.append("</w:tr>")
    parts.append("</w:tbl>")
    return etree.fromstring("".join(parts).encode())


class TestCellHelpers:
    def test_cell_text_simple(self):
        tc = _tc("Hello world")
        assert _cell_text(tc) == "Hello world"

    def test_cell_text_empty(self):
        tc = _tc("")
        assert _cell_text(tc) == ""

    def test_cell_grid_span_default(self):
        tc = _tc("A")
        assert _cell_grid_span(tc) == 1

    def test_cell_grid_span_set(self):
        tc = _tc("A", grid_span=3)
        assert _cell_grid_span(tc) == 3

    def test_vmerge_none(self):
        tc = _tc("A")
        assert _cell_vmerge(tc) is None

    def test_vmerge_restart(self):
        tc = _tc("A", v_merge="restart")
        assert _cell_vmerge(tc) == "restart"

    def test_vmerge_continue(self):
        tc = _tc("A", v_merge="continue")
        assert _cell_vmerge(tc) == "continue"


class TestExpandTableXml:
    def test_simple_2x2(self):
        tbl = _tbl(
            [("A", None, None), ("B", None, None)],
            [("C", None, None), ("D", None, None)],
        )
        grid = expand_table_xml(tbl)
        assert grid == [["A", "B"], ["C", "D"]]

    def test_horizontal_span(self):
        tbl = _tbl(
            [("Header", 2, None)],
            [("C", None, None), ("D", None, None)],
            grid_cols=2,
        )
        grid = expand_table_xml(tbl)
        assert grid[0] == ["Header", "Header"]
        assert grid[1] == ["C", "D"]

    def test_vertical_merge(self):
        tbl = _tbl(
            [("Merged", None, "restart"), ("B", None, None)],
            [("", None, "continue"), ("D", None, None)],
            grid_cols=2,
        )
        grid = expand_table_xml(tbl)
        assert grid[0] == ["Merged", "B"]
        assert grid[1] == ["Merged", "D"]

    def test_combined_span_and_merge(self):
        """Horizontal span + vertical merge."""
        tbl = _tbl(
            [("Wide", 2, "restart"), ("C", None, None)],
            [("", 2, "continue"), ("F", None, None)],
            grid_cols=3,
        )
        grid = expand_table_xml(tbl)
        assert grid[0] == ["Wide", "Wide", "C"]
        assert grid[1] == ["Wide", "Wide", "F"]

    def test_empty_table(self):
        tbl = etree.fromstring(f'<w:tbl xmlns:w="{WNS}"></w:tbl>'.encode())
        grid = expand_table_xml(tbl)
        assert grid == []

    def test_grid_dimensions(self):
        """3 rows x 4 cols."""
        tbl = _tbl(
            [("A", None, None), ("B", None, None), ("C", None, None), ("D", None, None)],
            [("E", None, None), ("F", None, None), ("G", None, None), ("H", None, None)],
            [("I", None, None), ("J", None, None), ("K", None, None), ("L", None, None)],
        )
        grid = expand_table_xml(tbl)
        assert len(grid) == 3
        assert all(len(row) == 4 for row in grid)

    def test_three_row_vertical_merge(self):
        """Vertical merge spanning 3 rows."""
        tbl = _tbl(
            [("Start", None, "restart"), ("B1", None, None)],
            [("", None, "continue"), ("B2", None, None)],
            [("", None, "continue"), ("B3", None, None)],
            grid_cols=2,
        )
        grid = expand_table_xml(tbl)
        assert grid[0][0] == "Start"
        assert grid[1][0] == "Start"
        assert grid[2][0] == "Start"
        assert [row[1] for row in grid] == ["B1", "B2", "B3"]


class TestExtractTablesXml:
    def test_extracts_from_docx(self, tmp_path):
        """Create a minimal .docx ZIP and extract its table."""
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}">'
            f"<w:body>"
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>World</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        docx_path = tmp_path / "test.docx"
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        tables = extract_tables_xml(docx_path)
        assert len(tables) == 1
        assert tables[0] == [["Hello", "World"]]

    def test_multiple_tables(self, tmp_path):
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>T1</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>T2</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        docx_path = tmp_path / "test.docx"
        with zipfile.ZipFile(docx_path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        tables = extract_tables_xml(docx_path)
        assert len(tables) == 2


class TestClassifyTable:
    def test_use_matrix(self):
        header = ["Use"] + [f"R{i}" for i in range(1, 7)] + [f"B{i}" for i in range(1, 7)] + [
            f"M{i}" for i in range(1, 6)
        ] + ["SD1", "SD2", "W1", "PC", "PCA", "TM"]
        grid = [header, ["Dwelling"] + ["R"] * (len(header) - 1)]
        assert classify_table(grid) == "use_matrix"

    def test_lookup(self):
        grid = [["Term", "Definition"], ["Lot", "A parcel of land"]]
        assert classify_table(grid) == "lookup"

    def test_dimensional(self):
        grid = [["District", "Standard", "Minimum Lot Area"], ["R1", "Lot Area", "5000"]]
        assert classify_table(grid) == "dimensional"

    def test_unknown_empty(self):
        assert classify_table([]) == "unknown"
        assert classify_table([[]]) == "unknown"

    def test_unknown_no_match(self):
        grid = [["Foo", "Bar", "Baz", "Qux"], ["1", "2", "3", "4"]]
        assert classify_table(grid) == "unknown"
