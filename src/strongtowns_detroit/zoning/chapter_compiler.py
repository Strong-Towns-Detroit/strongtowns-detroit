"""Compile every Chapter 50 source block into a traceable provision ledger.

This layer is comprehensive but deliberately conservative. It classifies the
source form of every numbered provision; only separately reviewed declarations
are described as executable law.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Iterable

from strongtowns_detroit.zoning.citations import extract_citations

HISTORY_RE = re.compile(r"^\(Code 1984,|^\(Ord\.", re.I)
HEADING_RE = re.compile(
    r"^Sec\.\s*(50-\d{1,2}-\d{1,4}(?:\.\d+)*)\.\s*(?:-\s*)?(.*)$", re.I
)


def classify_paragraph(text: str, article: int) -> list[str]:
    """Return broad, non-exclusive provision classes for a paragraph."""
    lower = text.lower()
    kinds: list[str] = []
    if HEADING_RE.match(text):
        return ["section_heading"]
    if HISTORY_RE.match(text):
        return ["legislative_history"]
    if "reserved" in lower and len(lower) < 80:
        kinds.append("reserved")
    if article == 16 and (" mean" in lower or "defined" in lower):
        kinds.append("definition")
    if article == 15 or "nonconform" in lower:
        kinds.append("nonconformity")
    if article == 5 or any(word in lower for word in ("violation", "penalty", "enforcement")):
        kinds.append("enforcement")
    if article == 17 or "zoning map" in lower:
        kinds.append("map")
    if any(word in lower for word in ("appeal", "application", "hearing", "notice", "petition")):
        kinds.append("procedure")
    if any(phrase in lower for phrase in ("shall not", "prohibited", "may not", "is unlawful")):
        kinds.append("prohibition")
    if any(phrase in lower for phrase in ("shall be", "shall comply", "is required", "must ")):
        kinds.append("requirement")
    if any(phrase in lower for phrase in ("except", "exception", "provided that", "unless")):
        kinds.append("exception")
    if any(word in lower for word in ("purpose", "intent", "objective")):
        kinds.append("purpose")
    if not kinds:
        kinds.append("operative_text" if len(text) > 40 else "source_text")
    return sorted(set(kinds))


def classify_table(article: int, section: str, rows: list[list[str]]) -> str:
    """Classify by ordinance context; no table becomes executable here."""
    if article == 12:
        return "use_permission_matrix"
    if article == 13:
        return "dimensional_or_intensity_table"
    if article == 17:
        return "map_or_district_table"
    if article == 16:
        return "definition_or_construction_table"
    if section.startswith("50-11-"):
        return "overlay_or_special_district_table"
    return "ordinance_table"


def _article(section: str) -> int:
    return int(section.split("-")[1])


def compile_chapter_package(source: dict, executable: dict) -> dict:
    """Compile a comprehensive source ledger joined to reviewed rules."""
    rules_by_section: dict[str, list[str]] = defaultdict(list)
    verified_rule_ids: set[str] = set()
    structural_rule_ids: set[str] = set()
    for rule in executable["rules"]:
        if rule["review_status"] == "verified":
            verified_rule_ids.add(rule["id"])
        else:
            structural_rule_ids.add(rule["id"])
        for section in rule["source"]["sections"]:
            rules_by_section[section].append(rule["id"])
    permissions_by_section: dict[str, list[str]] = defaultdict(list)
    verified_permission_ids: set[str] = set()
    structural_permission_ids: set[str] = set()
    for permission in executable.get("permissions", []):
        if permission["review_status"] == "verified":
            verified_permission_ids.add(permission["id"])
        else:
            structural_permission_ids.add(permission["id"])
        for section in permission["source"]["sections"]:
            permissions_by_section[section].append(permission["id"])
    definitions_by_section: dict[str, list[str]] = defaultdict(list)
    for definition in executable.get("definitions", []):
        for section in definition["source"]["sections"]:
            definitions_by_section[section].append(definition["id"])
    provisions_by_section: dict[str, list[str]] = defaultdict(list)
    verified_provision_ids: set[str] = set()
    machine_provision_ids: set[str] = set()
    for provision in executable.get("provisions", []):
        if provision["review_status"] == "verified":
            verified_provision_ids.add(provision["id"])
        else:
            machine_provision_ids.add(provision["id"])
        for section in provision["source"]["sections"]:
            provisions_by_section[section].append(provision["id"])
    formulas_by_section: dict[str, list[str]] = defaultdict(list)
    for formula in executable.get("formulas", []):
        for section in formula["source"]["sections"]:
            formulas_by_section[section].append(formula["id"])
    computed_rules_by_section: dict[str, list[str]] = defaultdict(list)
    for rule in executable.get("computedRules", []):
        for section in rule["source"]["sections"]:
            computed_rules_by_section[section].append(rule["id"])

    grouped: dict[str, dict] = {}
    unsectioned: list[dict] = []
    provision_counts: Counter[str] = Counter()
    source_block_count = 0

    for document in source["documents"]:
        for block in document["blocks"]:
            source_block_count += 1
            section = block.get("section")
            block_id = f"{document['document']}:{block['sourceIndex']}"
            if not section:
                unsectioned.append({"id": block_id, "document": document["document"], **block})
                continue
            article = _article(section)
            entry = grouped.setdefault(section, {
                "section": section,
                "article": article,
                "document": document["document"],
                "title": "",
                "provisions": [],
                "citations": [],
                "review": {
                    "status": "source_encoded",
                    "executableRuleIds": [],
                    "permissionIds": [],
                    "definitionIds": [],
                    "provisionCandidateIds": [],
                    "formulaIds": [],
                    "computedRuleIds": [],
                    "note": "Source is encoded; legal normalization and review remain pending.",
                },
            })
            if block["type"] == "paragraph":
                heading = HEADING_RE.match(block["text"])
                if heading:
                    entry["title"] = heading.group(2).strip()
                kinds = classify_paragraph(block["text"], article)
                citations = [
                    {**asdict(item), "citation_type": item.citation_type.value}
                    for item in extract_citations(block["text"], section)
                ]
                provision = {
                    "id": block_id,
                    "sourceIndex": block["sourceIndex"],
                    "kind": "paragraph",
                    "classes": kinds,
                    "text": block["text"],
                    "citations": citations,
                }
                entry["citations"].extend(citations)
                provision_counts.update(kinds)
            else:
                table_class = classify_table(article, section, block["rows"])
                provision = {
                    "id": block_id,
                    "sourceIndex": block["sourceIndex"],
                    "kind": "table",
                    "classes": [table_class],
                    "rows": block["rows"],
                }
                provision_counts[table_class] += 1
            entry["provisions"].append(provision)

    for section, entry in grouped.items():
        rule_ids = sorted(set(rules_by_section.get(section, [])))
        permission_ids = sorted(set(permissions_by_section.get(section, [])))
        definition_ids = sorted(set(definitions_by_section.get(section, [])))
        provision_ids = sorted(set(provisions_by_section.get(section, [])))
        formula_ids = sorted(set(formulas_by_section.get(section, [])))
        computed_rule_ids = sorted(set(computed_rules_by_section.get(section, [])))
        if (
            rule_ids or permission_ids or definition_ids or provision_ids
            or formula_ids or computed_rule_ids
        ):
            entry["review"] = {
                "status": (
                    "partially_reviewed_executable"
                    if (
                        any(rule_id in verified_rule_ids for rule_id in rule_ids)
                        or any(item_id in verified_permission_ids for item_id in permission_ids)
                        or any(item_id in verified_provision_ids for item_id in provision_ids)
                    )
                    else "structurally_verified_tables"
                    if (
                        rule_ids or permission_ids or definition_ids
                        or formula_ids or computed_rule_ids
                    )
                    else "source_encoded"
                ),
                "executableRuleIds": rule_ids,
                "permissionIds": permission_ids,
                    "definitionIds": definition_ids,
                    "provisionCandidateIds": provision_ids,
                    "formulaIds": formula_ids,
                    "computedRuleIds": computed_rule_ids,
                "note": (
                    "Named artifacts are linked; this does not certify the entire section "
                    "or resolve use-specific conditions."
                ),
            }

    represented_rules = {
        rule_id
        for entry in grouped.values()
        for rule_id in entry["review"]["executableRuleIds"]
    }
    all_rules = {rule["id"] for rule in executable["rules"]}
    represented_permissions = {
        permission_id
        for entry in grouped.values()
        for permission_id in entry["review"].get("permissionIds", [])
    }
    all_permissions = {item["id"] for item in executable.get("permissions", [])}
    represented_definitions = {
        definition_id
        for entry in grouped.values()
        for definition_id in entry["review"].get("definitionIds", [])
    }
    all_definitions = {item["id"] for item in executable.get("definitions", [])}
    represented_provisions = {
        provision_id
        for entry in grouped.values()
        for provision_id in entry["review"].get("provisionCandidateIds", [])
    }
    all_provisions = {item["id"] for item in executable.get("provisions", [])}
    represented_formulas = {
        item_id for entry in grouped.values()
        for item_id in entry["review"].get("formulaIds", [])
    }
    all_formulas = {item["id"] for item in executable.get("formulas", [])}
    represented_computed_rules = {
        item_id for entry in grouped.values()
        for item_id in entry["review"].get("computedRuleIds", [])
    }
    all_computed_rules = {
        item["id"] for item in executable.get("computedRules", [])
    }
    return {
        "schemaVersion": "chapter-50-package-v1",
        "municipality": "Detroit",
        "sourceSchema": source["schemaVersion"],
        "executableSchema": executable["schemaVersion"],
        "sections": [grouped[key] for key in sorted(grouped, key=_section_key)],
        "unsectionedBlocks": unsectioned,
        "coverage": {
            "sourceDocuments": len(source["documents"]),
            "sourceBlocks": source_block_count,
            "numberedSections": len(grouped),
            "unsectionedBlocks": len(unsectioned),
            "executableRules": len(all_rules),
            "verifiedExecutableRules": len(verified_rule_ids),
            "structuralDimensionRules": len(structural_rule_ids),
            "reviewedRulesLinkedToSections": len(represented_rules),
            "reviewedRulesWithoutSourceSection": sorted(all_rules - represented_rules),
            "permissions": len(all_permissions),
            "verifiedPermissions": len(verified_permission_ids),
            "structuralPermissions": len(structural_permission_ids),
            "structuralPermissionsLinkedToSections": len(represented_permissions),
            "structuralPermissionsWithoutSourceSection": sorted(
                all_permissions - represented_permissions
            ),
            "structuralDefinitions": len(all_definitions),
            "structuralDefinitionsLinkedToSections": len(represented_definitions),
            "structuralDefinitionsWithoutSourceSection": sorted(
                all_definitions - represented_definitions
            ),
            "structuralUseAssignments": len(executable.get("useAssignments", [])),
            "verifiedTextProvisions": len(verified_provision_ids),
            "verifiedTextProvisionsLinkedToSections": len(
                verified_provision_ids & represented_provisions
            ),
            "verifiedTextProvisionsWithoutSourceSection": sorted(
                verified_provision_ids - represented_provisions
            ),
            "machineClassifiedProvisions": len(machine_provision_ids),
            "machineClassifiedProvisionsLinkedToSections": len(
                machine_provision_ids & represented_provisions
            ),
            "machineClassifiedProvisionsWithoutSourceSection": sorted(
                machine_provision_ids - represented_provisions
            ),
            "formulas": len(all_formulas),
            "formulasWithoutSourceSection": sorted(all_formulas - represented_formulas),
            "computedRules": len(all_computed_rules),
            "computedRulesWithoutSourceSection": sorted(
                all_computed_rules - represented_computed_rules
            ),
            "sectionStatus": dict(sorted(Counter(
                entry["review"]["status"] for entry in grouped.values()
            ).items())),
            "provisionClasses": dict(sorted(provision_counts.items())),
        },
    }


def _section_key(section: str) -> tuple[int, ...]:
    chapter, article, provision = section.split("-")
    return (int(chapter), int(article), *(int(piece) for piece in provision.split(".")))
