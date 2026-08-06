#!/usr/bin/env python3
"""Build a standalone, print-ready HTML small-multiple map from isochrone GeoJSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
DEFAULT_BOUNDARY = (
    HERE.parents[2]
    / "pipelines/housingDataAnalysis/resources/data"
    / "Detroit_City_Council_Districts_2026.geojson"
)


def render(data_path, spec_path, output_path, boundary_path=None):
    isochrones = gpd.read_file(data_path).to_crs("EPSG:4326")
    spec = json.loads(spec_path.read_text())
    expected = set(spec["threshold_minutes"])
    errors = []
    for mode in spec["modes"]:
        present = set(
            isochrones.loc[isochrones["mode"] == mode, "minutes"].astype(int)
        )
        if present != expected:
            errors.append(
                f"{mode}: expected {sorted(expected)}, found {sorted(present)}"
            )
    if errors:
        raise SystemExit(
            "Isochrone data does not match spec.json. Rerun the routing provider:\n  "
            + "\n  ".join(errors)
        )
    boundary_geojson = None
    if boundary_path:
        districts = gpd.read_file(boundary_path).to_crs("EPSG:4326")
        city = unary_union(districts.geometry)
        isochrones.geometry = isochrones.geometry.intersection(city)
        isochrones = isochrones[~isochrones.geometry.is_empty]
        boundary_geojson = mapping(city)
    roads_path = output_path.with_name("road_context.geojson")
    roads = json.loads(roads_path.read_text()) if roads_path.exists() else None
    data = json.loads(isochrones.to_json())
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    specification = json.dumps(spec, separators=(",", ":")).replace("</", "<\\/")
    boundary = json.dumps(boundary_geojson, separators=(",", ":")).replace("</", "<\\/")
    road_payload = json.dumps(roads, separators=(",", ":")).replace("</", "<\\/")
    template = (HERE / "template.html").read_text()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        template.replace("__GEOJSON__", payload)
        .replace("__SPEC__", specification)
        .replace("__BOUNDARY__", boundary)
        .replace("__ROADS__", road_payload)
    )
    display_path = output_path.with_name("display_isochrones.geojson")
    isochrones.to_file(display_path, driver="GeoJSON")
    print(f"Wrote {output_path}")
    print(f"Wrote {display_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("--spec", type=Path, default=HERE / "spec.json")
    parser.add_argument("--output", type=Path, default=HERE / "output" / "map.html")
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    args = parser.parse_args()
    render(args.data, args.spec, args.output, args.boundary)


if __name__ == "__main__":
    main()
