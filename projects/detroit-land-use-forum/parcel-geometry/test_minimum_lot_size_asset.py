import geopandas as gpd
import pandas as pd

from build_minimum_lot_size_asset import (
    classify_lot_area,
    select_residential_area_cases,
)


def test_area_classification_uses_one_percent_tolerance():
    frame = gpd.GeoDataFrame({
        "zoning_district": ["R2", "R2", "R2", "B4"],
        "total_square_footage": [4949, 4950, None, 1000],
        "geometry": [None] * 4,
    })
    result = classify_lot_area(frame)
    assert result["below_minimum"].tolist() == [True, False, False, False]
    assert result["evaluated"].tolist() == [True, True, False, False]


def test_detroit_parks_taxpayer_is_out_of_scope():
    frame = gpd.GeoDataFrame({
        "zoning_district": ["R1", "R2", "R3"],
        "total_square_footage": [4_000, 4_000, 4_000],
        "taxpayer_1": [
            "DETROIT PARKS & RECREATION",
            "CITY OF DETROIT PARKS & REC",
            "RECOVERYPARK FARMS INC",
        ],
        "taxpayer_2": [None, None, None],
        "geometry": [None] * 3,
    })
    result = classify_lot_area(frame)
    assert result["in_scope"].tolist() == [False, False, True]
    assert result["evaluated"].tolist() == [False, False, True]


def test_bza_area_subset_excludes_width_and_nonresidential_cases():
    histories = pd.DataFrame([
        {
            "case_history_id": "area-r2", "proposal": "R2 deficient lot area",
            "final_outcome": "granted_reversed",
        },
        {
            "case_history_id": "width-r2", "proposal": "R2 excessive lot width",
            "final_outcome": "granted_reversed",
        },
        {
            "case_history_id": "area-b4", "proposal": "B4 deficient lot area",
            "final_outcome": "granted_reversed",
        },
    ])
    categories = pd.DataFrame([
        {"case_history_id": "area-r2", "category": "lot_dimensions",
         "evidence": '["deficient lot area"]'},
        {"case_history_id": "width-r2", "category": "lot_dimensions",
         "evidence": '["excessive lot width"]'},
        {"case_history_id": "area-b4", "category": "lot_dimensions",
         "evidence": '["deficient lot area"]'},
    ])
    result = select_residential_area_cases(histories, categories)
    assert result["case_history_id"].tolist() == ["area-r2"]
