"""Generate structurally verified requirements from district dimensional tables."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source, eq

DISTRICT_HEADING_RE = re.compile(
    r"^Sec\.\s*50-13-\d+\.\s*(?:-\s*)?([A-Z0-9]+) District\.$", re.I
)


def add_structural_dimensions(code: OrdinanceBuilder, source_corpus: dict) -> int:
    section_districts = _section_districts(source_corpus)
    candidates = compile_candidates(source_corpus)
    count = 0
    for item in candidates["dimensions"]:
        normalization = item["normalization"]
        section = item["source"]["section"]
        district = section_districts.get(section)
        if not normalization or not district:
            continue
        scenario_id = _slug(item["scenarioRaw"])
        code.district(district, f"{district} district", _district_category(district))
        code.use(scenario_id, item["scenarioRaw"], "dimensional_table_scenario")
        code.standard(
            id=item["id"],
            label=item["standardRaw"],
            metric=normalization["metric"],
            operator=normalization["operator"],
            value=normalization["value"],
            unit=normalization["unit"],
            when=(eq("district", district), eq("use", scenario_id)),
            source=Source(
                item["source"]["document"], (section,), item["valueRaw"],
                "Table cell is structurally verified; additional-regulation cells and "
                "cross-referenced exceptions remain separate work.",
            ),
            review_status="structurally_verified",
        )
        count += 1
    return count


def _section_districts(source_corpus: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for document in source_corpus["documents"]:
        for block in document["blocks"]:
            if block["type"] != "paragraph":
                continue
            match = DISTRICT_HEADING_RE.match(block["text"])
            if match and block.get("section"):
                result[block["section"]] = match.group(1).upper()
    return result


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "unnamed_use"


def _district_category(code: str) -> str:
    if code.startswith("R"):
        return "residential"
    if code.startswith("B"):
        return "business"
    if code.startswith("M"):
        return "industrial"
    return "special_or_overlay"
