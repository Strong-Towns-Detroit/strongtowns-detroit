"""Generate structurally verified use permissions from Article XII."""

from __future__ import annotations

import re

from strongtowns_detroit.zoning.candidates import compile_candidates
from strongtowns_detroit.zoning.codebook import OrdinanceBuilder, Source

CODE_SEMANTICS = {
    "—": ("not_allowed", "50-12-5"),
    "R": ("allowed_by_right", "50-12-4"),
    "C": ("conditional_use", "50-12-3"),
    "L": ("legislative_approval", "50-12-108"),
}


def add_structural_permissions(code: OrdinanceBuilder, source_corpus: dict) -> int:
    """Add table cells whose code has one source-defined meaning."""
    candidates = compile_candidates(source_corpus)
    count = 0
    for item in candidates["permissions"]:
        if item["permission"] in CODE_SEMANTICS:
            status, meaning_section = CODE_SEMANTICS[item["permission"]]
        elif item["normalization"] and item["normalization"]["status"] == "accessory_only":
            status, meaning_section = "accessory_only", item["normalization"]["authority"]
        else:
            continue
        use_id = _slug(item["useName"])
        district = item["district"]
        code.district(district, f"{district} district", _district_category(district))
        code.use(use_id, item["useName"], "ordinance_use")
        provenance = item["source"]
        code.permission(
            id=item["id"],
            use=use_id,
            district=district,
            permission=status,
            conditions=(meaning_section,),
            source=Source(
                provenance["document"],
                (provenance["section"], meaning_section),
                item["permission"],
                (
                    "Accessory-only condition compiled from the final-column note."
                    if status == "accessory_only"
                    else "Use-specific standards and final-column notes are compiled separately."
                ),
            ),
            review_status="structurally_verified",
        )
        count += 1
    return count


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
