"""Recreational-space-ratio formulas embedded in Article XIII tables."""

from __future__ import annotations

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq
from strongtowns_detroit.zoning.detroit_dimensions import (
    _district_category,
    _section_districts,
    _slug,
)


def add_recreational_space_formulas(code: OrdinanceBuilder, source_corpus: dict) -> int:
    candidates = compile_candidates(source_corpus)
    districts = _section_districts(source_corpus)
    ratios = sorted({
        float(item["interpretation"]["ratio"])
        for item in candidates["dimensions"]
        if item.get("interpretation") and item["interpretation"]["type"] == "ratio_formula"
    })
    for ratio in ratios:
        code.formula(
            id=_formula_id(ratio), output_unit="square_feet",
            expression={"op": "multiply", "args": [{"var": "gross_floor_area"}, ratio]},
            variables={"gross_floor_area": "square_feet"}, minimum=None,
            source=Source(
                "ARTICLE_XIII.municode.json",
                ("50-13-239",), f"gross floor area × {ratio:g} RSR",
            ),
            review_status="verified",
        )
    count = 0
    for item in candidates["dimensions"]:
        interpretation = item.get("interpretation")
        if not interpretation or interpretation["type"] != "ratio_formula":
            continue
        section = item["source"]["section"]
        district = districts.get(section)
        if not district:
            continue
        scenario = _slug(item["scenarioRaw"])
        ratio = float(interpretation["ratio"])
        code.district(district, f"{district} district", _district_category(district))
        code.use(scenario, item["scenarioRaw"], "dimensional_table_scenario")
        code.computed_standard(
            id=f"{item['id']}:recreational_space",
            label="Minimum recreational space",
            when=(eq("district", district), eq("use", scenario)),
            metric="recreational_space_area", operator=">=", formula=_formula_id(ratio),
            source=Source(
                item["source"]["document"], (section, "50-13-239"),
                item["valueRaw"],
                "RSR is a recreational-space requirement, not lot coverage.",
            ),
            review_status="verified",
        )
        count += 1
    return count


def _formula_id(ratio: float) -> str:
    return f"recreational_space_ratio_{str(ratio).replace('.', '_')}"
