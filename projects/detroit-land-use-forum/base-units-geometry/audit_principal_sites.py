#!/usr/bin/env python3
"""Distinguish principal-building ambiguity from broad candidate-site flags."""

from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARCELS = data_repository() / "pipelines/parcel-data/parcels_with_compliance.gpkg"
BUILDINGS = HERE / "data/base_units_buildings.geojson"
OVERLAPS = HERE / "output/building_parcel_overlaps.csv"
OUT = HERE / "output/principal_building_site_audit.csv"
SUMMARY = HERE / "output/principal_building_site_audit_summary.json"
DOMINANT_SHARE_THRESHOLD = 0.90


def normalize_parcel_id(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return cleaned or None


def run() -> None:
    parcels = gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id",
            "zoning_district",
            "use_code_description",
            "geometry",
        ],
    )
    parcels = parcels[
        parcels["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
        & parcels["use_code_description"].eq("SINGLE FAMILY")
    ].copy()
    parcels["parcel_key"] = parcels["parcel_id"].map(normalize_parcel_id)
    eligible_keys = set(parcels["parcel_key"].dropna())

    buildings = gpd.read_file(
        BUILDINGS,
        columns=["building_id", "parcel_id", "status", "geometry"],
    )
    buildings = buildings[
        buildings["status"].fillna("").str.lower().isin(
            {"active", "current"}
        )
    ].copy()
    buildings["parcel_key"] = buildings["parcel_id"].map(
        normalize_parcel_id
    )
    buildings = buildings[
        buildings["parcel_key"].isin(eligible_keys)
    ].to_crs(2898)
    buildings["footprint_area_sqft"] = buildings.geometry.area
    principal = (
        buildings.sort_values("footprint_area_sqft", ascending=False)
        .drop_duplicates("parcel_key")
        [["building_id", "parcel_key", "footprint_area_sqft"]]
    )

    overlaps = pd.read_csv(OVERLAPS, dtype={"parcel_id": "string"})
    overlaps["overlap_parcel_key"] = overlaps["parcel_id"].map(
        normalize_parcel_id
    )
    joined = principal.merge(
        overlaps[
            [
                "building_id",
                "overlap_parcel_key",
                "building_share",
            ]
        ],
        on="building_id",
        how="left",
    )
    joined["is_linked_parcel"] = joined["parcel_key"].eq(
        joined["overlap_parcel_key"]
    )
    counts = joined.groupby("building_id").size().rename(
        "material_parcel_count"
    )
    linked = (
        joined[joined["is_linked_parcel"]]
        .drop_duplicates("building_id")
        .set_index("building_id")["building_share"]
        .rename("linked_parcel_share")
    )
    audit = principal.join(
        counts, on="building_id"
    ).join(linked, on="building_id")
    audit["principal_site_ambiguous"] = (
        audit["material_parcel_count"].gt(1)
        & (
            audit["linked_parcel_share"].isna()
            | audit["linked_parcel_share"].lt(
                DOMINANT_SHARE_THRESHOLD
            )
        )
    )
    audit.to_csv(OUT, index=False)
    summary = {
        "single_family_parcels": int(len(parcels)),
        "parcels_with_principal_building": int(len(audit)),
        "principal_buildings_touching_multiple_parcels": int(
            audit["material_parcel_count"].gt(1).sum()
        ),
        "dominant_linked_share_threshold": DOMINANT_SHARE_THRESHOLD,
        "principal_site_ambiguous": int(
            audit["principal_site_ambiguous"].sum()
        ),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
