import pytest
from pathlib import Path

from strongtowns_detroit.zoning.dimensional import parse_dimensional_table
from strongtowns_detroit.zoning.rules import (
    BuildingScenario,
    EvaluationStatus,
    REVIEWED_RESIDENTIAL_RULES,
    RuleMetric,
    evaluate_minimum,
    rule_for,
)
from strongtowns_detroit.zoning.table_parser import extract_tables_xml


def test_single_family_rules_match_all_six_reviewed_tables():
    for district in ("R1", "R2", "R3", "R4", "R5", "R6"):
        area = rule_for(
            district,
            BuildingScenario.ONE_FAMILY_PRINCIPAL,
            RuleMetric.MINIMUM_LOT_AREA,
        )
        width = rule_for(
            district,
            BuildingScenario.ONE_FAMILY_PRINCIPAL,
            RuleMetric.MINIMUM_LOT_WIDTH,
        )
        assert area is not None and area.value == 5_000
        assert width is not None and width.value == 50
        assert f"50-13-{int(district[1]) + 1}" in area.source_refs


def test_two_family_rules_preserve_area_and_r3_width_difference():
    for district in ("R2", "R3", "R4", "R5", "R6"):
        area = rule_for(
            district,
            BuildingScenario.TWO_FAMILY_PRINCIPAL,
            RuleMetric.MINIMUM_LOT_AREA,
        )
        width = rule_for(
            district,
            BuildingScenario.TWO_FAMILY_PRINCIPAL,
            RuleMetric.MINIMUM_LOT_WIDTH,
        )
        assert area is not None and area.value == 6_000
        assert width is not None
        assert width.value == (60 if district == "R3" else 55)


def test_r1_two_family_is_not_silently_given_a_dimensional_rule():
    rule = rule_for(
        "R1",
        BuildingScenario.TWO_FAMILY_PRINCIPAL,
        RuleMetric.MINIMUM_LOT_AREA,
    )
    result = evaluate_minimum(rule, 7_000)
    assert rule is None
    assert result.status == EvaluationStatus.NOT_APPLICABLE


def test_setback_rules_are_scenario_specific_and_cited():
    side = rule_for(
        "R4",
        BuildingScenario.TWO_FAMILY_PRINCIPAL,
        RuleMetric.MINIMUM_COMBINED_SIDE_SETBACK,
    )
    assert side is not None
    assert side.value == 14
    assert side.source_value == "4 ft. minimum/ 14 ft. combined"
    assert side.source_refs == ("50-13-5", "50-16-382")


def test_unknown_measurement_remains_unknown():
    rule = rule_for(
        "R2",
        BuildingScenario.ONE_FAMILY_PRINCIPAL,
        RuleMetric.MINIMUM_LOT_AREA,
    )
    result = evaluate_minimum(rule, None)
    assert result.status == EvaluationStatus.UNKNOWN
    assert result.missing_inputs == ("minimum_lot_area",)


def test_legal_boundary_and_measurement_tolerance_are_separate():
    rule = rule_for(
        "R2",
        BuildingScenario.ONE_FAMILY_PRINCIPAL,
        RuleMetric.MINIMUM_LOT_AREA,
    )
    assert rule is not None and rule.value == 5_000
    assert evaluate_minimum(rule, 4_960, measurement_tolerance=50).status == (
        EvaluationStatus.MEETS
    )
    assert evaluate_minimum(rule, 4_949, measurement_tolerance=50).status == (
        EvaluationStatus.FAILS
    )


def test_reviewed_rule_ids_are_unique():
    ids = [rule.rule_id for rule in REVIEWED_RESIDENTIAL_RULES]
    assert len(ids) == len(set(ids))


def test_reviewed_area_and_width_rules_match_repository_ordinance_source():
    """SOURCE-DRIFT GATE: normalized values must match all six source tables."""
    source = Path(
        "resources/ARTICLE_XIII.___INTENSITY_AND_DIMENSIONAL_STANDARDS.docx"
    )
    tables = extract_tables_xml(source)[:6]
    assert len(tables) == 6
    for index, table in enumerate(tables, start=1):
        district = f"R{index}"
        records = parse_dimensional_table(table, f"50-13-{index + 1}")
        values = {
            (record.district, record.standard_name): record.value
            for record in records
        }
        single = "Single-family dwellings, religious residential facilities"
        assert values[(single, "Minimum Lot Dimensions - Area (sq. ft.)")] == (
            f"{rule_for(district, BuildingScenario.ONE_FAMILY_PRINCIPAL, RuleMetric.MINIMUM_LOT_AREA).value:,.0f}"
        )
        assert values[(single, "Minimum Lot Dimensions - Width (feet)")] == (
            f"{rule_for(district, BuildingScenario.ONE_FAMILY_PRINCIPAL, RuleMetric.MINIMUM_LOT_WIDTH).value:g}"
        )
        if district == "R1":
            assert not any(record.district == "Two-family dwellings" for record in records)
            continue
        assert values[("Two-family dwellings", "Minimum Lot Dimensions - Area (sq. ft.)")] == (
            f"{rule_for(district, BuildingScenario.TWO_FAMILY_PRINCIPAL, RuleMetric.MINIMUM_LOT_AREA).value:,.0f}"
        )
        assert values[("Two-family dwellings", "Minimum Lot Dimensions - Width (feet)")] == (
            f"{rule_for(district, BuildingScenario.TWO_FAMILY_PRINCIPAL, RuleMetric.MINIMUM_LOT_WIDTH).value:g}"
        )
