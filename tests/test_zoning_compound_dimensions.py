from pathlib import Path

from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_compound_dimensions import add_compound_side_yards
from strongtowns_detroit.zoning.detroit_recreational_space import (
    add_recreational_space_formulas,
)
from strongtowns_detroit.zoning.json_engine import evaluate_package
from strongtowns_detroit.zoning.source_model import compile_source_corpus

ROOT = Path(__file__).resolve().parents[1]


def source():
    return compile_source_corpus(ROOT / "resources")


def test_side_yard_compounds_become_two_requirements_each():
    builder = build_detroit_code()
    assert add_compound_side_yards(builder, source()) == 34
    rules = [item for item in builder.compile()["rules"] if item["id"].endswith((":individual", ":combined"))]
    assert len(rules) == 34
    assert {item["requirement"]["metric"] for item in rules} == {
        "side_setback", "combined_side_setback"
    }


def test_rsr_is_recreational_space_not_lot_coverage():
    builder = build_detroit_code()
    assert add_recreational_space_formulas(builder, source()) == 12
    compiled = builder.compile()
    assert len(compiled["formulas"]) == 4
    rule = next(item for item in compiled["computedRules"] if item["formula"] == "recreational_space_ratio_0_12")
    context = {item["field"]: item["value"] for item in rule["when"]["all"]}
    result = next(item for item in evaluate_package(
        compiled, context, {"gross_floor_area": 10_000, "recreational_space_area": 1_199}
    ) if item["ruleId"] == rule["id"])
    assert result["requirement"]["metric"] == "recreational_space_area"
    assert result["requirement"]["value"] == 1200
    assert result["status"] == "fails"
