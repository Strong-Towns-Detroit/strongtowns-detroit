import geopandas as gpd

from build_land_value_estimate import model


def test_model_uses_landmap_then_fallback():
    rows = []
    for index in range(20):
        rows.append({
            "parcel_id": f"vacant-{index}",
            "property_class_description": "RESIDENTIAL-VACANT",
            "assessed_value": 100 + index,
            "total_square_footage": 100,
            "landmap": "A",
            "neighborhood": "N",
            "geometry": None,
        })
    rows.append({
        "parcel_id": "improved",
        "property_class_description": "RESIDENTIAL-IMPROVED",
        "assessed_value": 10_000,
        "total_square_footage": 200,
        "landmap": "A",
        "neighborhood": "N",
        "geometry": None,
    })
    result, audit = model(gpd.GeoDataFrame(rows))
    improved = result[result["parcel_id"].eq("improved")].iloc[0]
    assert improved["estimate_method"] == "landmap median"
    assert improved["estimated_assessed_land_value"] > 0
    assert audit["training_comparables_after_1pct_tail_trim"] > 0
