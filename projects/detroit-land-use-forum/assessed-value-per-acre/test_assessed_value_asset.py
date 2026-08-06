import geopandas as gpd

from build_assessed_value_asset import classify, concentration


def test_classification_and_concentration():
    frame = gpd.GeoDataFrame({
        "assessed_value": [100, 100, 0, None],
        "total_square_footage": [20, 80, 100, 100],
        "geometry": [None] * 4,
    })
    result = classify(frame)
    assert result["recorded"].tolist() == [True, True, True, False]
    assert result["map_color"].iloc[2] != result["map_color"].iloc[0]
    # The first 10% of recorded acreage holds half the assessed value.
    assert concentration(result, 0.10) == 0.5
