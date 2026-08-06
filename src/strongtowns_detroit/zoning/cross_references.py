"""Source-model citation graph with explicit resolution states."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict

from strongtowns_detroit.zoning.citations import extract_citations

RESERVED_RANGE_RE = re.compile(
    r"^Secs?\.\s*(50-\d{1,2}-\d{1,4}(?:\.\d+)*)[—–-]"
    r"(50-\d{1,2}-\d{1,4}(?:\.\d+)*)\.\s*(?:-\s*)?Reserved\.?$",
    re.I,
)


def compile_cross_references(source: dict) -> dict:
    sections = set(source["sectionIndex"])
    reserved_ranges = _reserved_ranges(source)
    edges: list[dict] = []
    resolution_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()

    for document in source["documents"]:
        for block in document["blocks"]:
            if block["type"] != "paragraph":
                continue
            block_id = f"{document['document']}:{block['sourceIndex']}"
            for offset, citation in enumerate(extract_citations(
                block["text"], block.get("section") or ""
            )):
                citation_type = citation.citation_type.value
                resolution = _resolution(
                    citation_type, citation.target, sections, reserved_ranges
                )
                row = {
                    "id": f"{block_id}:citation:{offset}",
                    "sourceBlockId": block_id,
                    "sourceDocument": document["document"],
                    "sourceSection": block.get("section"),
                    "target": citation.target,
                    "type": citation_type,
                    "rawText": citation.raw_text,
                    "resolution": resolution,
                }
                edges.append(row)
                resolution_counts[resolution] += 1
                type_counts[citation_type] += 1

    return {
        "schemaVersion": "ordinance-cross-references-v1",
        "sections": sorted(sections, key=_section_key),
        "reservedRanges": reserved_ranges,
        "edges": edges,
        "coverage": {
            "edges": len(edges),
            "types": dict(sorted(type_counts.items())),
            "resolution": dict(sorted(resolution_counts.items())),
            "missingInternalTargets": sorted({
                edge["target"] for edge in edges
                if edge["resolution"] == "missing_internal_target"
            }, key=_section_key),
        },
    }


def _reserved_ranges(source: dict) -> list[dict]:
    ranges: list[dict] = []
    for document in source["documents"]:
        for block in document["blocks"]:
            if block["type"] != "paragraph":
                continue
            match = RESERVED_RANGE_RE.match(block["text"])
            if match:
                ranges.append({
                    "start": match.group(1),
                    "end": match.group(2),
                    "sourceDocument": document["document"],
                    "sourceIndex": block["sourceIndex"],
                })
    return ranges


def _resolution(
    citation_type: str,
    target: str,
    sections: set[str],
    reserved_ranges: list[dict],
) -> str:
    if citation_type == "section":
        if target in sections:
            return "resolved_section"
        if any(_in_range(target, item["start"], item["end"]) for item in reserved_ranges):
            return "resolved_reserved_section"
        return "missing_internal_target"
    if citation_type in {"figure", "table_ref"}:
        section = target.split(":", 1)[1]
        return "resolved_anchored_item" if section in sections else "missing_internal_target"
    if citation_type in {"self_ref", "article", "division", "subdivision"}:
        return "contextual_reference"
    return "external_reference"


def _in_range(value: str, start: str, end: str) -> bool:
    value_key, start_key, end_key = map(_section_key, (value, start, end))
    return start_key <= value_key <= end_key


def _section_key(section: str) -> tuple[int, ...]:
    value = section.split(":", 1)[-1]
    chapter, article, provision = value.split("-")
    return (int(chapter), int(article), *(int(piece) for piece in provision.split(".")))
