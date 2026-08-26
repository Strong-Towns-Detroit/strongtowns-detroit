import geopandas as gpd
from shapely.geometry import Point, Polygon

from strongtowns_detroit.data.osm import normalize_osm_features, prepare_osm_source


def test_osm_normalization_preserves_all_category_tags_and_source_identity():
    frame = gpd.GeoDataFrame(
        {
            "amenity": ["cafe", None],
            "shop": ["bakery", "books"],
        },
        index=[("node", 1), ("way", 2)],
        geometry=[
            Point(-83, 42),
            Polygon([(-83, 42), (-83, 42.01), (-82.99, 42.01), (-83, 42)]),
        ],
        crs="EPSG:4326",
    )
    result = normalize_osm_features(frame).set_index("source_id")
    assert result.loc["osm:node:1", "tag_keys"] == ["amenity", "shop"]
    assert result.loc["osm:node:1", "routing_point_method"] == "source_point"
    assert result.loc["osm:way:2", "routing_point_method"] == "representative_point"
    assert result.loc["osm:way:2", "source_geometry_type"] == "Polygon"
    source = prepare_osm_source(frame).set_index("source_id")
    assert source.loc["osm:way:2"].geometry.geom_type == "Polygon"


def test_osm_normalization_accounts_for_rejected_features():
    frame = gpd.GeoDataFrame(
        {"amenity": ["cafe", None]},
        index=[("node", 1), ("node", 2)],
        geometry=[Point(-83, 42), Point(-83.1, 42.1)],
        crs="EPSG:4326",
    )
    accepted, rejected = prepare_osm_source(frame, return_rejected=True)
    assert len(accepted) == 1
    assert rejected.to_dict("records") == [{
        "source_row": 1,
        "source_id": "osm:node:2",
        "reason": "missing_tags",
    }]
