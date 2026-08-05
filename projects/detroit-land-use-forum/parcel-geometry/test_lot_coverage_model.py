from lot_coverage_model import (
    coverage_building_type,
    maximum_coverage_percent,
)


def test_building_type_is_explicit_and_r_district_only():
    assert coverage_building_type("R2", "SINGLE FAMILY") == "single_family"
    assert coverage_building_type("R2", "TWO FAMILY") == "two_family"
    assert coverage_building_type("R3", "DUPLEX") == "two_family"
    assert coverage_building_type("R3", "HALF DUPLEX") == "two_family"
    assert coverage_building_type("R3", "ROW HOUSE") == "townhouse"
    assert coverage_building_type("R5", "FOUR FAMILY") == "multiple_family"
    assert coverage_building_type("R1", "DUPLEX") is None
    assert coverage_building_type("B4", "SINGLE FAMILY") is None
    assert coverage_building_type("R2", "INCOME BUNGALOW") is None


def test_single_family_small_lot_adjustment():
    assert maximum_coverage_percent("single_family", 4_000) == 35
    assert maximum_coverage_percent("single_family", 3_900) == 36
    assert maximum_coverage_percent("single_family", 3_000) == 45
    assert maximum_coverage_percent("single_family", 2_000) == 45


def test_two_family_small_lot_adjustment():
    assert maximum_coverage_percent("two_family", 4_300) == 35
    assert maximum_coverage_percent("two_family", 4_000) == 38
    assert maximum_coverage_percent("two_family", 3_500) == 43
    assert maximum_coverage_percent("two_family", 3_300) == 45
    assert maximum_coverage_percent("two_family", 3_000) == 45
