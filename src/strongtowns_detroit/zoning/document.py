"""Parse zoning ordinance .docx files into a section hierarchy.

Reads paragraph style names to determine heading levels and builds
a tree of SectionNode objects representing the document structure.
Tables encountered between headings are attached to the most recent
section node.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from pathlib import Path

from lxml import etree

from strongtowns_detroit.zoning.models import SectionNode
from strongtowns_detroit.zoning.table_parser import WNS, NSMAP, expand_table_xml

# Heading style name → level mapping
_HEADING_LEVELS: dict[str, int] = {
    "Heading3": 3,
    "Heading 3": 3,
    "Heading4": 4,
    "Heading 4": 4,
    "Heading5": 5,
    "Heading 5": 5,
}

# Styles that produce content paragraphs (not headings)
_CONTENT_STYLES = {
    "Section",
    "Paragraph1",
    "Paragraph 1",
    "List2",
    "List 2",
    "List3",
    "List 3",
    "List4",
    "List 4",
    "HistoryNote",
    "History Note",
}

# Section number pattern: "Sec. 50-12-101" or just "50-12-101"
_SECTION_NUM_RE = re.compile(r"(?:Sec\.?\s*)?(\d{2}-\d{1,2}-\d{1,4}(?:\.\d+)*)")


def _para_style(p: etree._Element) -> str:
    """Extract the style name from a <w:p> element."""
    style_els = p.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NSMAP)
    return style_els[0] if style_els else ""


def _para_text(p: etree._Element) -> str:
    """Extract all text from a <w:p> element."""
    runs = p.findall(f".//{{{WNS}}}r/{{{WNS}}}t")
    return "".join(r.text or "" for r in runs).strip()


def _extract_section_number(text: str) -> str:
    """Extract a section number like '50-12-101' from heading text."""
    m = _SECTION_NUM_RE.search(text)
    return m.group(1) if m else ""


def parse_document(docx_path: Path) -> list[SectionNode]:
    """Parse a zoning ordinance .docx into a section tree.

    Uses paragraph style names to determine hierarchy:
    - Heading 3 → Article level (level=3)
    - Heading 4 → Division level (level=4)
    - Heading 5 → Section level (level=5)
    - Other recognized styles → content paragraphs

    Tables encountered between headings are attached to the
    most recent section node via the XML-level table parser.
    """
    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = etree.fromstring(xml_bytes)
    body = root.find(f"{{{WNS}}}body")
    if body is None:
        return []

    # Walk all block-level children (paragraphs and tables)
    top_nodes: list[SectionNode] = []
    # Stack of (level, node) for building the tree
    stack: list[tuple[int, SectionNode]] = []

    def _current_node() -> SectionNode | None:
        return stack[-1][1] if stack else None

    for elem in body:
        tag = etree.QName(elem.tag).localname

        if tag == "p":
            style = _para_style(elem)
            text = _para_text(elem)

            level = _HEADING_LEVELS.get(style)
            if level is not None and text:
                # New heading → new SectionNode
                number = _extract_section_number(text)
                node = SectionNode(number=number, title=text, level=level)

                # Pop stack back to parent level
                while stack and stack[-1][0] >= level:
                    stack.pop()

                parent = _current_node()
                if parent is not None:
                    parent.children.append(node)
                else:
                    top_nodes.append(node)

                stack.append((level, node))

            elif text:
                # Content paragraph — attach to current section
                node = _current_node()
                if node is not None:
                    node.content.append(text)

        elif tag == "tbl":
            # Table — expand and attach to current section
            grid = expand_table_xml(elem)
            if grid:
                node = _current_node()
                if node is not None:
                    node.tables.append(grid)

    return top_nodes


def walk_sections(nodes: list[SectionNode]) -> Iterator[SectionNode]:
    """Depth-first traversal of a section tree."""
    for node in nodes:
        yield node
        yield from walk_sections(node.children)


def find_sections(nodes: list[SectionNode], pattern: str) -> list[SectionNode]:
    """Find sections whose number matches a regex pattern."""
    regex = re.compile(pattern)
    return [node for node in walk_sections(nodes) if regex.search(node.number)]
