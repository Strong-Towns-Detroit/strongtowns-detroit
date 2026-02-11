"""Tests for strongtowns_detroit.zoning.definitions."""

import zipfile

import pytest

from strongtowns_detroit.zoning.definitions import (
    extract_all_definitions,
    parse_definition_table,
)

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class TestParseDefinitionTable:
    def test_basic_definitions(self):
        grid = [
            ["Term", "Definition"],
            ["Lot", "A parcel of land"],
            ["Setback", "The minimum distance from a property line"],
        ]
        records = parse_definition_table(grid)
        assert len(records) == 2
        assert records[0].term == "Lot"
        assert records[0].definition == "A parcel of land"

    def test_header_detection(self):
        """Header row with 'Term' should be skipped."""
        grid = [
            ["Term", "Definition"],
            ["Lot", "A parcel"],
        ]
        records = parse_definition_table(grid)
        assert len(records) == 1
        assert records[0].term == "Lot"

    def test_no_header_row(self):
        """If first row doesn't look like a header, treat it as data."""
        grid = [
            ["Lot", "A parcel of land"],
            ["Setback", "Distance from property line"],
        ]
        records = parse_definition_table(grid)
        assert len(records) == 2
        assert records[0].term == "Lot"

    def test_empty_term_skipped(self):
        grid = [
            ["Lot", "A parcel"],
            ["", "Orphaned definition"],
            ["Setback", "Distance"],
        ]
        records = parse_definition_table(grid)
        assert len(records) == 2

    def test_empty_definition_kept(self):
        """A term with no definition should still be recorded."""
        grid = [
            ["Lot", ""],
        ]
        records = parse_definition_table(grid)
        assert len(records) == 1
        assert records[0].definition == ""

    def test_section_ref(self):
        grid = [
            ["Lot", "A parcel"],
        ]
        records = parse_definition_table(grid, section_ref="50-16-100")
        assert records[0].section_ref == "50-16-100"

    def test_whitespace_stripped(self):
        grid = [
            ["  Lot  ", "  A parcel of land  "],
        ]
        records = parse_definition_table(grid)
        assert records[0].term == "Lot"
        assert records[0].definition == "A parcel of land"

    def test_too_small_grid(self):
        assert parse_definition_table([]) == []
        assert parse_definition_table([["Term", "Def"]]) == []  # Header only


class TestExtractAllDefinitions:
    def test_definitions_from_docx(self, tmp_path):
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl>"
            f"<w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Term</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Definition</w:t></w:r></w:p></w:tc>"
            f"</w:tr>"
            f"<w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>Lot</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>A parcel of land</w:t></w:r></w:p></w:tc>"
            f"</w:tr>"
            f"</w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "article_xvi.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        records = extract_all_definitions(path)
        assert len(records) == 1
        assert records[0].term == "Lot"

    def test_non_lookup_tables_skipped(self, tmp_path):
        """A multi-column table should not be parsed as definitions."""
        doc_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<w:document xmlns:w="{WNS}"><w:body>'
            f"<w:tbl><w:tr>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc>"
            f"<w:tc><w:tcPr/><w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc>"
            f"</w:tr></w:tbl>"
            f"</w:body></w:document>"
        )
        path = tmp_path / "not_lookup.docx"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("word/document.xml", doc_xml)

        records = extract_all_definitions(path)
        assert records == []
