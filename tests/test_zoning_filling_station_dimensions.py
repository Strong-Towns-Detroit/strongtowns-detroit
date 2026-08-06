from pathlib import Path

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_filling_station_dimensions import (
    add_filling_station_general_standards,
    add_filling_station_lot_standards,
)
from strongtowns_detroit.zoning.json_engine import evaluate_package
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def package():
    builder = build_detroit_code()
    count = add_filling_station_lot_standards(
        builder, compile_source_corpus(ROOT / "resources")
    )
    return count, builder.compile()


def test_fixed_filling_station_cells_compile_to_width_and_area_rules():
    count, compiled = package()
    assert count == 4
    rules = [
        item for item in compiled["rules"]
        if item["id"].startswith("filling_station:")
    ]
    assert len(rules) == 2
    assert len(compiled["computedRules"]) == 2
    assert {item["source"]["sections"] for item in rules} == {
        ("50-13-174",), ("50-13-175",)
    }


def test_engine_selects_exact_pump_bay_and_building_size_cell():
    _, compiled = package()
    context = {
        "use": "motor_vehicle_filling_station",
        "pump_islands": 2,
        "service_bays": 1,
        "gross_floor_area": 600,
        "on_traditional_main_street": False,
        "includes_restaurant_service": False,
    }
    results = [
        item for item in evaluate_package(
            compiled, context, {"lot_width": 120, "lot_area": 13_000}
        )
        if item["ruleId"].startswith("filling_station:")
    ]
    assert len(results) == 2
    assert {item["status"] for item in results} == {"meets"}
    assert {item["requirement"]["value"] for item in results} == {120, 12_000}


def test_additive_formula_handles_extra_pump_islands_and_service_bays():
    _, compiled = package()
    context = {
        "use": "motor_vehicle_filling_station", "pump_islands": 7,
        "service_bays": 4, "gross_floor_area": 600,
        "on_traditional_main_street": False, "includes_restaurant_service": False,
    }
    result = next(item for item in evaluate_package(
        compiled, context, {"lot_width": 120, "lot_area": 25_999}
    ) if item["ruleId"] == "filling_station:up_to_600_sf:minimum_lot_area")
    assert result["requirement"]["value"] == 26_000
    assert result["status"] == "fails"


def test_section_176_source_conflict_is_not_silently_compiled():
    _, compiled = package()
    assert not any(
        "50-13-176" in item["source"]["sections"] for item in compiled["rules"]
    )


def test_direct_filling_station_cross_references_compile_by_element_type():
    builder = build_detroit_code()
    assert add_filling_station_general_standards(builder) == 10
    compiled = builder.compile()
    context = {
        "use": "motor_vehicle_filling_station",
        "element_type": "fuel_pump_or_pump_island",
        "on_traditional_main_street": False,
    }
    result = next(item for item in evaluate_package(
        compiled, context, {"property_line_setback": 19}
    ) if item["ruleId"] == "filling_station:fuel_pump_property_line_setback")
    assert result["status"] == "fails"


def test_traditional_main_street_station_building_goes_to_front_line():
    builder = build_detroit_code()
    add_filling_station_general_standards(builder)
    compiled = builder.compile()
    context = {
        "use": "motor_vehicle_filling_station",
        "element_type": "principal_building_or_structure",
        "on_traditional_main_street": True,
    }
    result = next(item for item in evaluate_package(
        compiled, context, {"front_setback": 1}
    ) if item["ruleId"] == "filling_station:tms_build_to_line")
    assert result["status"] == "fails"
