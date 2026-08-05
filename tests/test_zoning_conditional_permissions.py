from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.detroit_conditional_permissions import (
    add_reviewed_conditional_permissions,
)
from strongtowns_detroit.zoning.json_engine import evaluate_permissions


def package():
    builder = build_detroit_code()
    assert add_reviewed_conditional_permissions(builder) == 108
    return builder.compile()


def applicable_permission(compiled, context):
    return [
        row for row in evaluate_permissions(compiled, context)
        if row["status"] == "applicable"
    ]


def test_r3_multifamily_permission_branches_at_efficiency_share_boundary():
    compiled = package()
    base = {"district": "R3", "use": "multiple_family_dwelling"}
    assert applicable_permission(compiled, {**base, "efficiency_unit_share": 0.49})[0][
        "permission"
    ] == "allowed_by_right"
    assert applicable_permission(compiled, {**base, "efficiency_unit_share": 0.50})[0][
        "permission"
    ] == "conditional_use"


def test_b5_multifamily_permission_depends_on_ground_floor_space():
    compiled = package()
    base = {"district": "B5", "use": "multiple_family_dwelling"}
    assert applicable_permission(
        compiled, {**base, "ground_floor_commercial_or_pedestrian_space": True}
    )[0]["permission"] == "allowed_by_right"
    assert applicable_permission(
        compiled, {**base, "ground_floor_commercial_or_pedestrian_space": False}
    )[0]["permission"] == "conditional_use"


def test_missing_branch_fact_is_reported_unknown():
    results = evaluate_permissions(
        package(), {"district": "PCA", "use": "multiple_family_dwelling"}
    )
    assert len(results) == 2
    assert {row["status"] for row in results} == {"unknown"}
    assert {tuple(row["missingContext"]) for row in results} == {
        ("ground_floor_commercial_or_pedestrian_space",)
    }


def test_parking_structure_threshold_is_exact():
    compiled = package()
    base = {"district": "PC", "use": "parking_structure"}
    assert applicable_permission(
        compiled, {**base, "street_facing_ground_floor_pedestrian_space_share": 0.30}
    )[0]["permission"] == "allowed_by_right"
    assert applicable_permission(
        compiled, {**base, "street_facing_ground_floor_pedestrian_space_share": 0.299}
    )[0]["permission"] == "conditional_use"


def test_mkt_poultry_processing_uses_5000_square_foot_boundary():
    compiled = package()
    base = {"district": "MKT", "use": "poultry_or_small_game_processing"}
    assert applicable_permission(compiled, {**base, "gross_floor_area": 5000})[0][
        "permission"
    ] == "allowed_by_right"
    assert applicable_permission(compiled, {**base, "gross_floor_area": 5001})[0][
        "permission"
    ] == "conditional_use"


def test_b5_fast_food_project_form_and_drive_through_are_distinct():
    compiled = package()
    base = {"district": "B5", "use": "fast_food_restaurant"}
    assert applicable_permission(compiled, {
        **base, "has_drive_up_or_drive_through": False,
        "integrated_multistory_mixed_or_multitenant": True,
    })[0]["permission"] == "allowed_by_right"
    assert applicable_permission(compiled, {
        **base, "has_drive_up_or_drive_through": True,
    })[0]["permission"] == "conditional_use"


def test_b2_confection_branches_include_hard_6000_square_foot_prohibition():
    compiled = package()
    base = {"district": "B2", "use": "confection_manufacturing"}
    assert applicable_permission(compiled, {
        **base, "gross_floor_area": 3500, "retail_floor_area_share": 0.10,
        "traditional_main_street_overlay": True,
    })[0]["permission"] == "allowed_by_right"
    assert applicable_permission(compiled, {
        **base, "gross_floor_area": 6001, "retail_floor_area_share": 0.10,
        "traditional_main_street_overlay": False,
    })[0]["permission"] == "not_allowed"


def test_mkt_barber_upper_floor_case_remains_unassigned():
    compiled = package()
    context = {
        "district": "MKT", "use": "barber_or_beauty_shop",
        "single_story_building": False, "located_on_first_floor": False,
    }
    assert not applicable_permission(compiled, context)
