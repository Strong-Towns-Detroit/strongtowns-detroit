from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.codebook import Source
from strongtowns_detroit.zoning.detroit_special_district_dimensions import (
    add_sd1_sd2_dimensions,
)
from strongtowns_detroit.zoning.json_engine import evaluate_package


def package():
    builder = build_detroit_code()
    # Formula A is shared with Article XIII and referenced by SD1/SD2.
    builder.formula(
        id="formula_a", output_unit="feet",
        expression={"op": "divide", "args": [
            {"op": "add", "args": [
                {"var": "building_length_along_adjacent_lot_line"},
                {"op": "multiply", "args": [2, {"var": "building_height"}]},
            ]}, 15,
        ]},
        variables={}, minimum=None,
        source=Source(
            "ARTICLE_XIII.___INTENSITY_AND_DIMENSIONAL_STANDARDS.docx",
            ("50-13-229",), "Formula A",
        ),
    )
    counts = add_sd1_sd2_dimensions(builder)
    return counts, builder.compile()


def test_special_district_rule_counts_are_explicit():
    counts, _ = package()
    assert counts == {"rules": 16, "computedRules": 6, "formulas": 3, "provisions": 2}


def test_sd1_front_setback_uses_lesser_of_adjacent_average_or_20():
    _, compiled = package()
    result = next(item for item in evaluate_package(
        compiled, {"district": "SD1"},
        {"adjacent_buildings_average_front_setback": 12, "front_setback": 13},
    ) if item["ruleId"] == "sd1:maximum_front_setback")
    assert result["requirement"]["value"] == 12
    assert result["status"] == "fails"


def test_sd2_mixed_use_height_bonus_caps_at_80_feet():
    _, compiled = package()
    context = {
        "district": "SD2", "mixed_use_building": True,
        "abutting_right_of_way_width": 90, "distance_to_r1_r3": 40,
    }
    result = next(item for item in evaluate_package(
        compiled, context, {"height": 81}
    ) if item["ruleId"] == "sd2:mixed_height_bonus")
    assert result["requirement"]["value"] == 80
    assert result["status"] == "fails"


def test_sd1_side_formula_only_applies_beside_r1_r4():
    _, compiled = package()
    context = {
        "district": "SD1", "adjacent_to_r1_r4": True,
    }
    result = next(item for item in evaluate_package(compiled, context, {
        "building_length_along_adjacent_lot_line": 60,
        "building_height": 30, "side_setback": 7,
    }) if item["ruleId"] == "sd1:side_setback_adjacent_r1_r4")
    assert result["requirement"]["value"] == 8
    assert result["status"] == "fails"
