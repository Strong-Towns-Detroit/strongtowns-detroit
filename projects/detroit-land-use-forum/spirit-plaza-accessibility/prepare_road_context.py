#!/usr/bin/env python3
"""Extract a lightweight, city-clipped road hierarchy for the HTML maps."""

from __future__ import annotations

import argparse
import ast
import math
import re
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
DEFAULT_GRAPH = REPO_ROOT / "cache/Detroit__Michigan__USA_1bcfe6a4_drive.graphml"
DEFAULT_BOUNDARY = (
    REPO_ROOT
    / "pipelines/housingDataAnalysis/street_simplification/output"
    / "detroit_boundary.gpkg"
)

CLASSES = {
    "major": {
        "motorway", "motorway_link", "trunk", "trunk_link",
        "primary", "primary_link",
    },
    "arterial": {"secondary", "secondary_link", "tertiary", "tertiary_link"},
    "local": {"residential", "unclassified", "living_street"},
}

DEFAULT_WIDTH_M = {
    "motorway": 11.0,
    "motorway_link": 6.5,
    "trunk": 10.0,
    "trunk_link": 6.5,
    "primary": 9.0,
    "primary_link": 6.0,
    "secondary": 8.0,
    "secondary_link": 5.5,
    "tertiary": 7.0,
    "tertiary_link": 5.0,
    "residential": 6.5,
    "unclassified": 6.5,
    "living_street": 5.0,
}


def highway_values(value):
    return set(value if isinstance(value, list) else [value])


def road_class(value):
    values = highway_values(value)
    for label, accepted in CLASSES.items():
        if values & accepted:
            return label
    return None


def values(value):
    """Normalize GraphML scalars and serialized lists."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, str) and value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            return list(parsed) if isinstance(parsed, (list, tuple, set)) else [parsed]
        except (SyntaxError, ValueError):
            pass
    return [value]


def first_highway(value):
    candidates = [str(item) for item in values(value)]
    for hierarchy in CLASSES.values():
        for candidate in candidates:
            if candidate in hierarchy:
                return candidate
    return candidates[0] if candidates else "unclassified"


def corridor_value(value):
    candidates = [str(item).strip() for item in values(value) if str(item).strip()]
    return "|".join(sorted(candidates))


def parse_width_m(value):
    parsed = []
    for item in values(value):
        text = str(item).strip().lower()
        match = re.search(r"\d+(?:\.\d+)?", text)
        if not match:
            continue
        width = float(match.group())
        if "ft" in text or "'" in text:
            width *= 0.3048
        if 2.0 <= width <= 40.0:
            parsed.append(width)
    return max(parsed) if parsed else None


def parse_lanes(value):
    parsed = []
    for item in values(value):
        match = re.search(r"\d+(?:\.\d+)?", str(item))
        if match:
            lanes = float(match.group())
            if 0.5 <= lanes <= 12:
                parsed.append(lanes)
    return max(parsed) if parsed else None


def road_width(row):
    """Return width in meters plus the OSM evidence used."""
    explicit = parse_width_m(row.get("width"))
    if explicit is not None:
        return explicit, "width"
    lanes = parse_lanes(row.get("lanes"))
    highway = first_highway(row.get("highway"))
    if lanes is not None:
        # OSM lanes describe the carriageway represented by this centerline.
        return max(3.5, lanes * 3.2), "lanes"
    return DEFAULT_WIDTH_M.get(highway, 6.5), "class"


def linear_only(geometry):
    """Discard point fragments produced when roads touch the clip boundary."""
    if geometry.geom_type in {"LineString", "MultiLineString"}:
        return geometry
    parts = []
    for part in getattr(geometry, "geoms", ()):
        if part.geom_type == "LineString":
            parts.append(part)
        elif part.geom_type == "MultiLineString":
            parts.extend(part.geoms)
    return unary_union(parts) if parts else None


def run(graph_path, boundary_path, output_path, simplify_m=8):
    graph = ox.load_graphml(graph_path)
    edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()
    edges["road_class"] = edges["highway"].map(road_class)
    edges = edges[edges["road_class"].notna()]
    width_values = edges.apply(road_width, axis=1)
    edges["road_width_m"] = [item[0] for item in width_values]
    edges["width_source"] = [item[1] for item in width_values]
    edges["corridor"] = [
        corridor_value(row.get("ref"))
        or corridor_value(row.get("name"))
        or corridor_value(row.get("osmid"))
        for _, row in edges.iterrows()
    ]
    # Lane tagging frequently appears on only some constituent OSM ways.
    # Propagate a corridor's median tagged lane width across its unmeasured
    # segments so the rendered carriageway does not pulse at every graph edge.
    lane_widths = (
        edges.loc[edges["width_source"] == "lanes"]
        .groupby(["corridor", "road_class"])["road_width_m"]
        .median()
    )
    for index in edges.index[edges["width_source"] == "class"]:
        key = (edges.at[index, "corridor"], edges.at[index, "road_class"])
        if key in lane_widths:
            edges.at[index, "road_width_m"] = lane_widths[key]
            edges.at[index, "width_source"] = "corridor_lanes"
    # Two-meter buckets retain meaningful OSM variation without exporting
    # hundreds of thousands of separate line features.
    edges["width_bucket_m"] = (
        (edges["road_width_m"] / 2).round() * 2
    ).clip(lower=4, upper=24)

    boundary = gpd.read_file(boundary_path).to_crs(edges.crs)
    city = unary_union(boundary.geometry)
    edges.geometry = edges.geometry.intersection(city)
    edges.geometry = edges.geometry.map(linear_only)
    edges = edges[edges.geometry.notna() & ~edges.geometry.is_empty]
    # OSMnx drive graphs contain reciprocal directed edges for many two-way
    # streets. They are cartographically coincident; drawing both with
    # transparency makes some segments look darker than their neighbors.
    edges["_geometry_key"] = edges.geometry.map(
        lambda geometry: geometry.normalize().wkb_hex
    )
    edges = (
        edges.sort_values("road_width_m", ascending=False)
        .drop_duplicates("_geometry_key")
    )

    projected = edges.to_crs(edges.estimate_utm_crs())
    rows = []
    for (label, width, source), group in projected.groupby(
        ["road_class", "width_bucket_m", "width_source"]
    ):
        geometry = unary_union(group.geometry)
        geometry = geometry.simplify(simplify_m, preserve_topology=True)
        geometry = gpd.GeoSeries([geometry], crs=projected.crs).to_crs("EPSG:4326").iloc[0]
        rows.append({
            "road_class": label,
            "road_width_m": float(width),
            "width_source": source,
            "geometry": geometry,
        })
    output = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_file(output_path, driver="GeoJSON")
    print(f"Wrote {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--output", type=Path, default=HERE / "output/road_context.geojson")
    parser.add_argument("--simplify-m", type=float, default=8)
    args = parser.parse_args()
    run(args.graph, args.boundary, args.output, args.simplify_m)


if __name__ == "__main__":
    main()
