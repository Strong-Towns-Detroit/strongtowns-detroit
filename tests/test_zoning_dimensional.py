"""Tests for strongtowns_detroit.zoning.dimensional."""

import zipfile

import pytest

from strongtowns_detroit.zoning.dimensional import (
    _is_spanning_row,
    extract_all_dimensional_standards,
    parse_dimensional_table,
)

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class TestIsSpanningRow:
    def test_all_same(self):
        assert _is_spanning_row(["Lot Standards", "Lot Standards", "Lot Standards"]) is True

    def test_all_empty(self):
        assert _is_spanning_row(["", "", ""]) is True

    def test_single_value(self):
        assert _is_spanning_row(["Category", "", ""]) is True

    def test_different_values(self):
        assert _is_spanning_row(["R1", "5000", "40"]) is False

    def test_empty_row(self):
        assert _is_spanning_row([]) is False


class TestParseDimensionalTable:
    def test_basic_dimensional(self):
        grid = [
            ["District", "Minimum Lot Area", "Minimum Lot Width"],
            ["R1", "5,000 sq ft", "40 ft"],
            ["R2", "3,600 sq ft", "30 ft"],
        ]
        records = parse_dimensional_table(grid)
        assert len(records) == 4  # 2 districts × 2 standards

        r1_area = [r for r in records if r.district == "R1" and r.standard_name == "Minimum Lot Area"]
        assert len(r1_area) == 1
        assert r1_area[0].value == "5,000 sq ft"

    def test_spanning_rows_skipped(self):
        grid = [
            ["District", "Standard", "Value"],
            ["Lot Standards", "Lot Standards", "Lot Standards"],  # spanning row
            ["R1", "Min Area", "5000"],
        ]
        records = parse_dimensional_table(grid)
        assert len(records) == 2  # Only R1 row parsed
        assert all(r.district == "R1" for r in records)

    def test_section_ref(self):
        grid = [
            ["District", "Height"],
            ["R1", "35 ft"],
        ]
        records = parse_dimensional_table(grid, section_ref="50-13-201")
        assert records[0].section_ref == "50-13-201"

    def test_empty_values_skipped(self):
        grid = [
            ["District", "Area", "Width"],
            ["R1", "5000", ""],
        ]
        records = parse_dimensional_table(grid)
        assert len(records) == 1
        assert records[0].standard_name == "Area"

    def test_empty_district_skipped(self):
        grid = [
            ["District", "Area"],
            ["", "5000"],
            ["R1", "3000"],
        ]
        records = parse_dimensional_table(grid)
        assert len(records) == 1
        assert records[0].district == "R1"

    def test_too_small_grid(self):
        assert parse_dimensional_table([]) == []
        assert parse_dimensional_table([["X"]]) == []

    def test_merged_district_cells(self):
        """Simulates expanded vertical merge: same district repeated across rows."""
        grid = [
            ["District", "Standard", "Value"],
            ["R1", "Min Lot Area", "5,000 sq ft"],
            ["R1", "Min Lot Width", "40 ft"],  # Same district from vMerge expansion
            ["R2", "Min Lot Area", "3,600 sq ft"],
        ]
        records = parse_dimensional_table(grid)
        r1_records = [r for r in records if r.district == "R1"]
        assert len(r1_records) == 4  # 2 rows × 2 non-district columns


class TestExtractAllDimensionalStandards:
    def test_dimensional_table_extracted(self, tmp_path):
        """Create a .docx with a dimensional table."""
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>District</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Standard</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Minimum Lot Area</w:t></w:r></w:p></w:tc>"
            f"</w:tr><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>R1</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Lot Size</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>5,000 sq ft</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "article_xiii.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        records = extract_all_dimensional_standards(path)
        assert len(records) == 2
        assert records[0].district == "R1"

    def test_non_dimensional_skipped(self, tmp_path):
        """A 2-column lookup table should not be parsed."""
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Term</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Def</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "lookup.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        records = extract_all_dimensional_standards(path)
        assert records == []
