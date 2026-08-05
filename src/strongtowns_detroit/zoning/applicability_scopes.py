"""Compile Article XI district and overlay heading scopes."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.chapter_compiler import HEADING_RE

DIVISION_RE = re.compile(r"^DIVISION\s+(\d+)\.\s*(?:-\s*)?(.*)$", re.I)
SUBDIVISION_RE = re.compile(r"^Subdivision\s+([A-Z])\.\s*(?:-\s*)?(.*)$", re.I)
DISTRICT_CODE_RE = re.compile(r"^([A-Z]+\d*)\b")


def compile_applicability_scopes(source: dict) -> dict:
    document = next(
        item for item in source["documents"]
        if item["document"].startswith("ARTICLE_XI.")
    )
    scopes: list[dict] = []
    active: dict | None = None
    in_overlay_division = False
    for block in document["blocks"]:
        if block["type"] != "paragraph":
            continue
        division = DIVISION_RE.match(block["text"])
        subdivision = SUBDIVISION_RE.match(block["text"])
        if division:
            number, label = division.groups()
            in_overlay_division = int(number) == 14
            active = None
            if 2 <= int(number) <= 13:
                code_match = DISTRICT_CODE_RE.match(label)
                if not code_match:
                    raise ValueError(f"Article XI district code missing: {label}")
                active = _scope(
                    f"district:{code_match.group(1)}", "special_purpose_district",
                    label, block["sourceIndex"], code=code_match.group(1),
                )
                scopes.append(active)
            continue
        if subdivision and in_overlay_division:
            letter, label = subdivision.groups()
            active = _scope(
                f"overlay:{letter.lower()}", "overlay_area", label,
                block["sourceIndex"], subdivision=letter,
            )
            scopes.append(active)
            continue
        heading = HEADING_RE.match(block["text"])
        if heading and active is not None:
            active["sections"].append(heading.group(1))

    return {
        "schemaVersion": "zoning-applicability-scopes-v1",
        "sourceDocument": document["document"],
        "scopes": scopes,
        "coverage": {
            "specialPurposeDistricts": sum(
                item["kind"] == "special_purpose_district" for item in scopes
            ),
            "overlayAreas": sum(item["kind"] == "overlay_area" for item in scopes),
            "sectionsAssigned": sum(len(item["sections"]) for item in scopes),
        },
    }


def _scope(id: str, kind: str, label: str, source_index: int, **extra: str) -> dict:
    return {
        "id": id,
        "kind": kind,
        "label": label,
        "sourceIndex": source_index,
        "sections": [],
        "reviewStatus": "structurally_verified",
        **extra,
    }
