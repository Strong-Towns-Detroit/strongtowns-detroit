"""Reviewed Formula A/B definitions and structural table references."""

from __future__ import annotations

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq
from strongtowns_detroit.zoning.detroit_dimensions import (
    _section_districts,
    _slug,
)

ARTICLE_XIII = "ARTICLE_XIII.municode.json"


def add_side_setback_formulas(code: OrdinanceBuilder, source_corpus: dict) -> int:
    base_expression = {
        "op": "add",
        "args": [
            {"var": "building_length_along_adjacent_lot_line"},
            {"op": "multiply", "args": [2, {"var": "building_height"}]},
        ],
    }
    for name, divisor, minimum in (("formula_a", 15, None), ("formula_b", 6, 5)):
        code.formula(
            id=name,
            output_unit="feet",
            expression={"op": "divide", "args": [base_expression, divisor]},
            variables={
                "building_length_along_adjacent_lot_line": "feet",
                "building_height": "feet",
            },
            minimum=minimum,
            source=Source(
                ARTICLE_XIII, ("50-13-229",),
                "resulting sum divided by 15" if divisor == 15 else "resulting sum divided by six; minimum five feet",
            ),
        )

    districts = _section_districts(source_corpus)
    count = 0
    for item in compile_candidates(source_corpus)["dimensions"]:
        interpretation = item.get("interpretation") or {}
        if interpretation.get("type") != "named_formula":
            continue
        section = item["source"]["section"]
        district = districts.get(section)
        if not district:
            continue
        scenario = _slug(item["scenarioRaw"])
        code.computed_standard(
            id=item["id"],
            label=item["standardRaw"],
            when=(eq("district", district), eq("use", scenario)),
            metric="side_setback",
            operator=">=",
            formula=interpretation["formula"],
            source=Source(
                item["source"]["document"], (section, "50-13-229"), item["valueRaw"]
            ),
        )
        count += 1
    return count
