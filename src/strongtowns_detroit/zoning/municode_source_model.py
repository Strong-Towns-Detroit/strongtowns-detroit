"""Derived source model for a lossless Municode Chapter 50 snapshot.

The raw response files and manifest remain canonical. This module converts
Municode's HTML chunks into the paragraph/table block contract consumed by the
rule compiler while retaining node IDs, order, and raw HTML on every source
node for traceability.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from lxml import etree, html

SECTION_RE = re.compile(r"\b(?:Secs?\.?\s*)?(50-\d{1,2}-\d{1,4}(?:\.\d+)*)\b", re.I)
ARTICLE_RE = re.compile(r"ARTICLE\s+([IVXLCDM]+)", re.I)


class MunicodeSnapshotError(ValueError):
    """The canonical snapshot is absent or fails integrity checks."""


def latest_snapshot(root: Path) -> Path:
    manifests = sorted(Path(root).glob("*/manifest.json"))
    if not manifests:
        raise MunicodeSnapshotError(f"no Municode manifest under {root}")
    return manifests[-1].parent


def verify_snapshot(snapshot: Path) -> dict:
    manifest_path = Path(snapshot) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for record in manifest["files"]:
        path = Path(snapshot) / record["path"]
        if not path.exists():
            failures.append(f"missing {record['path']}")
            continue
        payload = path.read_bytes()
        if len(payload) != record["bytes"]:
            failures.append(f"byte count {record['path']}")
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            failures.append(f"sha256 {record['path']}")
    if failures:
        raise MunicodeSnapshotError("; ".join(failures))
    return manifest


def _clean_text(element: etree._Element) -> str:
    return re.sub(r"\s+", " ", element.text_content()).strip()


def _expand_table(table: etree._Element) -> list[list[str]]:
    """Expand HTML rowspan/colspan into the same rectangular grid as DOCX."""
    rows = table.xpath(".//tr")
    grid: list[list[str | None]] = []
    spans: dict[tuple[int, int], str] = {}
    for row_index, row in enumerate(rows):
        values: list[str | None] = []
        col = 0
        cells = row.xpath("./th|./td")
        for cell in cells:
            while (row_index, col) in spans:
                values.append(spans[(row_index, col)])
                col += 1
            value = _clean_text(cell)
            rowspan = max(1, int(cell.get("rowspan", "1")))
            colspan = max(1, int(cell.get("colspan", "1")))
            for offset in range(colspan):
                values.append(value)
                for future in range(1, rowspan):
                    spans[(row_index + future, col + offset)] = value
            col += colspan
        while (row_index, col) in spans:
            values.append(spans[(row_index, col)])
            col += 1
        grid.append(values)
    width = max((len(row) for row in grid), default=0)
    return [[cell or "" for cell in row] + [""] * (width - len(row)) for row in grid]


def _content_blocks(content: str) -> Iterable[tuple[str, object, str]]:
    """Yield ordered paragraph/table blocks plus their exact source HTML."""
    if not content:
        return
    root = html.fromstring(content)
    for element in root.xpath(".//p[not(ancestor::table)] | .//table"):
        if element.tag.lower() == "table":
            yield "table", _expand_table(element), html.tostring(element, encoding="unicode")
        else:
            # A paragraph used as a table wrapper can include the entire table
            # in malformed legacy HTML. Preserve its own label, not descendants.
            clone = html.fromstring(html.tostring(element, encoding="unicode"))
            for nested in clone.xpath(".//table|.//p"):
                nested.getparent().remove(nested)
            text = _clean_text(clone)
            if text:
                yield "paragraph", text, html.tostring(element, encoding="unicode")


def _document_name(heading: str, index: int) -> str:
    if heading.upper().startswith("APPENDIX A"):
        return "APPENDIX_A.municode.json"
    match = ARTICLE_RE.search(heading)
    return f"ARTICLE_{match.group(1).upper()}.municode.json" if match else f"PART_{index:02d}.municode.json"


def compile_municode_source_corpus(snapshot: Path) -> dict:
    snapshot = Path(snapshot)
    manifest = verify_snapshot(snapshot)
    documents = []
    section_index: set[str] = set()
    node_index: list[dict] = []
    for article_index, article in enumerate(manifest["articles"], 1):
        record = next(
            item for item in manifest["files"]
            if item["kind"] == "municode_api_response"
            and item["name"].startswith(f"article-{article_index:02d}-")
        )
        payload = json.loads((snapshot / record["path"]).read_text(encoding="utf-8"))
        blocks = []
        source_nodes = []
        source_index = 0
        for node in payload.get("Docs", []):
            title = node.get("Title", "")
            match = SECTION_RE.search(title)
            section = match.group(1) if match else None
            if section:
                section_index.add(section)
            provenance = {
                "municodeNodeId": node["Id"],
                "docOrderId": node.get("DocOrderId"),
                "nodeDepth": node.get("NodeDepth"),
                "section": section,
            }
            title_html = node.get("TitleHtml", "")
            if title:
                blocks.append({
                    "type": "paragraph",
                    "sourceIndex": source_index,
                    "style": "MunicodeTitle",
                    "text": title,
                    "sourceHtml": title_html,
                    **provenance,
                })
                source_index += 1
            for kind, value, source_html in _content_blocks(node.get("Content", "")):
                block = {
                    "type": kind,
                    "sourceIndex": source_index,
                    "sourceHtml": source_html,
                    **provenance,
                }
                block["text" if kind == "paragraph" else "rows"] = value
                if kind == "paragraph":
                    block["style"] = "MunicodeContent"
                blocks.append(block)
                source_index += 1
            source_nodes.append({
                **provenance,
                "title": title,
                "titleHtml": title_html,
                "contentHtml": node.get("Content", ""),
                "docType": node.get("DocType"),
                "isAmended": node.get("IsAmended"),
                "isUpdated": node.get("IsUpdated"),
                "compareStatus": node.get("CompareStatus"),
                "amendedBy": node.get("AmendedBy", []),
                "notes": node.get("Notes", []),
                "drafts": node.get("Drafts", []),
                "footnotes": node.get("Footnotes"),
            })
            node_index.append({
                "id": node["Id"], "title": title, "section": section,
                "docOrderId": node.get("DocOrderId"), "articleId": article["id"],
            })
        documents.append({
            "document": _document_name(article["heading"], article_index),
            "sourceFormat": "municode_api_html",
            "articleId": article["id"],
            "articleHeading": article["heading"],
            "rawResponsePath": record["path"],
            "rawResponseSha256": record["sha256"],
            "blocks": blocks,
            "sourceNodes": source_nodes,
        })
    return {
        "schemaVersion": "ordinance-source-v3-municode",
        "municipality": "Detroit",
        "chapter": "50",
        "canonicalSource": {
            "kind": "municode_snapshot",
            "snapshot": snapshot.name,
            "manifest": f"resources/municode/{snapshot.name}/manifest.json",
            "manifestSha256": hashlib.sha256(
                (snapshot / "manifest.json").read_bytes()
            ).hexdigest(),
            "jobId": manifest["jobId"],
            "jobName": manifest.get("jobName"),
            "latestUpdatedDate": manifest["latestUpdatedDate"],
            "pendingOrdinanceCountReported": manifest.get("pendingOrdinanceCountReported"),
        },
        "documents": documents,
        "sectionIndex": sorted(section_index, key=_section_key),
        "nodeIndex": sorted(node_index, key=lambda item: item["docOrderId"] or 0),
    }


def _section_key(section: str) -> tuple[int, ...]:
    return tuple(int(piece) for piece in re.findall(r"\d+", section))
