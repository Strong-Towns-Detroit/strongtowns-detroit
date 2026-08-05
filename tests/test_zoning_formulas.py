from pathlib import Path

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_formulas import add_side_setback_formulas
from strongtowns_detroit.zoning.json_engine import evaluate_package
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def formula_package():
    source = compile_source_corpus(ROOT / "resources")
    builder = build_detroit_code()
    count = add_side_setback_formulas(builder, source)
    return count, builder.compile()


def test_formula_definitions_follow_section_50_13_229():
    count, package = formula_package()
    assert count == 80
    assert {item["id"] for item in package["formulas"]} == {"formula_a", "formula_b"}
    formula_b = next(item for item in package["formulas"] if item["id"] == "formula_b")
    assert formula_b["minimum"] == 5
    assert formula_b["source"]["sections"] == ("50-13-229",)


def test_json_engine_evaluates_formula_b_and_its_floor():
    _, package = formula_package()
    target = next(
        item for item in package["computedRules"] if item["formula"] == "formula_b"
    )
    context = {
        predicate["field"]: predicate["value"]
        for predicate in target["when"]["all"]
    }
    result = next(
        item for item in evaluate_package(package, context, {
            "building_length_along_adjacent_lot_line": 60,
            "building_height": 30,
            "side_setback": 19,
        }) if item["ruleId"] == target["id"]
    )
    assert result["requirement"]["value"] == 20
    assert result["status"] == "fails"

    floor_result = next(
        item for item in evaluate_package(package, context, {
            "building_length_along_adjacent_lot_line": 10,
            "building_height": 5,
            "side_setback": 5,
        }) if item["ruleId"] == target["id"]
    )
    assert floor_result["requirement"]["value"] == 5
    assert floor_result["status"] == "meets"


def test_missing_formula_inputs_preserve_unknown():
    _, package = formula_package()
    target = package["computedRules"][0]
    context = {
        predicate["field"]: predicate["value"]
        for predicate in target["when"]["all"]
    }
    result = next(
        item for item in evaluate_package(package, context, {"side_setback": 20})
        if item["ruleId"] == target["id"]
    )
    assert result["status"] == "unknown"
    assert result["requirement"]["value"] is None
