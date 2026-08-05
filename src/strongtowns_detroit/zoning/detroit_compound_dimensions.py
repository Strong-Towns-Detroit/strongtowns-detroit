"""Compound dimensional cells split into their independent requirements."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq
from strongtowns_detroit.zoning.detroit_dimensions import (
    _district_category,
    _section_districts,
    _slug,
)

SIDE_RE = re.compile(
    r"^(?P<minimum>[\d.]+)\s*ft\.\s*minimum\s*/\s*(?P<combined>[\d.]+)\s*ft\.\s*combined$",
    re.I,
)


def add_compound_side_yards(code: OrdinanceBuilder, source_corpus: dict) -> int:
    districts = _section_districts(source_corpus)
    count = 0
    for item in compile_candidates(source_corpus)["dimensions"]:
        match = SIDE_RE.fullmatch(item["valueRaw"])
        district = districts.get(item["source"]["section"])
        if not match or not district:
            continue
        scenario = _slug(item["scenarioRaw"])
        code.district(district, f"{district} district", _district_category(district))
        code.use(scenario, item["scenarioRaw"], "dimensional_table_scenario")
        for suffix, metric, amount in (
            ("individual", "side_setback", float(match.group("minimum"))),
            ("combined", "combined_side_setback", float(match.group("combined"))),
        ):
            code.minimum(
                id=f"{item['id']}:{suffix}",
                label=(
                    "Minimum individual side setback" if suffix == "individual"
                    else "Minimum combined side setbacks"
                ),
                metric=metric, value=amount, unit="feet",
                when=(eq("district", district), eq("use", scenario)),
                source=Source(
                    item["source"]["document"],
                    (item["source"]["section"], "50-16-382"),
                    item["valueRaw"],
                    "Compound table cell split without discarding either requirement.",
                ),
                review_status="structurally_verified",
            )
            count += 1
    return count
