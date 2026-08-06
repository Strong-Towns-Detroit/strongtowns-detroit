from strongtowns_detroit.zoning.parcel_evaluation import (
    ParcelMeasurements,
    evaluate_parcel_dimensions,
)
from strongtowns_detroit.zoning.rules import BuildingScenario, EvaluationStatus
from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.parcel_evaluation import evaluate_parcel_json


def test_named_scenario_produces_serializable_four_state_results():
    report = evaluate_parcel_dimensions(
        parcel_id="example",
        district="R2",
        scenario=BuildingScenario.ONE_FAMILY_PRINCIPAL,
        measurements=ParcelMeasurements(area_sqft=4_000, width_ft=30),
        area_tolerance_sqft=50,
        width_tolerance_ft=.5,
    )
    assert [item.status for item in report.evaluations] == [
        EvaluationStatus.FAILS,
        EvaluationStatus.FAILS,
    ]
    serialized = report.to_dict()
    assert serialized["scenario"] == "one_family_principal"
    assert serialized["evaluations"][0]["status"] == "fails"


def test_two_family_uses_its_own_thresholds():
    report = evaluate_parcel_dimensions(
        parcel_id="example",
        district="R3",
        scenario=BuildingScenario.TWO_FAMILY_PRINCIPAL,
        measurements=ParcelMeasurements(area_sqft=5_500, width_ft=57),
    )
    assert all(
        result.status == EvaluationStatus.FAILS
        for result in report.evaluations
    )


def test_public_parcel_path_consumes_compiled_json():
    package = build_detroit_code().compile()
    results = evaluate_parcel_json(
        package,
        district="R3",
        use="two_family_dwelling",
        building_role="principal",
        measurements={"lot_area": 5_500, "lot_width": 57},
    )
    failed = {
        item["requirement"]["metric"]
        for item in results if item["status"] == "fails"
    }
    assert {"lot_area", "lot_width"}.issubset(failed)
