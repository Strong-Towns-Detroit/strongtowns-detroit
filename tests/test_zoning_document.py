"""Tests for strongtowns_detroit.zoning.document."""

import zipfile

import pytest

from strongtowns_detroit.zoning.document import (
    find_sections,
    parse_document,
    walk_sections,
)
from strongtowns_detroit.zoning.models import SectionNode

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _make_docx(tmp_path, body_xml, filename="test.docx"):
    """Create a minimal .docx with given body XML content."""
    doc_xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<w:document xmlns:w="{WNS}">'
        f"<w:body>{body_xml}</w:body>"
        f"</w:document>"
    )
    path = tmp_path / filename
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", doc_xml)
    return path


def _heading(level, text):
    """Generate XML for a heading paragraph."""
    return (
        f'<w:p><w:pPr><w:pStyle w:val="Heading {level}"/></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def _para(text, style="Section"):
    """Generate XML for a content paragraph."""
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def _table(cells):
    """Generate XML for a simple 1-row table."""
    tcs = ""
    for text in cells:
        tcs += f"<w:tc><w:tcPr/><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>"
    return f"<w:tbl><w:tr>{tcs}</w:tr></w:tbl>"


class TestParseDocument:
    def test_single_heading(self, tmp_path):
        body = _heading(3, "Article XII Use Regulations")
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert len(nodes) == 1
        assert nodes[0].title == "Article XII Use Regulations"
        assert nodes[0].level == 3

    def test_section_number_extraction(self, tmp_path):
        body = _heading(5, "Sec. 50-12-101 Permitted Uses")
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert nodes[0].number == "50-12-101"

    def test_nested_hierarchy(self, tmp_path):
        body = (
            _heading(3, "Article XII")
            + _heading(4, "Division 1")
            + _heading(5, "Sec. 50-12-101 Uses")
            + _heading(5, "Sec. 50-12-102 Standards")
            + _heading(4, "Division 2")
            + _heading(5, "Sec. 50-12-201 Other Uses")
        )
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)

        assert len(nodes) == 1  # One article
        article = nodes[0]
        assert len(article.children) == 2  # Two divisions
        assert len(article.children[0].children) == 2  # Div 1 has 2 sections
        assert len(article.children[1].children) == 1  # Div 2 has 1 section

    def test_content_attached_to_section(self, tmp_path):
        body = (
            _heading(5, "Sec. 50-12-101 Uses")
            + _para("Residential uses are permitted.")
            + _para("See table below.", style="Paragraph 1")
        )
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert len(nodes[0].content) == 2
        assert "Residential" in nodes[0].content[0]

    def test_table_attached_to_section(self, tmp_path):
        body = (
            _heading(5, "Sec. 50-12-101 Uses")
            + _table(["R1", "R2", "R3"])
        )
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert len(nodes[0].tables) == 1
        assert nodes[0].tables[0] == [["R1", "R2", "R3"]]

    def test_empty_document(self, tmp_path):
        path = _make_docx(tmp_path, "")
        nodes = parse_document(path)
        assert nodes == []

    def test_heading_without_section_number(self, tmp_path):
        body = _heading(3, "Article XII Use Regulations")
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert nodes[0].number == ""

    def test_sibling_articles(self, tmp_path):
        body = (
            _heading(3, "Article XII")
            + _heading(3, "Article XIII")
        )
        path = _make_docx(tmp_path, body)
        nodes = parse_document(path)
        assert len(nodes) == 2


class TestWalkSections:
    def test_flat_list(self):
        nodes = [
            SectionNode(number="1", title="A", level=3),
            SectionNode(number="2", title="B", level=3),
        ]
        titles = [n.title for n in walk_sections(nodes)]
        assert titles == ["A", "B"]

    def test_nested(self):
        child = SectionNode(number="1.1", title="Child", level=4)
        parent = SectionNode(number="1", title="Parent", level=3, children=[child])
        titles = [n.title for n in walk_sections([parent])]
        assert titles == ["Parent", "Child"]

    def test_deep_nesting(self):
        leaf = SectionNode(number="1.1.1", title="Leaf", level=5)
        mid = SectionNode(number="1.1", title="Mid", level=4, children=[leaf])
        root = SectionNode(number="1", title="Root", level=3, children=[mid])
        all_nodes = list(walk_sections([root]))
        assert len(all_nodes) == 3
        assert [n.title for n in all_nodes] == ["Root", "Mid", "Leaf"]


class TestFindSections:
    def test_find_by_number(self):
        nodes = [
            SectionNode(number="50-12-101", title="Uses", level=5),
            SectionNode(number="50-12-102", title="Standards", level=5),
            SectionNode(number="50-13-101", title="Dimensional", level=5),
        ]
        result = find_sections(nodes, r"50-12")
        assert len(result) == 2

    def test_find_in_nested(self):
        child = SectionNode(number="50-12-101", title="Uses", level=5)
        parent = SectionNode(number="50-12-100", title="Division", level=4, children=[child])
        result = find_sections([parent], r"50-12-101")
        assert len(result) == 1
        assert result[0].title == "Uses"

    def test_no_match(self):
        nodes = [SectionNode(number="50-12-101", title="Uses", level=5)]
        result = find_sections(nodes, r"99-99")
        assert result == []
