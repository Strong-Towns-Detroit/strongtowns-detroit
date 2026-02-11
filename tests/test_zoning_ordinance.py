"""Tests for strongtowns_detroit.zoning.ordinance."""

import csv
import json
import zipfile

import pytest

from strongtowns_detroit.zoning.models import (
    DimensionalStandard,
    UsePermission,
    ZoningDefinition,
)
from strongtowns_detroit.zoning.ordinance import (
    export_to_csv,
    export_to_json,
    parse_ordinance,
)

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_docx(path, body_xml):
    """Create a minimal .docx with given body XML."""
    doc_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{WNS}">'
        f"<w:body>{body_xml}</w:body>"
        f"</w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", doc_xml)


def _heading(level, text):
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Heading {level}"/></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def _use_matrix_table():
    """Generate a small use-matrix table XML (>20 columns with district codes)."""
    districts = [f"R{i}" for i in range(1, 7)] + [f"B{i}" for i in range(1, 7)] + [
        f"M{i}" for i in range(1, 6)
    ] + ["SD1", "SD2", "W1", "PC", "PCA", "TM"]
    header_tcs = '<w:tc><w:tcPr/><w:p><w:r><w:t>Use</w:t></w:r></w:p></w:tc>'
    for d in districts:
        header_tcs += f'<w:tc><w:tcPr/><w:p><w:r><w:t>{d}</w:t></w:r></w:p></w:tc>'
    data_tcs = '<w:tc><w:tcPr/><w:p><w:r><w:t>Dwelling</w:t></w:r></w:p></w:tc>'
    for _ in districts:
        data_tcs += '<w:tc><w:tcPr/><w:p><w:r><w:t>R</w:t></w:r></w:p></w:tc>'
    return f"<w:tbl><w:tr>{header_tcs}</w:tr><w:tr>{data_tcs}</w:tr></w:tbl>"


def _dimensional_table():
    """Generate a dimensional standards table XML."""
    return (
        "<w:tbl><w:tr>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>District</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>Standard</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>Minimum Lot Area</w:t></w:r></w:p></w:tc>"
        "</w:tr><w:tr>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>R1</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>Lot</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>5000</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
    )


def _lookup_table():
    """Generate a 2-column lookup table XML."""
    return (
        "<w:tbl><w:tr>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>Lot</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:tcPr/><w:p><w:r><w:t>A parcel of land</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
    )


class TestParseOrdinance:
    def test_aggregates_all_types(self, tmp_path):
        """Parse a directory with files containing each table type."""
        # Article XII-like file with use matrix
        _make_docx(
            tmp_path / "article_xii.docx",
            _heading(3, "Article XII") + _use_matrix_table(),
        )
        # Article XIII-like file with dimensional table
        _make_docx(
            tmp_path / "article_xiii.docx",
            _heading(3, "Article XIII") + _dimensional_table(),
        )
        # Article XVI-like file with definitions
        _make_docx(
            tmp_path / "article_xvi.docx",
            _heading(3, "Article XVI") + _lookup_table(),
        )

        data = parse_ordinance(tmp_path)

        assert len(data["sections"]) == 3  # 3 articles
        assert len(data["use_permissions"]) > 0
        assert len(data["dimensional_standards"]) > 0
        assert len(data["definitions"]) > 0

    def test_empty_directory(self, tmp_path):
        data = parse_ordinance(tmp_path)
        assert data["sections"] == []
        assert data["use_permissions"] == []
        assert data["dimensional_standards"] == []
        assert data["definitions"] == []


class TestExportToJson:
    def test_creates_json_files(self, tmp_path):
        data = {
            "sections": [],
            "use_permissions": [
                UsePermission(use_name="Dwelling", district="R1", permission="R")
            ],
            "dimensional_standards": [
                DimensionalStandard(district="R1", standard_name="Lot Area", value="5000")
            ],
            "definitions": [
                ZoningDefinition(term="Lot", definition="A parcel")
            ],
        }
        output_dir = tmp_path / "output"
        export_to_json(data, output_dir)

        assert (output_dir / "use_permissions.json").exists()
        assert (output_dir / "dimensional_standards.json").exists()
        assert (output_dir / "definitions.json").exists()
        assert (output_dir / "sections.json").exists()

        # Verify JSON is valid
        with open(output_dir / "use_permissions.json") as f:
            loaded = json.load(f)
        assert len(loaded) == 1
        assert loaded[0]["use_name"] == "Dwelling"

    def test_sections_serialized(self, tmp_path):
        from strongtowns_detroit.zoning.models import SectionNode

        child = SectionNode(number="50-12-101", title="Uses", level=5, content=["text"])
        parent = SectionNode(number="50-12-100", title="Div 1", level=4, children=[child])
        data = {
            "sections": [parent],
            "use_permissions": [],
            "dimensional_standards": [],
            "definitions": [],
        }
        output_dir = tmp_path / "output"
        export_to_json(data, output_dir)

        with open(output_dir / "sections.json") as f:
            loaded = json.load(f)
        assert len(loaded) == 1
        assert loaded[0]["title"] == "Div 1"
        assert len(loaded[0]["children"]) == 1
        assert loaded[0]["children"][0]["content"] == ["text"]


class TestExportToCsv:
    def test_creates_csv_files(self, tmp_path):
        data = {
            "sections": [],
            "use_permissions": [
                UsePermission(use_name="Dwelling", district="R1", permission="R")
            ],
            "dimensional_standards": [
                DimensionalStandard(district="R1", standard_name="Lot Area", value="5000")
            ],
            "definitions": [
                ZoningDefinition(term="Lot", definition="A parcel")
            ],
        }
        output_dir = tmp_path / "output"
        export_to_csv(data, output_dir)

        assert (output_dir / "use_permissions.csv").exists()
        assert (output_dir / "dimensional_standards.csv").exists()
        assert (output_dir / "definitions.csv").exists()

        # Verify CSV is valid
        with open(output_dir / "use_permissions.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["use_name"] == "Dwelling"
        assert rows[0]["district"] == "R1"

    def test_empty_records(self, tmp_path):
        data = {
            "sections": [],
            "use_permissions": [],
            "dimensional_standards": [],
            "definitions": [],
        }
        output_dir = tmp_path / "output"
        export_to_csv(data, output_dir)

        with open(output_dir / "use_permissions.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows == []
