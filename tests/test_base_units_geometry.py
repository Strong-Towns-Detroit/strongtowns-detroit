import importlib.util
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, box


MODULE_PATH = (
    Path(__file__).parents[1]
    / "projects/detroit-land-use-forum/base-units-geometry/geometry_model.py"
)
SPEC = importlib.util.spec_from_file_location("base_units_geometry", MODULE_PATH)
geometry_model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry_model)


def test_normalize_parcel_id_removes_punctuation():
    assert geometry_model.normalize_parcel_id("02000184.") == "02000184"
    assert geometry_model.normalize_parcel_id(None) is None


def test_frontage_selects_edge_parallel_and_nearest_to_street():
    parcel = box(0, 20, 30, 120)
    street = LineString([(-100, 0), (100, 0)])
    result = geometry_model.estimate_street_facing_edge(parcel, street)
    assert result["geometry_frontage"] == 30
    assert result["edge_to_street_distance"] == 20
    assert result["frontage_confidence"] == "high"


def test_building_overlap_creates_multi_parcel_candidate_site():
    parcels = gpd.GeoDataFrame(
        {"parcel_id": ["A", "B"]},
        geometry=[box(0, 0, 30, 100), box(30, 0, 60, 100)],
        crs=2898,
    )
    buildings = gpd.GeoDataFrame(
        {"building_id": [1]},
        geometry=[box(20, 20, 40, 60)],
        crs=2898,
    )
    overlaps = geometry_model.building_parcel_overlaps(buildings, parcels)
    assert set(overlaps["parcel_id"]) == {"A", "B"}
    sites = geometry_model.infer_building_linked_sites(overlaps)
    assert sites["candidate_site_id"].nunique() == 1
    assert set(sites["parcel_id"]) == {"A", "B"}

