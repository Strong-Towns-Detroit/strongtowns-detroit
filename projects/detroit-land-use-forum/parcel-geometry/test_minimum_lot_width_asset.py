import geopandas as gpd
import pandas as pd

from build_minimum_lot_width_asset import (
    classify_lot_width,
    select_residential_width_cases,
)


def test_width_classification_uses_one_percent_tolerance():
    frame = gpd.GeoDataFrame({
        "zoning_district": ["R2", "R2", "R2", "B4"],
        "frontage": [49.49, 49.5, None, 25],
        "geometry": [None] * 4,
    })
    result = classify_lot_width(frame)
    assert result["below_minimum"].tolist() == [True, False, False, False]
    assert result["evaluated"].tolist() == [True, True, False, False]


def test_detroit_parks_taxpayer_is_out_of_scope():
    frame = gpd.GeoDataFrame({
        "zoning_district": ["R1", "R2", "R3"],
        "frontage": [40, 40, 40],
        "taxpayer_1": [
            "DETROIT PARKS AND RECREATION DEPT.",
            "PARKS & RECREATION",
            "KIRBY PARKING STRUCTURE LLC",
        ],
        "taxpayer_2": [None, None, None],
        "geometry": [None] * 3,
    })
    result = classify_lot_width(frame)
    assert result["in_scope"].tolist() == [False, False, True]
    assert result["evaluated"].tolist() == [False, False, True]


def test_bza_width_subset_excludes_excessive_and_nonresidential_cases():
    histories = pd.DataFrame([
        {
            "case_history_id": "width-r2",
            "proposal": "R2 deficient lot width",
            "final_outcome": "granted_reversed",
        },
        {
            "case_history_id": "excess-r2",
            "proposal": (
                "R2 maximum lot size and width: 70 feet lot width required, "
                "128 feet proposed, excessive by 58 feet"
            ),
            "final_outcome": "granted_reversed",
        },
        {
            "case_history_id": "width-b4",
            "proposal": "B4 deficient lot width",
            "final_outcome": "granted_reversed",
        },
    ])
    categories = pd.DataFrame([
        {
            "case_history_id": "width-r2",
            "category": "lot_dimensions",
            "evidence": '["deficient lot width"]',
        },
        {
            "case_history_id": "excess-r2",
            "category": "lot_dimensions",
            "evidence": '["excessive lot width"]',
        },
        {
            "case_history_id": "width-b4",
            "category": "lot_dimensions",
            "evidence": '["deficient lot width"]',
        },
    ])
    result = select_residential_width_cases(histories, categories)
    assert result["case_history_id"].tolist() == ["width-r2"]
