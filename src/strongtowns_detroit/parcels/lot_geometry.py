"""Conservative screening of parcel dimensions against a named zoning scenario.

This module deliberately does not determine legality or buildability.  It reports
whether the supplied measurements fall below the dimensional thresholds selected
for a specific use scenario, while preserving unknown inputs as unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Mapping


class ScreenStatus(StrEnum):
    BELOW_AREA_AND_WIDTH = "below_area_and_width"
    BELOW_AREA = "below_area"
    BELOW_WIDTH = "below_width"
    MEETS_SCREENED_DIMENSIONS = "meets_screened_dimensions"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class DimensionalStandard:
    minimum_area_sqft: float
    minimum_width_ft: float | None = None


@dataclass(frozen=True)
class ScreenResult:
    status: ScreenStatus
    area_below: bool | None
    width_below: bool | None
    reason: str


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) and number > 0 else None


def screen_dimensions(
    *,
    district,
    area_sqft,
    width_ft,
    standards: Mapping[str, DimensionalStandard],
    area_tolerance_sqft: float = 25,
    width_tolerance_ft: float = 0.5,
    require_width: bool = True,
) -> ScreenResult:
    """Screen measured parcel dimensions without turning unknowns into passes.

    Tolerances avoid labeling assessor values that merely reflect rounding as
    below a threshold.  ``require_width=False`` supports an area-only screen
    where the available frontage is not the ordinance's defined lot width.
    """
    if district not in standards:
        return ScreenResult(
            ScreenStatus.NOT_EVALUATED, None, None, "district_not_in_scenario"
        )

    area = _number(area_sqft)
    width = _number(width_ft)
    standard = standards[district]
    if area is None:
        return ScreenResult(
            ScreenStatus.NOT_EVALUATED, None, None, "missing_or_invalid_area"
        )
    if require_width and standard.minimum_width_ft is not None and width is None:
        return ScreenResult(
            ScreenStatus.NOT_EVALUATED, None, None, "missing_or_invalid_width"
        )

    area_below = area < standard.minimum_area_sqft - area_tolerance_sqft
    width_below = None
    if require_width and standard.minimum_width_ft is not None:
        width_below = width < standard.minimum_width_ft - width_tolerance_ft

    if area_below and width_below:
        status = ScreenStatus.BELOW_AREA_AND_WIDTH
    elif area_below:
        status = ScreenStatus.BELOW_AREA
    elif width_below:
        status = ScreenStatus.BELOW_WIDTH
    else:
        status = ScreenStatus.MEETS_SCREENED_DIMENSIONS
    return ScreenResult(status, area_below, width_below, "evaluated")

