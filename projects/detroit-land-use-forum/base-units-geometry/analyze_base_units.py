#!/usr/bin/env python3
"""Fetch and analyze Detroit's current Base Units geometry."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = HERE / "data"
OUTPUT = HERE / "output"
PARCELS = REPO / "pipelines/parcel-data/Parcels.geojson"
SERVICE = (
    "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/"
    "BaseUnitFeatures/FeatureServer"
)
LAYERS = {"addresses": 0, "streets": 1, "buildings": 2}
FETCH_OPTIONS = {
    "addresses": {
        # Retain the complete address layer. Besides the address-to-parcel
        # relationship used by the geometry analysis, this supports secondary
        # and historical-address matching for BZA cases.
        "outFields": "*",
        "returnGeometry": "true",
    },
    "streets": {"outFields": "*", "returnGeometry": "true"},
    "buildings": {"outFields": "*", "returnGeometry": "true"},
}

sys.path.insert(0, str(HERE))
from geometry_model import (  # noqa: E402
    building_parcel_overlaps,
    estimate_street_facing_edge,
    infer_building_linked_sites,
    normalize_parcel_id,
)


def request_json(url: str, parameters: dict[str, object]) -> dict:
    # POST avoids ArcGIS/HTTP URL-length failures when object ID batches are
    # supplied. The prior GET implementation produced HTTP 400 on the first
    # feature page even though the ID query succeeded.
    encoded = urllib.parse.urlencode(parameters).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ArcGIS request failed ({error.code}) for {url}: {detail}"
        ) from error
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload


def fetch_layer(name: str, discard_pages: bool = False) -> Path:
    """Download one ArcGIS layer without relying on a one-shot Hub export."""
    DATA.mkdir(parents=True, exist_ok=True)
    layer = LAYERS[name]
    url = f"{SERVICE}/{layer}/query"
    ids = request_json(
        url, {"where": "1=1", "returnIdsOnly": "true", "f": "json"}
    ).get("objectIds", [])
    destination = DATA / f"base_units_{name}.geojson"
    page_dir = DATA / f".{name}_pages"
    page_dir.mkdir(exist_ok=True)
    options = FETCH_OPTIONS[name]
    for start in range(0, len(ids), 2000):
        batch = ids[start : start + 2000]
        page_path = page_dir / f"{start:09d}.json"
        payload = None
        if page_path.exists():
            try:
                cached = json.loads(page_path.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and "features" in cached:
                    payload = cached
            except (json.JSONDecodeError, OSError):
                # An interrupted/disk-full write from an earlier run may leave
                # an empty or truncated page. It is not completed progress.
                pass
        if payload is None:
            payload = request_json(
                url,
                {
                    "objectIds": ",".join(map(str, batch)),
                    **options,
                    "outSR": 4326,
                    "f": "geojson",
                },
            )
        temporary_page = page_path.with_suffix(".tmp")
        temporary_page.write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
        temporary_page.replace(page_path)
        print(f"{name}: {min(start + len(batch), len(ids)):,}/{len(ids):,}")
        time.sleep(0.05)
    # Stream the consolidated GeoJSON so the page cache and a second in-memory
    # copy of the full layer are never required simultaneously.
    temporary_destination = destination.with_suffix(".tmp")
    with temporary_destination.open("w", encoding="utf-8") as stream:
        stream.write('{"type":"FeatureCollection","features":[')
        first = True
        for start in range(0, len(ids), 2000):
            page = json.loads(
                (page_dir / f"{start:09d}.json").read_text(encoding="utf-8")
            )
            for feature in page.get("features", []):
                if not first:
                    stream.write(",")
                json.dump(feature, stream, separators=(",", ":"))
                first = False
        stream.write("]}")
    temporary_destination.replace(destination)
    if discard_pages:
        import shutil

        shutil.rmtree(page_dir)
        print(f"{name}: discarded completed page cache {page_dir}")
    return destination


def load_parcels(sample: int | None = None) -> gpd.GeoDataFrame:
    columns = [
        "parcel_id",
        "frontage",
        "address",
        "street_name",
        "related_parcel_id",
        "taxpayer_1",
        "zoning_district",
        "geometry",
    ]
    parcels = gpd.read_file(PARCELS, columns=columns)
    parcels["parcel_key"] = parcels["parcel_id"].map(normalize_parcel_id)
    parcels = parcels.dropna(subset=["parcel_key", "geometry"]).drop_duplicates(
        "parcel_key"
    )
    if sample and sample < len(parcels):
        parcels = parcels.sample(sample, random_state=20260726)
    return parcels.to_crs(2898)


def analyze(sample: int | None = None) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    buildings = gpd.read_file(DATA / "base_units_buildings.geojson").to_crs(2898)
    streets = gpd.read_file(DATA / "base_units_streets.geojson").to_crs(2898)
    addresses_path = DATA / "base_units_addresses.geojson"
    addresses = (
        gpd.read_file(addresses_path)
        if addresses_path.exists()
        else gpd.GeoDataFrame()
    )
    parcels = load_parcels(sample)
    if "status" in buildings:
        buildings = buildings[
            buildings["status"].fillna("").str.lower().isin({"active", "current"})
        ].copy()
    buildings["linked_parcel_key"] = buildings["parcel_id"].map(normalize_parcel_id)

    overlaps = building_parcel_overlaps(
        buildings.rename(columns={"parcel_id": "base_units_parcel_id"}),
        parcels[["parcel_key", "geometry"]].rename(
            columns={"parcel_key": "parcel_id"}
        ),
        parcel_id_col="parcel_id",
    )
    overlaps.to_csv(OUTPUT / "building_parcel_overlaps.csv", index=False)
    sites = infer_building_linked_sites(overlaps)
    sites.to_csv(OUTPUT / "building_linked_candidate_sites.csv", index=False)

    # Prefer Base Units' address-to-street relationship where fields are
    # available. Fall back to the nearest named street matching assessor data,
    # then to the nearest street geometrically.
    street_lookup = streets.set_index("street_id").geometry.to_dict()
    parcel_street: dict[str, object] = {}
    required = {"parcel_id", "street_id"}
    if required.issubset(addresses.columns):
        address_rows = addresses.dropna(subset=list(required)).copy()
        address_rows["parcel_key"] = address_rows["parcel_id"].map(
            normalize_parcel_id
        )
        for parcel_key, group in address_rows.groupby("parcel_key"):
            geometries = [
                street_lookup[street_id]
                for street_id in group["street_id"]
                if street_id in street_lookup
            ]
            if geometries:
                parcel_street[parcel_key] = unary_union(geometries)

    street_tree = streets.sindex
    frontage_records = []
    frontage_geometries = []
    for index, parcel in parcels.iterrows():
        street = parcel_street.get(parcel.parcel_key)
        source = "base_units_address_link"
        if street is None:
            source = "nearest_base_units_street"
            nearest = list(street_tree.nearest(parcel.geometry, return_all=False))
            if not nearest or len(nearest) < 2 or not len(nearest[1]):
                continue
            street = streets.iloc[int(nearest[1][0])].geometry
        result = estimate_street_facing_edge(parcel.geometry, street)
        geometry = result.pop("geometry")
        assessor = pd.to_numeric(parcel.frontage, errors="coerce")
        estimate = result["geometry_frontage"]
        frontage_records.append(
            {
                "parcel_id": parcel.parcel_id,
                "parcel_key": parcel.parcel_key,
                "assessor_frontage": assessor,
                **result,
                "frontage_difference": estimate - assessor
                if np.isfinite(assessor)
                else np.nan,
                "frontage_source": source,
            }
        )
        frontage_geometries.append(geometry)
    frontage = gpd.GeoDataFrame(
        frontage_records, geometry=frontage_geometries, crs=parcels.crs
    )
    frontage.to_file(OUTPUT / "geometry_frontage_sample.gpkg", driver="GPKG")
    frontage.drop(columns="geometry").to_csv(
        OUTPUT / "geometry_frontage_comparison.csv", index=False
    )

    comparable = frontage.dropna(
        subset=["assessor_frontage", "geometry_frontage"]
    ).copy()
    comparable = comparable[
        comparable["assessor_frontage"].gt(0)
        & comparable["geometry_frontage"].gt(0)
    ]
    absolute_error = comparable["frontage_difference"].abs()
    summary = {
        "parcel_records_loaded": int(len(parcels)),
        "active_buildings_loaded": int(len(buildings)),
        "buildings_joined_to_linked_parcel": int(
            buildings["linked_parcel_key"].isin(set(parcels.parcel_key)).sum()
        ),
        "buildings_with_multiple_material_parcel_overlaps": int(
            (overlaps.groupby("building_id").size() >= 2).sum()
        ),
        "candidate_sites": int(sites["candidate_site_id"].nunique())
        if not sites.empty
        else 0,
        "frontages_compared": int(len(comparable)),
        "frontage_median_absolute_error_ft": float(absolute_error.median())
        if len(comparable)
        else None,
        "frontage_within_2_ft_share": float((absolute_error <= 2).mean())
        if len(comparable)
        else None,
        "frontage_within_5_ft_share": float((absolute_error <= 5).mean())
        if len(comparable)
        else None,
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument(
        "--layer",
        action="append",
        choices=sorted(LAYERS),
        help="Fetch only this layer; repeat for more than one (default: all)",
    )
    fetch_parser.add_argument(
        "--discard-pages",
        action="store_true",
        help="Delete resumable page files after successful consolidation",
    )
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--sample", type=int)
    args = parser.parse_args()
    if args.command == "fetch":
        for layer in args.layer or LAYERS:
            fetch_layer(layer, discard_pages=args.discard_pages)
    else:
        analyze(args.sample)


if __name__ == "__main__":
    main()
