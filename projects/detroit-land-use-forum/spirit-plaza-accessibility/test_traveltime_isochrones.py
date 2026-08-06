from shapely.geometry import box

from traveltime_isochrones import departures, median_coverage


def test_departure_window_includes_both_endpoints():
    spec = {
        "service_date": "2026-07-29",
        "timezone": "America/Detroit",
        "departure_window": {
            "start": "12:00",
            "end": "13:00",
            "interval_minutes": 5,
        },
    }
    values = departures(spec)
    assert len(values) == 13
    assert values[0].strftime("%H:%M") == "12:00"
    assert values[-1].strftime("%H:%M") == "13:00"


def test_median_coverage_rejects_minority_only_area():
    common = box(-83.05, 42.32, -83.04, 42.33)
    outlier = box(-83.03, 42.32, -83.02, 42.33)
    result = median_coverage([common, common, outlier], cell_m=100)
    assert result.intersects(common)
    assert not result.intersects(outlier)
