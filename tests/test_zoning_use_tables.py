"""Tests for strongtowns_detroit.zoning.use_tables."""

import zipfile

import pytest

from strongtowns_detroit.zoning.use_tables import (
    extract_all_use_permissions,
    parse_use_table,
)

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class TestParseUseTable:
    def test_basic_matrix(self):
        grid = [
            ["Use", "R1", "R2", "B1"],
            ["One-family dwelling", "R", "R", "—"],
            ["Day care center", "C", "C/R", "R"],
        ]
        records = parse_use_table(grid)
        assert len(records) == 6  # 2 uses × 3 districts

        # Check specific records
        r1_dwelling = [r for r in records if r.use_name == "One-family dwelling" and r.district == "R1"]
        assert len(r1_dwelling) == 1
        assert r1_dwelling[0].permission == "R"

        b1_dwelling = [r for r in records if r.use_name == "One-family dwelling" and r.district == "B1"]
        assert len(b1_dwelling) == 1
        assert b1_dwelling[0].permission == "—"

    def test_dash_normalization(self):
        """Both '-' and '—' should normalize to '—'."""
        grid = [
            ["Use", "R1"],
            ["Thing", "-"],
        ]
        records = parse_use_table(grid)
        assert records[0].permission == "—"

    def test_empty_cells_become_dash(self):
        grid = [
            ["Use", "R1"],
            ["Thing", ""],
        ]
        records = parse_use_table(grid)
        assert records[0].permission == "—"

    def test_section_ref_passed_through(self):
        grid = [
            ["Use", "R1"],
            ["Dwelling", "R"],
        ]
        records = parse_use_table(grid, section_ref="50-12-101")
        assert records[0].conditions == "50-12-101"

    def test_empty_use_rows_skipped(self):
        grid = [
            ["Use", "R1"],
            ["", "R"],
            ["Dwelling", "C"],
        ]
        records = parse_use_table(grid)
        assert len(records) == 1
        assert records[0].use_name == "Dwelling"

    def test_too_small_grid(self):
        assert parse_use_table([]) == []
        assert parse_use_table([["Use"]]) == []
        assert parse_use_table([["Use", "R1"]]) == []  # No data rows

    def test_whitespace_stripped(self):
        grid = [
            ["  Use  ", "  R1  "],
            ["  Dwelling  ", "  R  "],
        ]
        records = parse_use_table(grid)
        assert records[0].use_name == "Dwelling"
        assert records[0].district == "R1"
        assert records[0].permission == "R"


class TestExtractAllUsePermissions:
    def _make_use_matrix_docx(self, tmp_path):
        """Create a .docx with a use matrix table (20+ columns with district codes)."""
        districts = [f"R{i}" for i in range(1, 7)] + [f"B{i}" for i in range(1, 7)] + [
            f"M{i}" for i in range(1, 6)
        ] + ["SD1", "SD2", "W1", "PC", "PCA", "TM"]
        header_tcs = '<w:tc><w:tcPr/><w:p><w:r><w:t>Use</w:t></w:r></w:p></w:tc>'
        for d in districts:
            header_tcs += f'<w:tc><w:tcPr/><w:p><w:r><w:t>{d}</w:t></w:r></w:p></w:tc>'

        data_tcs = '<w:tc><w:tcPr/><w:p><w:r><w:t>Dwelling</w:t></w:r></w:p></w:tc>'
        for _ in districts:
            data_tcs += '<w:tc><w:tcPr/><w:p><w:r><w:t>R</w:t></w:r></w:p></w:tc>'

        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl>"
            f"<w:tr>{header_tcs}</w:tr>"
            f"<w:tr>{data_tcs}</w:tr>"
            f"</w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "article_xii.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)
        return path

    def test_extract_from_docx(self, tmp_path):
        path = self._make_use_matrix_docx(tmp_path)
        records = extract_all_use_permissions(path)
        assert len(records) > 0
        assert all(r.use_name == "Dwelling" for r in records)
        assert all(r.permission == "R" for r in records)

    def test_non_use_tables_skipped(self, tmp_path):
        """A 2-column lookup table should not be parsed as a use matrix."""
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Term</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Definition</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "not_use.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)
        records = extract_all_use_permissions(path)
        assert records == []
