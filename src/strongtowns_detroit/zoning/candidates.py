"""Provenance-preserving machine candidates for later legal review."""

from __future__ import annotations

from collections import Counter
import re

from strongtowns_detroit.zoning.definitions import parse_definition_table
from strongtowns_detroit.zoning.dimensional import parse_dimensional_table
from strongtowns_detroit.zoning.use_tables import parse_use_table
from strongtowns_detroit.zoning.table_parser import _DISTRICT_PATTERN
from strongtowns_detroit.zoning.citations import extract_citations

DELEGATED_ANTENNA_STANDARD = "Division 3, Subdivision G, of this article"
FULLY_PROMOTED_COMPOSITES = {
    **{
        ("Brewpub or micro- brewery or small distillery or small winery", district): "50-12-217"
        for district in ("M1", "M2", "M3", "M4", "SD1")
    },
    **{("Loft", district): "50-12-159" for district in ("B2", "B3", "B4")},
    **{
        ("Residential use combined in structures with permitted commercial uses", district): "50-12-159"
        for district in ("B2", "B3", "B4")
    },
    ("Office, business or professional", "MKT"): "50-12-298",
    **{("Parking structures", district): "50-12-301" for district in ("B5", "PC", "PCA")},
    ("Rental hall", "SD1"): "50-12-309",
    ("Theater and concert café, excluding drive-in theaters", "SD2"): "50-12-317",
    ("Storage or killing of poultry or small game for direct, retail sale on the premises or for wholesale trade", "MKT"): "50-12-315",
    ("Wholesaling, warehousing, storage buildings, or public storage facilities", "MKT"): "50-12-358",
    ("Parking lots or parking areas", "B4"): "50-12-299",
    ("Restaurant, carry-out, with drive-up or drive-through facilities", "B5"): "50-12-310",
    ("Restaurant, carry-out, without drive-up or drive-through facilities", "B5"): "50-12-310",
    ("Restaurant, carry-out, without drive-up or drive-through facilities", "PCA"): "50-12-310",
    ("Restaurant, fast food, with drive-up or drive-through facilities", "B5"): "50-12-310",
    ("Restaurant, fast food, without drive-up or drive-through facilities", "B5"): "50-12-310",
    ("Restaurant, fast food, without drive-up or drive-through facilities", "PCA"): "50-12-310",
    ("Confection manufacture", "B2"): "50-12-334",
    ("Confection manufacture", "B4"): "50-12-334",
    ("Food catering establishment", "B2"): "50-12-336",
    ("Food catering establishment", "B4"): "50-12-336",
    ("Jewelry manufacture", "B4"): "50-12-340",
    ("Lithographing, and sign shops", "B4"): "50-12-342",
    ("Wearing apparel manufacturing", "B4"): "50-12-360",
    ("Establishment for the sale of beer or alcoholic liquor for consumption on the premises", "SD1"): "50-12-220",
}
PARTIALLY_PROMOTED_COMPOSITES = {
    ("Printing or engraving shop", "SD2"): "50-12-323",
    **{("Trade services, general", district): "50-12-353" for district in ("B2", "SD1", "SD2")},
    ("Lithographing, and sign shops", "B2"): "50-12-342",
    ("Barber or beauty shop", "MKT"): "50-12-235",
}
VALID_PERMISSION_CODES = {
    "—", "R", "C", "L", "C/R", "R/C", "*", DELEGATED_ANTENNA_STANDARD,
}
UNAMBIGUOUS_PERMISSIONS = {
    "—": {"status": "not_allowed", "authority": None},
    "R": {"status": "allowed_by_right", "authority": None},
    "C": {"status": "conditional_use", "authority": "conditional_use_permit"},
    "L": {"status": "legislative_approval", "authority": "legislative_body"},
}
DIMENSION_METRICS = {
    "Minimum Lot Dimensions - Area (sq. ft.)": ("lot_area", ">=", "square_feet"),
    "Minimum Lot Dimensions - Width (feet)": ("lot_width", ">=", "feet"),
    "Minimum Setbacks (feet) - Front": ("front_setback", ">=", "feet"),
    "Minimum Setbacks (feet) - Side*": ("side_setback", ">=", "feet"),
    "Minimum Setbacks (feet) - Rear": ("rear_setback", ">=", "feet"),
    "Max. Height (feet)": ("height", "<=", "feet"),
    "Max. Lot Coverage (%)": ("lot_coverage", "<=", "percent"),
    "Max FAR": ("floor_area_ratio", "<=", "ratio"),
}
LEADING_NUMBER_RE = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\b")


def compile_candidates(source: dict) -> dict:
    permissions: list[dict] = []
    dimensions: list[dict] = []
    definitions: list[dict] = []
    use_assignments: list[dict] = []
    rejected: list[dict] = []

    for document in source["documents"]:
        for block in document["blocks"]:
            if block["type"] != "table":
                continue
            section = block.get("section") or ""
            provenance = {
                "document": document["document"],
                "section": section or None,
                "sourceIndex": block["sourceIndex"],
            }
            article = _article(section)
            if article == 12 and _has_district_header(block["rows"]):
                standards_by_use = _standards_by_use(block["rows"])
                for offset, item in enumerate(parse_use_table(block["rows"], section)):
                    standards_raw = standards_by_use.get(item.use_name, "")
                    normalization = UNAMBIGUOUS_PERMISSIONS.get(item.permission)
                    if item.permission == "*" and "accessory use only" in standards_raw.casefold():
                        normalization = {"status": "accessory_only", "authority": "50-12-521"}
                    if (
                        item.permission in {"C/R", "R/C"}
                        and item.use_name == "Multiple-family dwelling"
                        and item.district in {"R3", "B5", "PCA"}
                    ):
                        normalization = {
                            "status": "branched_permission",
                            "authority": "50-12-162",
                        }
                    key = (item.use_name, item.district)
                    if key in FULLY_PROMOTED_COMPOSITES:
                        normalization = {
                            "status": "branched_permission",
                            "authority": FULLY_PROMOTED_COMPOSITES[key],
                        }
                    elif key in PARTIALLY_PROMOTED_COMPOSITES:
                        normalization = {
                            "status": "partially_branched_permission",
                            "authority": PARTIALLY_PROMOTED_COMPOSITES[key],
                        }
                    if item.permission == DELEGATED_ANTENNA_STANDARD:
                        normalization = {
                            "status": "partially_branched_delegated_rule",
                            "authority": "50-12-367--50-12-398",
                        }
                    row = {
                        "id": _id(provenance, "permission", offset),
                        "useName": item.use_name,
                        "district": item.district,
                        "permission": item.permission,
                        "conditionsRaw": item.conditions,
                        "standardsRaw": standards_raw,
                        "conditionTargets": sorted({
                            citation.target
                            for citation in extract_citations(standards_raw, section)
                        }),
                        "source": provenance,
                        "reviewStatus": "machine_candidate",
                        "normalization": normalization,
                        "reviewReadiness": (
                            "promoted_to_reviewed_rules"
                            if normalization and normalization["status"] == "branched_permission"
                            else "partially_promoted_to_reviewed_rules"
                            if normalization and normalization["status"] == "partially_branched_permission"
                            else "delegated_rule_review_required"
                            if normalization and normalization["status"] == "partially_branched_delegated_rule"
                            else "ready_for_cell_review" if normalization
                            else "needs_legal_interpretation"
                        ),
                    }
                    if item.permission in VALID_PERMISSION_CODES:
                        permissions.append(row)
                    else:
                        rejected.append({
                            **row,
                            "candidateType": "permission",
                            "rejectionReason": "unrecognized_permission_code",
                        })
            elif article == 13:
                for offset, item in enumerate(parse_dimensional_table(block["rows"], section)):
                    normalization = _normalize_dimension(item.standard_name, item.value)
                    interpretation = (
                        None if normalization
                        else _classify_dimension_text(item.standard_name, item.value, section)
                    )
                    review_readiness = "ready_for_cell_review" if normalization else (
                        "promoted_to_reviewed_rules"
                        if (
                            interpretation and interpretation["type"] == "named_formula"
                        ) or (
                            interpretation and interpretation["type"] == "ratio_formula"
                        ) or (
                            interpretation and interpretation["type"] == "compound_standard"
                            and item.standard_name == "Minimum Setbacks (feet) - Side*"
                        ) or (
                            section in {"50-13-174", "50-13-175"}
                            and interpretation
                            and interpretation["type"] in {"compound_standard", "unparsed_text"}
                        ) or _promoted_cross_reference(item.standard_name, interpretation)
                        else "linked_additional_regulations"
                        if (
                            interpretation and interpretation["type"] == "cross_reference"
                            and item.standard_name == "Add'l. Regs."
                        )
                        else "reviewed_no_numeric_rule"
                        if interpretation and interpretation["type"] == "no_minimum"
                        else "source_conflict_requires_resolution"
                        if section == "50-13-176"
                        else "needs_legal_interpretation"
                    )
                    dimensions.append({
                        "id": _id(provenance, "dimension", offset),
                        "scenarioRaw": item.district,
                        "standardRaw": item.standard_name,
                        "valueRaw": item.value,
                        "source": provenance,
                        "reviewStatus": "machine_candidate",
                        "normalization": normalization,
                        "interpretation": interpretation,
                        "reviewReadiness": review_readiness,
                    })
            elif document["document"].startswith("APPENDIX_A"):
                for offset, item in enumerate(parse_definition_table(block["rows"], section)):
                    if (
                        item.term.strip().casefold() == "specific land use"
                        or not item.term.strip() or not item.definition.strip()
                    ):
                        continue
                    use_assignments.append({
                        "id": _id(provenance, "use-assignment", offset),
                        "specificUse": item.term,
                        "useCategory": item.definition,
                        "source": provenance,
                        "reviewStatus": "machine_candidate",
                        "reviewReadiness": "ready_for_cell_review",
                    })
            elif article == 16:
                for offset, item in enumerate(parse_definition_table(block["rows"], section)):
                    if not item.definition.strip():
                        continue
                    definitions.append({
                        "id": _id(provenance, "definition", offset),
                        "term": item.term,
                        "meaning": item.definition,
                        "source": provenance,
                        "reviewStatus": "machine_candidate",
                        "reviewReadiness": "ready_for_cell_review",
                    })

    return {
        "schemaVersion": "zoning-candidates-v1",
        "warning": "Candidates are not executable law until normalized and reviewed.",
        "permissions": permissions,
        "dimensions": dimensions,
        "definitions": definitions,
        "useAssignments": use_assignments,
        "rejected": rejected,
        "coverage": {
            "permissions": len(permissions),
            "dimensions": len(dimensions),
            "definitions": len(definitions),
            "useAssignments": len(use_assignments),
            "rejected": len(rejected),
            "rejectionReasons": dict(sorted(Counter(
                item["rejectionReason"] for item in rejected
            ).items())),
            "permissionReviewReadiness": dict(sorted(Counter(
                item["reviewReadiness"] for item in permissions
            ).items())),
            "dimensionReviewReadiness": dict(sorted(Counter(
                item["reviewReadiness"] for item in dimensions
            ).items())),
            "dimensionInterpretationTypes": dict(sorted(Counter(
                item["interpretation"]["type"]
                for item in dimensions if item["interpretation"]
            ).items())),
            "definitionReviewReadiness": dict(sorted(Counter(
                item["reviewReadiness"] for item in definitions
            ).items())),
        },
    }


def _article(section: str) -> int | None:
    return int(section.split("-")[1]) if section else None


def _has_district_header(rows: list[list[str]]) -> bool:
    """Reject spacing/lookup tables that the legacy fallback treated as matrices."""
    return any(
        sum(bool(_DISTRICT_PATTERN.fullmatch(cell.strip())) for cell in row) >= 3
        for row in rows[:3]
    )


def _standards_by_use(rows: list[list[str]]) -> dict[str, str]:
    district_row = max(
        rows[:3],
        key=lambda row: sum(bool(_DISTRICT_PATTERN.fullmatch(cell.strip())) for cell in row),
    )
    district_columns = [
        index for index, cell in enumerate(district_row)
        if _DISTRICT_PATTERN.fullmatch(cell.strip())
    ]
    if not district_columns:
        return {}
    last_district = max(district_columns)
    result: dict[str, str] = {}
    for row in rows:
        if len(row) < 2 or not row[1].strip():
            continue
        standards = next(
            (cell.strip() for cell in row[last_district + 1:] if cell.strip()), ""
        )
        result[row[1].strip()] = standards
    return result


def _id(source: dict, kind: str, offset: int) -> str:
    return f"{source['document']}:{source['sourceIndex']}:{kind}:{offset}"


def _normalize_dimension(standard: str, raw_value: str) -> dict | None:
    spec = DIMENSION_METRICS.get(standard)
    match = LEADING_NUMBER_RE.match(raw_value)
    if not spec or not match:
        return None
    # Compound values such as "4 ft. minimum / 14 ft. combined" require more
    # than one rule and must not be collapsed to the first number.
    lower = raw_value.lower()
    if "/" in raw_value or "formula" in lower or " per " in lower:
        return None
    number = float(match.group(1).replace(",", ""))
    metric, operator, unit = spec
    return {
        "metric": metric,
        "operator": operator,
        "value": int(number) if number.is_integer() else number,
        "unit": unit,
        "sourceValue": raw_value,
    }


def _classify_dimension_text(standard: str, raw_value: str, section: str) -> dict:
    lower = raw_value.strip().casefold()
    citations = sorted({item.target for item in extract_citations(raw_value, section)})
    if standard == "Add'l. Regs." or citations or lower.startswith(("see section", "article ", "division ")):
        return {"type": "cross_reference", "targets": citations, "sourceValue": raw_value}
    if lower in {"formula a", "formula b"}:
        return {
            "type": "named_formula",
            "formula": lower.replace(" ", "_"),
            "sourceValue": raw_value,
            "reviewNote": "Flattened DOCX text does not establish mathematical precedence.",
        }
    if "no minimum requirement" in lower or "no minimum requirements" in lower:
        return {"type": "no_minimum", "sourceValue": raw_value}
    if lower in {"-", "—"}:
        return {"type": "not_applicable_or_unspecified", "sourceValue": raw_value}
    if "rsr" in lower:
        ratio = re.search(r"([\d.]+)\s*rsr", lower)
        return {
            "type": "ratio_formula", "symbol": "RSR",
            "metric": "recreational_space_area",
            "ratio": float(ratio.group(1)) if ratio else None,
            "sourceValue": raw_value,
        }
    if "/" in raw_value and re.search(r"\d", raw_value):
        return {"type": "compound_standard", "sourceValue": raw_value}
    if any(word in lower for word in ("service bay", "lot width/lot area", "limitation")):
        return {"type": "table_structure", "sourceValue": raw_value}
    return {"type": "unparsed_text", "sourceValue": raw_value}


def _promoted_cross_reference(standard: str, interpretation: dict | None) -> bool:
    if not interpretation or interpretation["type"] != "cross_reference":
        return False
    targets = set(interpretation.get("targets", ()))
    if targets in ({"50-11-245"}, {"50-11-275"}):
        return standard in {
            "Minimum Setbacks (feet) - Front",
            "Minimum Setbacks (feet) - Side*",
            "Minimum Setbacks (feet) - Rear",
            "Max. Height (feet)",
        }
    if targets == {"50-13-177"}:
        return standard == "Max. Lot Coverage (%)"
    if targets == {"50-13-178", "50-13-179"}:
        return standard in {
            "Minimum Setbacks (feet) - Front",
            "Minimum Setbacks (feet) - Side*",
            "Minimum Setbacks (feet) - Rear",
        }
    return False
