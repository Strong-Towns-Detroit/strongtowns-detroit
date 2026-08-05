from build_dalt_comparison_asset import pv_reduction, series


def test_series_and_present_value_result():
    rows = series()
    assert len(rows) == 21
    assert rows[0]["conventional"] == 6000
    assert rows[0]["dalt"] == 2000
    assert rows[0]["lvt"] == 2000
    assert rows[-1]["conventional"] == 2000
    assert 0.965 < pv_reduction(rows) < 0.975
