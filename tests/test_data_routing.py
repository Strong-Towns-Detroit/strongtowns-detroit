from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from strongtowns_detroit.data.routing import (
    build_routing_anchor_tables,
    parcel_key_v1,
    stable_anchor_id,
    import_review_decisions,
)


def fixtures():
    parcels = gpd.GeoDataFrame(
        {"parcel_id": ["01-23.4", "02-00"]},
        geometry=[
            Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]),
            Polygon([(200, 0), (300, 0), (300, 100), (200, 100)]),
        ],
        crs="EPSG:2898",
    )
    addresses = gpd.GeoDataFrame(
        {
            "address_id": [10],
            "objectid": [99],
            "parcel_id": ["01-23.4"],
            "street_id": [7],
        },
        geometry=[Point(50, 10)],
        crs="EPSG:2898",
    )
    streets = gpd.GeoDataFrame(
        {"street_id": [7]},
        geometry=[LineString([(-100, -20), (400, -20)])],
        crs="EPSG:2898",
    )
    return parcels, addresses, streets


def test_parcel_key_is_named_and_source_identifier_is_not_changed():
    assert parcel_key_v1("01-23.4") == "01234"


def test_anchor_ids_are_stable_under_input_reordering_and_unrelated_streets():
    parcels, addresses, streets = fixtures()
    first = build_routing_anchor_tables(parcels, addresses, streets)["anchors"]
    unrelated = gpd.GeoDataFrame(
        {"street_id": [999]},
        geometry=[LineString([(10000, 10000), (10100, 10000)])],
        crs="EPSG:2898",
    )
    second = build_routing_anchor_tables(
        parcels.iloc[::-1], addresses.iloc[::-1],
        gpd.GeoDataFrame(
            pd.concat([unrelated, streets], ignore_index=True),
            geometry="geometry", crs="EPSG:2898",
        ),
    )["anchors"]
    assert set(first.anchor_id) == set(second.anchor_id)


def test_linked_and_fallback_review_contracts_and_frontages():
    parcels, addresses, streets = fixtures()
    result = build_routing_anchor_tables(parcels, addresses, streets)
    anchors = result["anchors"].set_index("parcel_key")
    assert anchors.loc["01234", "method"] == "linked_address"
    assert anchors.loc["01234", "review_status"] == "not_required"
    assert anchors.loc["0200", "method"] == "nearest_street_fallback"
    assert anchors.loc["0200", "review_status"] == "required"
    assert set(result["frontages"].anchor_id) == set(result["anchors"].anchor_id)
    assert result["anchors"].parcel_boundary_distance_ft.max() <= 0.01


def test_building_source_omission_is_null_and_supplied_empty_is_zero():
    parcels, addresses, streets = fixtures()
    omitted = build_routing_anchor_tables(parcels, addresses, streets)["evidence"]
    empty_buildings = gpd.GeoDataFrame(
        {"parcel_id": [], "status": []}, geometry=[], crs="EPSG:2898"
    )
    supplied = build_routing_anchor_tables(
        parcels, addresses, streets, empty_buildings
    )["evidence"]
    assert omitted.linked_current_building_count.isna().all()
    assert supplied.linked_current_building_count.eq(0).all()


def test_anchor_identity_tuple_is_explicit():
    assert stable_anchor_id("01234", "7", "linked_address") == stable_anchor_id(
        "01234", "7", "linked_address"
    )


def test_review_import_rejects_stale_parent_and_updates_valid_decision():
    current = pd.DataFrame({
        "anchor_id": ["a"], "review_status": ["required"], "reviewer": [None],
        "review_time": [None], "evidence_uri": [None], "notes": [None],
        "parent_disposition_snapshot": [None],
    })
    decisions = pd.DataFrame({
        "anchor_id": ["a"], "decision": ["approved"], "reviewer": ["reviewer"],
        "review_time": ["2026-08-26T12:00:00-04:00"],
        "evidence_uri": ["evidence/a"], "notes": ["checked"],
        "parent_disposition_snapshot": ["parent"],
    })
    result = import_review_decisions(
        decisions, current, expected_parent_manifest_sha256="parent"
    )
    assert result.iloc[0].review_status == "approved"
    stale = decisions.assign(parent_disposition_snapshot="old")
    with pytest.raises(ValueError, match="stale parent"):
        import_review_decisions(
            stale, current, expected_parent_manifest_sha256="parent"
        )
