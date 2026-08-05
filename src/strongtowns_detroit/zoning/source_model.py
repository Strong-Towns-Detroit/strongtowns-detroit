"""Lossless-enough JSON source model for Detroit ordinance DOCX exports."""

from __future__ import annotations

import base64
import hashlib
import re
import zipfile
from pathlib import Path

from lxml import etree

from strongtowns_detroit.zoning.document import _para_style, _para_text
from strongtowns_detroit.zoning.table_parser import WNS, expand_table_xml

SECTION_RE = re.compile(r"^(?:Sec\.?\s*)?(50-\d{1,2}-\d{1,4}(?:\.\d+)*)\b", re.I)


def compile_source_document(path: Path, *, include_archive: bool = False) -> dict:
    """Preserve every nonempty paragraph and table in document order.

    The active section is inferred from ordinary paragraphs because the City
    DOCX export does not style numbered provisions as headings consistently.
    Raw text and table cells are never normalized in this layer.
    """
    archive_bytes = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{{{WNS}}}body")
    blocks: list[dict] = []
    active_section: str | None = None
    if body is None:
        return _source_document(path, archive_bytes, blocks, include_archive)
    for source_index, element in enumerate(body):
        kind = etree.QName(element.tag).localname
        if kind == "p":
            text = _para_text(element)
            if not text:
                continue
            match = SECTION_RE.match(text)
            if match:
                active_section = match.group(1)
            blocks.append({
                "type": "paragraph",
                "sourceIndex": source_index,
                "style": _para_style(element),
                "section": active_section,
                "text": text,
            })
        elif kind == "tbl":
            grid = expand_table_xml(element)
            if grid:
                blocks.append({
                    "type": "table",
                    "sourceIndex": source_index,
                    "section": active_section,
                    "rows": grid,
                })
    return _source_document(path, archive_bytes, blocks, include_archive)


def _source_document(
    path: Path,
    archive_bytes: bytes,
    blocks: list[dict],
    include_archive: bool,
) -> dict:
    document = {
        "document": path.name,
        "archiveSha256": hashlib.sha256(archive_bytes).hexdigest(),
        "archiveBytes": len(archive_bytes),
        "blocks": blocks,
    }
    if include_archive:
        document["archive"] = {
            "encoding": "base64",
            "data": base64.b64encode(archive_bytes).decode("ascii"),
        }
    return document


def compile_source_corpus(resources: Path, *, include_archives: bool = False) -> dict:
    documents = [
        compile_source_document(path, include_archive=include_archives)
        for path in sorted(Path(resources).glob("*.docx"))
    ]
    sections = sorted({
        block["section"]
        for document in documents
        for block in document["blocks"]
        if block.get("section")
    })
    return {
        "schemaVersion": "ordinance-source-v2",
        "municipality": "Detroit",
        "chapter": "50",
        "documents": documents,
        "sectionIndex": sections,
    }
