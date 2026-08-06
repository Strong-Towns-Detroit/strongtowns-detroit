from build_parking_land_asset import (
    SQFT_PER_ACRE,
    acres,
    calculations,
)


def test_acre_conversion():
    assert acres(1, SQFT_PER_ACRE) == 1
    assert round(acres(1075, 300), 3) == 7.404
    assert round(acres(1075, 350), 3) == 8.638


def test_land_totals_reconcile():
    parking, types, sensitivity = calculations()
    assert parking["requested_shortfall_spaces"] == 1075
    assert types["gap"].sum() == 1075
    assert round(types["midpoint_acres"].sum(), 3) == 8.021
    assert sensitivity["square_feet_per_space"].tolist() == [
        250, 300, 325, 350, 400
    ]
