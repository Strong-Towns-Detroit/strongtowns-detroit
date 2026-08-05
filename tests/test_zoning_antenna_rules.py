from strongtowns_detroit.zoning.detroit_antenna_rules import add_reviewed_antenna_rules
from strongtowns_detroit.zoning.detroit_code import build_detroit_code
from strongtowns_detroit.zoning.json_engine import evaluate_permissions


def package():
    builder = build_detroit_code()
    counts = add_reviewed_antenna_rules(builder)
    return counts, builder.compile()


def applicable(compiled, context):
    return [row for row in evaluate_permissions(compiled, context) if row["status"] == "applicable"]


def test_category_d_rules_compile_as_branches_not_copied_matrix_codes():
    counts, compiled = package()
    assert counts == {"permissions": 41, "provisions": 6}
    assert len(compiled["provisions"]) == 6


def test_r4_category_d_distance_controls_conditional_or_prohibited():
    _, compiled = package()
    base = {"district": "R4", "use": "category_d_antenna_tower"}
    assert applicable(compiled, {**base, "distance_to_r1_r3_or_single_two_family_home": 121})[0][
        "permission"
    ] == "conditional_use"
    assert applicable(compiled, {**base, "distance_to_r1_r3_or_single_two_family_home": 120})[0][
        "permission"
    ] == "not_allowed"


def test_industrial_exact_120_foot_gap_remains_unknown():
    _, compiled = package()
    results = evaluate_permissions(compiled, {
        "district": "M2", "use": "category_d_antenna_tower",
        "distance_to_single_two_family_home": 120,
    })
    assert results
    assert not applicable(compiled, {
        "district": "M2", "use": "category_d_antenna_tower",
        "distance_to_single_two_family_home": 120,
    })


def test_p1_general_antenna_prohibition_is_explicit():
    _, compiled = package()
    assert applicable(compiled, {"district": "P1", "use": "antenna"})[0][
        "permission"
    ] == "not_allowed"
