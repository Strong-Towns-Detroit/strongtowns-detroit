import geopandas as gpd
import pandas as pd

from build_lot_coverage_assets import classify_coverage, select_cases


def test_coverage_excludes_multi_parcel_candidates_and_missing_footprints():
    frame = gpd.GeoDataFrame({
        "building_type": ["single_family"] * 4,
        "lot_area_sqft": [4_000, 4_000, 4_000, 4_000],
        "footprint_sqft": [1_500, 1_400, None, 1_500],
        "candidate_multi_parcel_site": [False, False, False, True],
        "geometry": [None] * 4,
    })
    result = classify_coverage(frame, "single_family")
    assert result["evaluated"].tolist() == [True, True, False, False]
    assert result["above_maximum"].tolist() == [True, False, False, False]


def test_two_family_uses_its_own_small_lot_rule():
    frame = gpd.GeoDataFrame({
        "building_type": ["two_family", "single_family"],
        "lot_area_sqft": [4_000, 4_000],
        "footprint_sqft": [1_500, 1_500],
        "candidate_multi_parcel_site": [False, False],
        "geometry": [None, None],
    })
    result = classify_coverage(frame, "two_family")
    assert result.loc[0, "allowed_coverage_pct"] == 38
    assert pd.isna(result.loc[1, "allowed_coverage_pct"])
    assert result["evaluated"].tolist() == [True, False]


def test_bza_type_subsets_are_explicit():
    histories = pd.DataFrame([
        {
            "case_history_id": "single",
            "proposal": "addition to an existing single-family dwelling",
        },
        {
            "case_history_id": "duplex",
            "proposal": "construct two attached 2 family dwellings",
        },
        {
            "case_history_id": "ambiguous",
            "proposal": "addition to a residential home in an R2 district",
        },
    ])
    categories = pd.DataFrame([
        {
            "case_history_id": case_id,
            "category": "lot_coverage",
            "evidence": "excessive lot coverage",
        }
        for case_id in ["single", "duplex", "ambiguous"]
    ])
    assert select_cases(
        histories, categories, "single_family"
    )["case_history_id"].tolist() == ["single"]
    assert select_cases(
        histories, categories, "two_family"
    )["case_history_id"].tolist() == ["duplex"]
