from strongtowns_detroit.parcels.lot_geometry import (
    DimensionalStandard,
    ScreenStatus,
    screen_dimensions,
)


STANDARDS = {"R1": DimensionalStandard(5000, 50)}


def test_unknown_district_is_not_evaluated():
    result = screen_dimensions(
        district="PD", area_sqft=3000, width_ft=30, standards=STANDARDS
    )
    assert result.status == ScreenStatus.NOT_EVALUATED


def test_missing_measurement_is_not_a_pass():
    result = screen_dimensions(
        district="R1", area_sqft=None, width_ft=30, standards=STANDARDS
    )
    assert result.status == ScreenStatus.NOT_EVALUATED


def test_reports_each_failed_dimension():
    result = screen_dimensions(
        district="R1", area_sqft=3500, width_ft=40, standards=STANDARDS
    )
    assert result.status == ScreenStatus.BELOW_AREA_AND_WIDTH


def test_rounding_tolerance_avoids_false_precision():
    result = screen_dimensions(
        district="R1", area_sqft=4990, width_ft=49.8, standards=STANDARDS
    )
    assert result.status == ScreenStatus.MEETS_SCREENED_DIMENSIONS


def test_area_only_screen_does_not_claim_frontage_is_lot_width():
    result = screen_dimensions(
        district="R1",
        area_sqft=3500,
        width_ft=None,
        standards=STANDARDS,
        require_width=False,
    )
    assert result.status == ScreenStatus.BELOW_AREA

