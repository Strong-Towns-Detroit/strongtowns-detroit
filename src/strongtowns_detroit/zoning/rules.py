"""Reviewed, executable zoning rules with source-level provenance.

This module is deliberately downstream of ordinance extraction.  Extracted
strings remain source evidence; these records are the smaller, reviewed layer
that may be applied to a named development scenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class BuildingScenario(StrEnum):
    ONE_FAMILY_PRINCIPAL = "one_family_principal"
    TWO_FAMILY_PRINCIPAL = "two_family_principal"


class RuleMetric(StrEnum):
    MINIMUM_LOT_AREA = "minimum_lot_area"
    MINIMUM_LOT_WIDTH = "minimum_lot_width"
    MINIMUM_FRONT_SETBACK = "minimum_front_setback"
    MINIMUM_SIDE_SETBACK = "minimum_side_setback"
    MINIMUM_COMBINED_SIDE_SETBACK = "minimum_combined_side_setback"
    MINIMUM_REAR_SETBACK = "minimum_rear_setback"


class EvaluationStatus(StrEnum):
    MEETS = "meets"
    FAILS = "fails"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class NormalizedRule:
    rule_id: str
    ordinance_version: str
    district: str
    scenario: BuildingScenario
    metric: RuleMetric
    operator: str
    value: float
    unit: str
    source_refs: tuple[str, ...]
    source_value: str
    review_status: str = "verified"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: str
    status: EvaluationStatus
    measured_value: float | None
    required_value: float
    unit: str
    explanation: str
    source_refs: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()


# The repository's source snapshot uses the recodified Chapter 50 numbering.
# Update this identifier when a new ordinance snapshot is reviewed.
ORDINANCE_VERSION = "detroit-zoning-ordinance-chapter-50-repository-snapshot"

_DISTRICTS = tuple(f"R{number}" for number in range(1, 7))
_DISTRICT_SECTION = {
    district: f"50-13-{index}"
    for index, district in enumerate(_DISTRICTS, start=2)
}


def _rule(
    district: str,
    scenario: BuildingScenario,
    metric: RuleMetric,
    value: float,
    unit: str,
    source_value: str,
    metric_ref: str,
    *,
    notes: tuple[str, ...] = (),
) -> NormalizedRule:
    return NormalizedRule(
        rule_id=f"{district.lower()}:{scenario.value}:{metric.value}",
        ordinance_version=ORDINANCE_VERSION,
        district=district,
        scenario=scenario,
        metric=metric,
        operator=">=",
        value=value,
        unit=unit,
        source_refs=(_DISTRICT_SECTION[district], metric_ref),
        source_value=source_value,
        notes=notes,
    )


def _residential_rules() -> tuple[NormalizedRule, ...]:
    rules: list[NormalizedRule] = []
    for district in _DISTRICTS:
        rules.extend(
            _scenario_rules(
                district,
                BuildingScenario.ONE_FAMILY_PRINCIPAL,
                lot_area=5_000,
                lot_width=50,
            )
        )

    # The R1 table does not include two-family dwellings. R3 is the one
    # district whose reviewed table sets a 60-foot rather than 55-foot width.
    for district in _DISTRICTS[1:]:
        rules.extend(
            _scenario_rules(
                district,
                BuildingScenario.TWO_FAMILY_PRINCIPAL,
                lot_area=6_000,
                lot_width=60 if district == "R3" else 55,
            )
        )
    return tuple(rules)


def _scenario_rules(
    district: str,
    scenario: BuildingScenario,
    *,
    lot_area: float,
    lot_width: float,
) -> list[NormalizedRule]:
    return [
        _rule(
            district, scenario, RuleMetric.MINIMUM_LOT_AREA, lot_area,
            "square_feet", f"{lot_area:,.0f}", "50-13-222",
        ),
        _rule(
            district, scenario, RuleMetric.MINIMUM_LOT_WIDTH, lot_width,
            "feet", f"{lot_width:g}", "50-13-222",
            notes=(
                "Assessor frontage is not universally identical to legal lot width.",
            ),
        ),
        _rule(
            district, scenario, RuleMetric.MINIMUM_FRONT_SETBACK, 20,
            "feet", "20", "50-16-382",
        ),
        _rule(
            district, scenario, RuleMetric.MINIMUM_SIDE_SETBACK, 4,
            "feet", "4 ft. minimum/ 14 ft. combined", "50-16-382",
        ),
        _rule(
            district, scenario, RuleMetric.MINIMUM_COMBINED_SIDE_SETBACK, 14,
            "feet", "4 ft. minimum/ 14 ft. combined", "50-16-382",
        ),
        _rule(
            district, scenario, RuleMetric.MINIMUM_REAR_SETBACK, 30,
            "feet", "30", "50-13-231",
        ),
    ]


REVIEWED_RESIDENTIAL_RULES = _residential_rules()
_RULE_INDEX = {
    (rule.district, rule.scenario, rule.metric): rule
    for rule in REVIEWED_RESIDENTIAL_RULES
}


def rule_for(
    district: str,
    scenario: BuildingScenario,
    metric: RuleMetric,
) -> NormalizedRule | None:
    """Return a reviewed rule, preserving unsupported scenarios as absent."""
    try:
        scenario = BuildingScenario(scenario)
        metric = RuleMetric(metric)
    except ValueError:
        return None
    return _RULE_INDEX.get((str(district).upper(), scenario, metric))


def evaluate_minimum(
    rule: NormalizedRule | None,
    measured_value,
    *,
    measurement_tolerance: float = 0.0,
    assumptions: tuple[str, ...] = (),
) -> RuleEvaluation:
    """Evaluate a minimum while keeping the legal boundary exact.

    ``measurement_tolerance`` belongs to the measurement/classification, not
    to the ordinance rule. A value is classified as failing only when it lies
    more than the supplied tolerance below the legal minimum.
    """
    if rule is None:
        return RuleEvaluation(
            rule_id="unsupported-scenario",
            status=EvaluationStatus.NOT_APPLICABLE,
            measured_value=None,
            required_value=float("nan"),
            unit="unknown",
            explanation="No reviewed rule applies to this district and scenario.",
            source_refs=(),
            missing_inputs=("reviewed_applicable_rule",),
        )
    try:
        measured = float(measured_value)
    except (TypeError, ValueError):
        measured = float("nan")
    if not isfinite(measured) or measured < 0:
        return RuleEvaluation(
            rule_id=rule.rule_id,
            status=EvaluationStatus.UNKNOWN,
            measured_value=None,
            required_value=rule.value,
            unit=rule.unit,
            explanation="The required measurement is unavailable or invalid.",
            source_refs=rule.source_refs,
            assumptions=assumptions,
            missing_inputs=(rule.metric.value,),
        )
    fails = measured < rule.value - measurement_tolerance
    status = EvaluationStatus.FAILS if fails else EvaluationStatus.MEETS
    comparison = "falls below" if fails else "meets the screened boundary for"
    return RuleEvaluation(
        rule_id=rule.rule_id,
        status=status,
        measured_value=measured,
        required_value=rule.value,
        unit=rule.unit,
        explanation=(
            f"The measured value {comparison} the current {rule.value:g} "
            f"{rule.unit.replace('_', ' ')} minimum."
        ),
        source_refs=rule.source_refs,
        assumptions=assumptions,
    )
