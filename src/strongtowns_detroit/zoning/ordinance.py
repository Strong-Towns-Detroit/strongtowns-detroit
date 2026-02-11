"""Orchestrator for parsing the full Detroit Zoning Ordinance.

Ties together all individual parsers (use tables, dimensional standards,
definitions, document structure) into a single entry point that processes
the complete ordinance from .docx files and exports to JSON/CSV.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from strongtowns_detroit.zoning.definitions import extract_all_definitions
from strongtowns_detroit.zoning.dimensional import extract_all_dimensional_standards
from strongtowns_detroit.zoning.document import parse_document, walk_sections
from strongtowns_detroit.zoning.models import (
    DimensionalStandard,
    SectionNode,
    UsePermission,
    ZoningDefinition,
)
from strongtowns_detroit.zoning.use_tables import extract_all_use_permissions


def parse_ordinance(resources_dir: Path) -> dict:
    """Parse the entire Detroit Zoning Ordinance from .docx files.

    Scans *resources_dir* for .docx files, parses each one for
    document structure and structured data, and returns aggregated results.

    Returns a dict with:
    - 'sections': list of SectionNode trees (all articles)
    - 'use_permissions': list[UsePermission]
    - 'dimensional_standards': list[DimensionalStandard]
    - 'definitions': list[ZoningDefinition]
    """
    resources_dir = Path(resources_dir)
    docx_files = sorted(resources_dir.glob("*.docx"))

    all_sections: list[SectionNode] = []
    all_use: list[UsePermission] = []
    all_dim: list[DimensionalStandard] = []
    all_def: list[ZoningDefinition] = []

    for docx_path in docx_files:
        # Parse document structure
        sections = parse_document(docx_path)
        all_sections.extend(sections)

        # Extract structured data (each function classifies internally)
        all_use.extend(extract_all_use_permissions(docx_path))
        all_dim.extend(extract_all_dimensional_standards(docx_path))
        all_def.extend(extract_all_definitions(docx_path))

    return {
        "sections": all_sections,
        "use_permissions": all_use,
        "dimensional_standards": all_dim,
        "definitions": all_def,
    }


def _section_to_dict(node: SectionNode) -> dict:
    """Recursively convert a SectionNode to a JSON-serializable dict."""
    return {
        "number": node.number,
        "title": node.title,
        "level": node.level,
        "content": node.content,
        "tables": node.tables,
        "children": [_section_to_dict(c) for c in node.children],
    }


def export_to_json(data: dict, output_dir: Path) -> None:
    """Export parsed ordinance data to JSON files.

    Creates:
    - use_permissions.json
    - dimensional_standards.json
    - definitions.json
    - sections.json
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "use_permissions.json", "w") as f:
        json.dump([asdict(r) for r in data["use_permissions"]], f, indent=2)

    with open(output_dir / "dimensional_standards.json", "w") as f:
        json.dump([asdict(r) for r in data["dimensional_standards"]], f, indent=2)

    with open(output_dir / "definitions.json", "w") as f:
        json.dump([asdict(r) for r in data["definitions"]], f, indent=2)

    with open(output_dir / "sections.json", "w") as f:
        json.dump([_section_to_dict(s) for s in data["sections"]], f, indent=2)


def export_to_csv(data: dict, output_dir: Path) -> None:
    """Export parsed ordinance data to CSV files.

    Creates:
    - use_permissions.csv
    - dimensional_standards.csv
    - definitions.csv
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        output_dir / "use_permissions.csv",
        ["use_name", "district", "permission", "conditions"],
        data["use_permissions"],
    )
    _write_csv(
        output_dir / "dimensional_standards.csv",
        ["district", "standard_name", "value", "section_ref"],
        data["dimensional_standards"],
    )
    _write_csv(
        output_dir / "definitions.csv",
        ["term", "definition", "section_ref"],
        data["definitions"],
    )


def _write_csv(path: Path, fieldnames: list[str], records: list) -> None:
    """Write dataclass records to a CSV file."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
