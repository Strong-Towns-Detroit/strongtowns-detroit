#!/usr/bin/env python3
"""Fail-fast audit of Chapter 50 source, candidate, and review coverage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/zoning-ordinance"


def main() -> None:
    source = json.loads((DATA / "source-corpus.json").read_text())
    chapter = json.loads((DATA / "chapter-50-package.json").read_text())
    candidates = json.loads((DATA / "candidate-provisions.json").read_text())
    executable = json.loads((DATA / "executable-rules.json").read_text())
    cross_references = json.loads((DATA / "cross-references.json").read_text())
    applicability = json.loads((DATA / "applicability-scopes.json").read_text())

    source_blocks = sum(len(document["blocks"]) for document in source["documents"])
    represented = sum(len(section["provisions"]) for section in chapter["sections"])
    represented += len(chapter["unsectionedBlocks"])
    errors: list[str] = []
    if source.get("schemaVersion") != "ordinance-source-v3-municode":
        errors.append("canonical build is not using the Municode source model")
    if source.get("canonicalSource", {}).get("kind") != "municode_snapshot":
        errors.append("canonical Municode snapshot provenance is missing")
    node_count = sum(
        len(document.get("sourceNodes", [])) for document in source["documents"]
    )
    if node_count != len(source.get("nodeIndex", [])):
        errors.append("Municode node index does not match retained source nodes")
    if represented != source_blocks:
        errors.append(f"source block loss: {represented} represented / {source_blocks} source")
    if chapter["coverage"]["reviewedRulesWithoutSourceSection"]:
        errors.append("reviewed rules exist without source-section links")
    if chapter["coverage"]["structuralPermissionsWithoutSourceSection"]:
        errors.append("structural permissions exist without source-section links")
    if chapter["coverage"]["structuralDefinitionsWithoutSourceSection"]:
        errors.append("structural definitions exist without source-section links")
    if chapter["coverage"]["machineClassifiedProvisionsWithoutSourceSection"]:
        errors.append("typed prose candidates exist without source-section links")
    if chapter["coverage"]["verifiedTextProvisionsWithoutSourceSection"]:
        errors.append("verified text provisions exist without source-section links")
    if chapter["coverage"]["formulasWithoutSourceSection"]:
        errors.append("formulas exist without source-section links")
    if chapter["coverage"]["computedRulesWithoutSourceSection"]:
        errors.append("computed rules exist without source-section links")
    ids = [
        item["id"] for kind in ("permissions", "dimensions", "definitions", "useAssignments")
        for item in candidates[kind]
    ]
    if len(ids) != len(set(ids)):
        errors.append("candidate IDs are not unique")
    if len(executable.get("sourceProvisions", [])) != source_blocks:
        errors.append("DSL source-provision count does not match source blocks")
    serialized_executable = json.dumps(executable)
    if ".docx" in serialized_executable:
        errors.append("reviewed executable provenance still references a DOCX export")

    report = {
        "sourceDocuments": len(source["documents"]),
        "sourceSchema": source["schemaVersion"],
        "canonicalSource": source.get("canonicalSource"),
        "municodeNodes": node_count,
        "sourceBlocks": source_blocks,
        "numberedSections": len(chapter["sections"]),
        "sectionStatus": chapter["coverage"]["sectionStatus"],
        "candidateCoverage": candidates["coverage"],
        "executableRules": len(executable["rules"]),
        "verifiedExecutableRules": sum(
            item["review_status"] == "verified" for item in executable["rules"]
        ),
        "sourceEncodedDslProvisions": len(executable.get("sourceProvisions", [])),
        "machineClassifiedTextProvisions": chapter["coverage"]["machineClassifiedProvisions"],
        "verifiedTextProvisions": chapter["coverage"]["verifiedTextProvisions"],
        "crossReferenceResolution": cross_references["coverage"]["resolution"],
        "missingInternalReferenceTargets": len(
            cross_references["coverage"]["missingInternalTargets"]
        ),
        "applicabilityScopes": applicability["coverage"],
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
