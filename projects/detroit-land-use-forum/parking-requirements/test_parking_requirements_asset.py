from build_parking_requirements_asset import (
    PARKING_VALUES,
    outcome_counts,
    parking_cases,
)


def test_explicit_parking_pairs_are_consistent():
    cases = parking_cases()
    numeric = cases[cases["numeric_status"].eq("explicit_pair")]

    assert len(cases) == 69
    assert len(numeric) == len(PARKING_VALUES) == 35
    assert numeric["required_spaces"].sum() == 1741
    assert numeric["proposed_spaces"].sum() == 666
    assert numeric["shortfall_spaces"].sum() == 1075
    assert (numeric["proposed_spaces"] <= numeric["required_spaces"]).all()


def test_parking_category_outcomes():
    assert outcome_counts(parking_cases()) == (61, 3, 5)
