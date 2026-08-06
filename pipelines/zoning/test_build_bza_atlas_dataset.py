import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from build_bza_atlas_dataset import build_tables


def sample_inputs(count=10, mapped=8):
    ids = [f"case-{i}" for i in range(count)]
    histories = pd.DataFrame({
        "case_history_id": ids,
        "printed_case_number": [str(i) for i in range(count)],
        "final_outcome": ["granted_reversed"] * count,
    })
    categories = pd.DataFrame({
        "case_history_id": ids,
        "category": ["parking_supply"] * count,
    })
    sites = gpd.GeoDataFrame({
        "case_history_id": ids[:mapped],
        "site_id": [f"site-{i}" for i in range(mapped)],
        "site_key": [f"{i}:MAIN" for i in range(mapped)],
        "parcel_id": [f"parcel-{i}" for i in range(mapped)],
        "address": [f"{i} MAIN" for i in range(mapped)],
        "match_method": ["exact"] * mapped,
        "geometry": [box(i, 0, i + 0.5, 0.5) for i in range(mapped)],
    }, crs="EPSG:3857")
    return histories, categories, sites


def test_publication_gate_is_inclusive():
    applications, _, summary, _ = build_tables(*sample_inputs())
    row = summary.iloc[0]
    assert len(applications) == 10
    assert row["match_share"] == 0.8
    assert bool(row["publication_eligible"])


def test_below_match_gate_is_not_eligible():
    _, _, summary, _ = build_tables(*sample_inputs(mapped=7))
    assert not bool(summary.iloc[0]["publication_eligible"])
    assert "less than 80% mapped" in summary.iloc[0]["gate_reason"]


def test_qa_category_never_publishes():
    histories, categories, sites = sample_inputs()
    categories["category"] = "dimensional_relief_unspecified"
    _, _, summary, _ = build_tables(histories, categories, sites)
    assert summary.iloc[0]["atlas_tier"] == "qa_only"
    assert not bool(summary.iloc[0]["publication_eligible"])
