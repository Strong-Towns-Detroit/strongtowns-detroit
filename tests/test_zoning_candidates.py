from pathlib import Path

from strongtowns_detroit.zoning.candidates import (
    DELEGATED_ANTENNA_STANDARD,
    UNAMBIGUOUS_PERMISSIONS,
    VALID_PERMISSION_CODES,
    compile_candidates,
)
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def candidates():
    return compile_candidates(compile_source_corpus(ROOT / "resources"))


def test_every_candidate_has_exact_source_provenance():
    package = candidates()
    for kind in ("permissions", "dimensions", "definitions", "useAssignments", "rejected"):
        for item in package[kind]:
            assert item["source"]["document"].endswith(".docx")
            assert isinstance(item["source"]["sourceIndex"], int)


def test_invalid_permission_cells_are_quarantined():
    package = candidates()
    assert all(item["permission"] in VALID_PERMISSION_CODES for item in package["permissions"])
    assert all(
        item["permission"] not in VALID_PERMISSION_CODES
        for item in package["rejected"]
        if item["candidateType"] == "permission"
    )
    assert not any(item["source"]["section"] == "50-12-129" for item in package["rejected"])
    antenna = [
        item for item in package["permissions"]
        if item["permission"] == DELEGATED_ANTENNA_STANDARD
    ]
    assert len(antenna) == 29
    assert {item["reviewReadiness"] for item in antenna} == {
        "delegated_rule_review_required"
    }


def test_context_keeps_historic_boundaries_out_of_dimensions():
    package = candidates()
    assert not any(
        item["standardRaw"] == "General Boundaries"
        for item in package["dimensions"]
    )


def test_only_codes_defined_by_source_are_normalized_automatically():
    package = candidates()
    for item in package["permissions"]:
        if item["permission"] in UNAMBIGUOUS_PERMISSIONS or (
            item["permission"] == "*" and "accessory use only" in item["standardsRaw"].casefold()
        ):
            assert item["normalization"]
            assert item["reviewReadiness"] == "ready_for_cell_review"
        elif item["permission"] == DELEGATED_ANTENNA_STANDARD:
            assert item["normalization"]["status"] == "partially_branched_delegated_rule"
            assert item["reviewReadiness"] == "delegated_rule_review_required"
        elif item["normalization"] and item["normalization"]["status"] == "branched_permission":
            assert item["normalization"]["status"] == "branched_permission"
            assert item["reviewReadiness"] == "promoted_to_reviewed_rules"
        elif item["normalization"] and item["normalization"]["status"] == "partially_branched_permission":
            assert item["reviewReadiness"] == "partially_promoted_to_reviewed_rules"
        else:
            assert item["normalization"] is None
            assert item["reviewReadiness"] == "needs_legal_interpretation"


def test_r1_merged_table_columns_keep_rear_height_and_coverage_distinct():
    package = candidates()
    rows = [
        item for item in package["dimensions"]
        if item["source"]["section"] == "50-13-2"
        and item["scenarioRaw"] == "Single-family dwellings, religious residential facilities"
    ]
    values = {item["standardRaw"]: item["valueRaw"] for item in rows}
    assert values["Minimum Setbacks (feet) - Rear"] == "30"
    assert values["Max. Height (feet)"] == "35"
    assert values["Max. Lot Coverage (%)"].startswith("35 including")


def test_simple_dimensions_normalize_but_compound_side_yards_do_not():
    package = candidates()
    rows = [
        item for item in package["dimensions"]
        if item["source"]["section"] == "50-13-2"
        and item["scenarioRaw"] == "Single-family dwellings, religious residential facilities"
    ]
    values = {item["standardRaw"]: item for item in rows}
    assert values["Minimum Lot Dimensions - Area (sq. ft.)"]["normalization"]["value"] == 5000
    assert values["Max. Height (feet)"]["normalization"]["operator"] == "<="
    assert values["Minimum Setbacks (feet) - Side*"]["normalization"] is None


def test_appendix_assignments_are_not_mislabeled_as_definitions():
    package = candidates()
    assert package["useAssignments"]
    assert all(
        item["source"]["document"].startswith("APPENDIX_A")
        for item in package["useAssignments"]
    )
    assert not any(
        item["source"]["document"].startswith("APPENDIX_A")
        for item in package["definitions"]
    )


def test_non_numeric_dimension_cells_are_typed_not_flattened():
    package = candidates()
    unresolved = [item for item in package["dimensions"] if not item["normalization"]]
    assert all(item["interpretation"] for item in unresolved)
    types = package["coverage"]["dimensionInterpretationTypes"]
    assert types["cross_reference"] > 300
    assert types["named_formula"] == 80
    formula = next(
        item for item in unresolved
        if item["interpretation"]["type"] == "named_formula"
    )
    assert formula["interpretation"]["reviewNote"]


def test_use_permissions_retain_final_column_dependencies():
    package = candidates()
    multiple = next(
        item for item in package["permissions"]
        if item["useName"] == "Multiple-family dwelling"
        and item["district"] == "R3"
    )
    assert multiple["permission"] == "C/R"
    assert "50-12-162" in multiple["conditionTargets"]
    assert multiple["reviewReadiness"] == "promoted_to_reviewed_rules"
    farmers = next(
        item for item in package["permissions"]
        if item["useName"] == "Farmers' market" and item["district"] == "R1"
    )
    assert farmers["normalization"]["status"] == "accessory_only"
    assert "50-12-521" in farmers["conditionTargets"]


def test_filling_station_tables_preserve_service_bay_column_context():
    package = candidates()
    rows = [
        item for item in package["dimensions"]
        if item["source"]["section"] == "50-13-174"
        and item["scenarioRaw"] == "2 pump islands"
    ]
    assert {
        item["standardRaw"] for item in rows
    } == {
        "Lot Width/Lot Area - 0—2 Service Bays",
        "Lot Width/Lot Area - 3 Service Bays",
        "Each Additional Service Bay",
    }
    values = {item["standardRaw"]: item["valueRaw"] for item in rows}
    assert values["Lot Width/Lot Area - 0—2 Service Bays"] == (
        "120 feet/12,000 square feet"
    )
    assert values["Lot Width/Lot Area - 3 Service Bays"] == (
        "120 feet/14,000 square feet"
    )
    assert {item["reviewReadiness"] for item in rows[:2]} == {
        "promoted_to_reviewed_rules"
    }
    conflicted = [
        item for item in package["dimensions"]
        if item["source"]["section"] == "50-13-176"
    ]
    assert conflicted
    assert {item["reviewReadiness"] for item in conflicted} == {
        "source_conflict_requires_resolution"
    }


def test_repeated_merged_use_labels_do_not_become_dimension_values():
    package = candidates()
    assert not any(
        item["scenarioRaw"].casefold() == item["valueRaw"].casefold()
        for item in package["dimensions"]
    )


def test_additional_regulation_links_are_not_numeric_parse_failures():
    package = candidates()
    linked = [
        item for item in package["dimensions"]
        if item["standardRaw"] == "Add'l. Regs."
        and item.get("interpretation", {}).get("type") == "cross_reference"
    ]
    assert linked
    assert {item["reviewReadiness"] for item in linked} == {
        "linked_additional_regulations"
    }


def test_blank_figure_continuation_is_not_a_definition_candidate():
    package = candidates()
    assert len(package["definitions"]) == 467
    assert all(item["meaning"].strip() for item in package["definitions"])
