"""Legal lot-coverage rules using the project's manual assessor-use crosswalk."""

from __future__ import annotations

import json
import math
from functools import lru_cache

from strongtowns_detroit.repositories import data_repository

RESIDENTIAL_DISTRICTS = {f"R{i}" for i in range(1, 7)}
MANUAL_USE_CROSSWALK = (
    data_repository()
    / "pipelines/parcel-data"
    / "parcel_use_codes_to_zoning_use_codes_manual_mapping.json"
)

ZONING_USE_TO_BUILDING_TYPE = {
    "Single-family detached dwelling": "single_family",
    "Two-family dwelling": "two_family",
    "Townhouse": "townhouse",
    "Multiple-family dwelling": "multiple_family",
}


@lru_cache(maxsize=1)
def manual_building_type_crosswalk() -> dict[str, str | None]:
    mapping = json.loads(MANUAL_USE_CROSSWALK.read_text(encoding="utf-8"))
    result: dict[str, str | None] = {}
    for assessor_use, groups in mapping.items():
        candidates = {
            ZONING_USE_TO_BUILDING_TYPE[specific_use]
            for group in groups
            for specific_use in group.get("specific_use", [])
            if specific_use in ZONING_USE_TO_BUILDING_TYPE
        }
        result[assessor_use.strip().upper()] = (
            next(iter(candidates)) if len(candidates) == 1 else None
        )
    return result


def coverage_building_type(
    zoning_district: object,
    use_description: object,
) -> str | None:
    district = str(zoning_district or "").strip().upper()
    use = str(use_description or "").strip().upper()
    if district not in RESIDENTIAL_DISTRICTS:
        return None
    building_type = manual_building_type_crosswalk().get(use)
    # Section 50-13-187 applies the two-family coverage rule on land zoned
    # R2–R6. An existing two-family use in R1 is not silently assigned it.
    if district == "R1" and building_type == "two_family":
        return None
    return building_type


def maximum_coverage_percent(
    building_type: str | None,
    lot_area_sqft: float,
) -> float | None:
    """Return the legal maximum using complete 100-square-foot increments.

    Single-family: 35%, increasing below 4,000 sq. ft., capped at 45%.
    Two-family: 35%, increasing below 4,300 sq. ft., capped at 45%.
    """
    if building_type not in {"single_family", "two_family"}:
        return None
    if lot_area_sqft <= 0:
        return None
    small_lot_boundary = (
        4_000 if building_type == "single_family" else 4_300
    )
    complete_hundreds = max(
        0, math.floor((small_lot_boundary - lot_area_sqft) / 100)
    )
    return float(min(45, 35 + complete_hundreds))
