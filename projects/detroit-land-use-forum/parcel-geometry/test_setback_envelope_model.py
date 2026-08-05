from shapely.geometry import LineString, MultiPolygon, box

from setback_envelope_model import (
    principal_footprint_outside_area,
    single_family_setback_envelope,
)


def test_regular_30_by_100_lot_has_two_16_by_50_options():
    parcel = box(0, 0, 30, 100)
    front = LineString([(0, 0), (30, 0)])
    envelope = single_family_setback_envelope(parcel, front)
    assert envelope is not None
    assert round(envelope.option_left_4.area) == 800
    assert round(envelope.option_right_4.area) == 800


def test_building_may_use_either_side_yard_allocation():
    parcel = box(0, 0, 30, 100)
    front = LineString([(0, 0), (30, 0)])
    envelope = single_family_setback_envelope(parcel, front)
    building = box(4, 20, 20, 70)
    assert principal_footprint_outside_area(building, envelope) == 0


def test_shallow_lot_has_empty_envelope():
    parcel = box(0, 0, 30, 45)
    front = LineString([(0, 0), (30, 0)])
    envelope = single_family_setback_envelope(parcel, front)
    assert envelope is not None
    assert envelope.option_left_4.is_empty
    assert envelope.option_right_4.is_empty


def test_irregular_triangle_is_not_evaluated():
    parcel = box(0, 0, 30, 100).difference(box(10, 40, 30, 100))
    front = LineString([(0, 0), (30, 0)])
    assert single_family_setback_envelope(parcel, front) is None


def test_single_part_multipolygon_wrapper_is_supported():
    parcel = MultiPolygon([box(0, 0, 30, 100)])
    front = LineString([(0, 0), (30, 0)])
    envelope = single_family_setback_envelope(parcel, front)
    assert envelope is not None
    assert round(envelope.option_left_4.area) == 800
