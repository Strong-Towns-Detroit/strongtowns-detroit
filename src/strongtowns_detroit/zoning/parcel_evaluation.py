"""Compose reviewed zoning rules into a parcel/scenario result."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from strongtowns_detroit.zoning.rules import (
    BuildingScenario,
    RuleEvaluation,
    RuleMetric,
    evaluate_minimum,
    rule_for,
)
from strongtowns_detroit.zoning.json_engine import evaluate_package


@dataclass(frozen=True)
class ParcelMeasurements:
    area_sqft: float | None
    width_ft: float | None
    width_source: str = "assessor_frontage_proxy"


@dataclass(frozen=True)
class ParcelRuleReport:
    parcel_id: str
    district: str
    scenario: BuildingScenario
    evaluations: tuple[RuleEvaluation, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["scenario"] = self.scenario.value
        for result in data["evaluations"]:
            result["status"] = result["status"].value
        return data


def evaluate_parcel_dimensions(
    *,
    parcel_id: str,
    district: str,
    scenario: BuildingScenario,
    measurements: ParcelMeasurements,
    area_tolerance_sqft: float = 0.0,
    width_tolerance_ft: float = 0.0,
) -> ParcelRuleReport:
    width_assumptions = (
        f"Lot width is screened using {measurements.width_source}; it may not "
        "equal legal lot width in every parcel configuration.",
    )
    area = evaluate_minimum(
        rule_for(district, scenario, RuleMetric.MINIMUM_LOT_AREA),
        measurements.area_sqft,
        measurement_tolerance=area_tolerance_sqft,
    )
    width = evaluate_minimum(
        rule_for(district, scenario, RuleMetric.MINIMUM_LOT_WIDTH),
        measurements.width_ft,
        measurement_tolerance=width_tolerance_ft,
        assumptions=width_assumptions,
    )
    return ParcelRuleReport(
        parcel_id=parcel_id,
        district=district,
        scenario=scenario,
        evaluations=(area, width),
    )


def evaluate_parcel_json(
    package: dict,
    *,
    district: str,
    use: str,
    building_role: str,
    measurements: dict,
) -> list[dict]:
    """Public execution path: evaluate only the compiled JSON package."""
    return evaluate_package(
        package,
        {"district": district, "use": use, "building_role": building_role},
        measurements,
    )
