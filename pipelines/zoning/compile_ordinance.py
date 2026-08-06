#!/usr/bin/env python3
"""Compile ordinance sources and reviewed declarations to canonical JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_permissions import add_structural_permissions
from strongtowns_detroit.zoning.detroit_lexicon import add_structural_lexicon
from strongtowns_detroit.zoning.detroit_dimensions import add_structural_dimensions
from strongtowns_detroit.zoning.detroit_source_provisions import add_source_provisions
from strongtowns_detroit.zoning.chapter_compiler import compile_chapter_package
from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.ordinance import parse_ordinance
from strongtowns_detroit.zoning.source_model import compile_source_corpus
from strongtowns_detroit.zoning.municode_source_model import (
    compile_municode_source_corpus,
    latest_snapshot,
)
from strongtowns_detroit.zoning.cross_references import compile_cross_references
from strongtowns_detroit.zoning.detroit_text_candidates import add_text_candidates
from strongtowns_detroit.zoning.applicability_scopes import compile_applicability_scopes
from strongtowns_detroit.zoning.detroit_overlay_rules import add_gateway_overlay_prohibitions
from strongtowns_detroit.zoning.detroit_formulas import add_side_setback_formulas
from strongtowns_detroit.zoning.detroit_conditional_permissions import (
    add_reviewed_conditional_permissions,
)
from strongtowns_detroit.zoning.detroit_filling_station_dimensions import (
    add_filling_station_lot_standards,
    add_filling_station_general_standards,
)
from strongtowns_detroit.zoning.detroit_antenna_rules import add_reviewed_antenna_rules
from strongtowns_detroit.zoning.detroit_compound_dimensions import add_compound_side_yards
from strongtowns_detroit.zoning.detroit_recreational_space import (
    add_recreational_space_formulas,
)
from strongtowns_detroit.zoning.detroit_special_district_dimensions import (
    add_sd1_sd2_dimensions,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/zoning-ordinance"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=("municode", "docx"), default="municode",
        help="Canonical Municode snapshot (default) or legacy DOCX comparison source.",
    )
    parser.add_argument("--municode-snapshot", type=Path)
    args = parser.parse_args()
    if args.source == "municode":
        snapshot = args.municode_snapshot or latest_snapshot(ROOT / "resources/municode")
        source = compile_municode_source_corpus(snapshot)
    else:
        source = compile_source_corpus(ROOT / "resources")
    cross_references = compile_cross_references(source)
    applicability_scopes = compile_applicability_scopes(source)
    builder = build_detroit_code()
    structural_permissions = add_structural_permissions(builder, source)
    conditional_permissions = add_reviewed_conditional_permissions(builder)
    antenna_rules = add_reviewed_antenna_rules(builder)
    overlay_prohibitions = add_gateway_overlay_prohibitions(builder, source)
    structural_lexicon = add_structural_lexicon(builder, source)
    structural_dimensions = add_structural_dimensions(builder, source)
    computed_dimensions = add_side_setback_formulas(builder, source)
    filling_station_dimensions = add_filling_station_lot_standards(builder, source)
    filling_station_general = add_filling_station_general_standards(builder)
    compound_side_yards = add_compound_side_yards(builder, source)
    recreational_space_rules = add_recreational_space_formulas(builder, source)
    special_district_dimensions = add_sd1_sd2_dimensions(builder)
    source_provisions = add_source_provisions(builder, source)
    text_candidates = add_text_candidates(builder, source)
    executable = builder.compile()
    chapter = compile_chapter_package(source, executable)
    candidates = compile_candidates(source)
    extracted = parse_ordinance(ROOT / "resources")
    coverage = {
        "schemaVersion": "ordinance-coverage-v1",
        "source": {
            "format": source.get("canonicalSource", {}).get("kind", "legacy_docx"),
            "canonicalSource": source.get("canonicalSource"),
            "documents": len(source["documents"]),
            "sections": len(source["sectionIndex"]),
            "nodes": len(source.get("nodeIndex", [])),
            "blocks": sum(len(item["blocks"]) for item in source["documents"]),
            "tables": sum(
                block["type"] == "table"
                for item in source["documents"] for block in item["blocks"]
            ),
        },
        "legacyDocxMachineExtracted": {
            "usePermissionCells": len(extracted["use_permissions"]),
            "dimensionalCells": len(extracted["dimensional_standards"]),
            "definitions": len(extracted["definitions"]),
            "warning": "Legacy totals include known context and provenance errors.",
        },
        "provenanceCandidates": {
            key: candidates["coverage"][key]
            for key in ("permissions", "dimensions", "definitions", "useAssignments", "rejected")
        },
        "reviewedExecutable": {
            "districts": len(executable["districts"]),
            "uses": len(executable["uses"]),
            "rules": len(executable["rules"]),
            "verifiedRules": sum(
                item["review_status"] == "verified" for item in executable["rules"]
            ),
            "structurallyVerifiedDimensions": structural_dimensions,
            "computedDimensionRules": computed_dimensions,
            "reviewedFillingStationDimensionRules": filling_station_dimensions,
            "reviewedFillingStationGeneralRules": filling_station_general,
            "compoundSideYardRules": compound_side_yards,
            "recreationalSpaceRules": recreational_space_rules,
            "specialDistrictDimensionRules": special_district_dimensions,
            "structurallyVerifiedPermissions": structural_permissions,
            "reviewedConditionalPermissionBranches": conditional_permissions,
            "reviewedAntennaRules": antenna_rules,
            "verifiedOverlayProhibitions": overlay_prohibitions,
            "structurallyVerifiedDefinitions": structural_lexicon["definitions"],
            "structurallyVerifiedUseAssignments": structural_lexicon["useAssignments"],
            "sourceEncodedProvisions": source_provisions,
            "machineClassifiedTextProvisions": text_candidates,
            "scope": "Principal one- and two-family dwellings in R1-R6",
        },
        "warning": (
            "Source encoding is comprehensive. Machine candidates are not "
            "executable rules until normalized and reviewed."
        ),
    }
    write_json(OUTPUT / "source-corpus.json", source)
    write_json(OUTPUT / "executable-rules.json", executable)
    write_json(OUTPUT / "chapter-50-package.json", chapter)
    write_json(OUTPUT / "candidate-provisions.json", candidates)
    write_json(OUTPUT / "cross-references.json", cross_references)
    write_json(OUTPUT / "applicability-scopes.json", applicability_scopes)
    write_json(OUTPUT / "coverage.json", coverage)
    print(json.dumps({
        "documents": len(source["documents"]),
        "sourceSchema": source["schemaVersion"],
        "canonicalSource": source.get("canonicalSource"),
        "sections": len(source["sectionIndex"]),
        "sourceBlocks": sum(len(item["blocks"]) for item in source["documents"]),
        "executableRules": len(executable["rules"]),
        "verifiedRules": sum(
            item["review_status"] == "verified" for item in executable["rules"]
        ),
        "structuralDimensions": structural_dimensions,
        "computedDimensions": computed_dimensions,
        "fillingStationDimensions": filling_station_dimensions,
        "fillingStationGeneralRules": filling_station_general,
        "compoundSideYards": compound_side_yards,
        "recreationalSpaceRules": recreational_space_rules,
        "specialDistrictDimensions": special_district_dimensions,
        "structuralPermissions": structural_permissions,
        "conditionalPermissionBranches": conditional_permissions,
        "antennaRules": antenna_rules,
        "overlayProhibitions": overlay_prohibitions,
        "structuralDefinitions": structural_lexicon["definitions"],
        "structuralUseAssignments": structural_lexicon["useAssignments"],
        "sourceProvisions": source_provisions,
        "textCandidates": sum(text_candidates.values()),
        "crossReferences": cross_references["coverage"]["edges"],
        "missingInternalReferences": len(
            cross_references["coverage"]["missingInternalTargets"]
        ),
        "applicabilityScopes": len(applicability_scopes["scopes"]),
        "numberedSections": chapter["coverage"]["numberedSections"],
        "candidateProvisions": sum(
            candidates["coverage"][key]
            for key in ("permissions", "dimensions", "definitions", "useAssignments")
        ),
        "output": str(OUTPUT),
    }, indent=2))


if __name__ == "__main__":
    main()
