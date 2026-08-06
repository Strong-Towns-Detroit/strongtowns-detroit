"""Geometry helpers for the Detroit Base Units research track.

These functions intentionally return evidence and confidence fields. They do
not pronounce a group of assessor parcels to be a legal zoning lot.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union


def normalize_parcel_id(value: object) -> str | None:
    """Normalize Detroit parcel identifiers for cross-dataset comparison."""
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return cleaned or None


def exterior_segments(geometry: Polygon) -> list[LineString]:
    """Return non-zero exterior ring segments from a polygon."""
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "MultiPolygon":
        polygon = max(geometry.geoms, key=lambda part: part.area)
    elif geometry.geom_type == "Polygon":
        polygon = geometry
    else:
        return []
    coordinates = list(polygon.exterior.coords)
    return [
        LineString([start, end])
        for start, end in zip(coordinates, coordinates[1:])
        if start != end
    ]


def _angle_degrees(line: LineString) -> float:
    start, end = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180


def _local_street_segment(street: LineString | MultiLineString, point) -> LineString:
    components: Iterable[LineString]
    components = street.geoms if street.geom_type == "MultiLineString" else [street]
    candidates: list[LineString] = []
    for component in components:
        coordinates = list(component.coords)
        candidates.extend(
            LineString([start, end])
            for start, end in zip(coordinates, coordinates[1:])
            if start != end
        )
    return min(candidates, key=lambda segment: segment.distance(point))


def estimate_street_facing_edge(
    parcel: Polygon,
    street: LineString | MultiLineString,
    *,
    parallel_tolerance_degrees: float = 35,
) -> dict[str, object]:
    """Select the parcel edge most plausibly facing a supplied street.

    Ranking favors parallel edges, then distance to the street. If no edge is
    sufficiently parallel, the nearest edge is returned at low confidence.
    Length units are inherited from the input CRS; callers should use a local
    projected CRS such as EPSG:2898 (US survey feet).
    """
    segments = exterior_segments(parcel)
    if not segments or street is None or street.is_empty:
        return {
            "geometry_frontage": np.nan,
            "edge_to_street_distance": np.nan,
            "angle_difference": np.nan,
            "frontage_confidence": "not_evaluated",
            "geometry": None,
        }

    rows = []
    for edge in segments:
        midpoint = edge.interpolate(0.5, normalized=True)
        local_street = _local_street_segment(street, midpoint)
        angle_difference = abs(_angle_degrees(edge) - _angle_degrees(local_street))
        angle_difference = min(angle_difference, 180 - angle_difference)
        rows.append(
            {
                "edge": edge,
                "length": edge.length,
                "distance": edge.distance(street),
                "angle_difference": angle_difference,
            }
        )

    parallel = [
        row for row in rows if row["angle_difference"] <= parallel_tolerance_degrees
    ]
    chosen = min(parallel or rows, key=lambda row: (row["distance"], -row["length"]))
    if not parallel:
        confidence = "low"
    elif chosen["distance"] <= 80 and chosen["angle_difference"] <= 15:
        confidence = "high"
    else:
        confidence = "medium"
    return {
        "geometry_frontage": chosen["length"],
        "edge_to_street_distance": chosen["distance"],
        "angle_difference": chosen["angle_difference"],
        "frontage_confidence": confidence,
        "geometry": chosen["edge"],
    }


def building_parcel_overlaps(
    buildings: gpd.GeoDataFrame,
    parcels: gpd.GeoDataFrame,
    *,
    building_id_col: str = "building_id",
    parcel_id_col: str = "parcel_id",
    minimum_overlap_area: float = 10.0,
    minimum_building_share: float = 0.02,
) -> pd.DataFrame:
    """Measure material building-footprint overlap with assessor parcels."""
    if buildings.crs != parcels.crs:
        parcels = parcels.to_crs(buildings.crs)
    left = buildings[[building_id_col, "geometry"]].copy()
    left["_building_area"] = left.geometry.area
    right = parcels[[parcel_id_col, "geometry"]].copy()
    joined = gpd.sjoin(left, right, predicate="intersects", how="inner")
    parcel_geometries = right.geometry
    joined["overlap_area"] = [
        geometry.intersection(parcel_geometries.loc[index]).area
        for geometry, index in zip(joined.geometry, joined.index_right)
    ]
    joined["building_share"] = joined["overlap_area"] / joined["_building_area"]
    material = joined[
        (joined["overlap_area"] >= minimum_overlap_area)
        & (joined["building_share"] >= minimum_building_share)
    ].copy()
    return material[
        [building_id_col, parcel_id_col, "overlap_area", "building_share"]
    ].reset_index(drop=True)


def infer_building_linked_sites(
    overlaps: pd.DataFrame,
    *,
    building_id_col: str = "building_id",
    parcel_id_col: str = "parcel_id",
) -> pd.DataFrame:
    """Create evidence-based parcel groups connected by building footprints."""
    adjacency: dict[str, set[str]] = {}
    evidence: dict[tuple[str, str], set[object]] = {}
    for building_id, group in overlaps.groupby(building_id_col):
        parcel_ids = sorted(set(group[parcel_id_col].dropna().astype(str)))
        for parcel_id in parcel_ids:
            adjacency.setdefault(parcel_id, set())
        for left_index, left in enumerate(parcel_ids):
            for right in parcel_ids[left_index + 1 :]:
                adjacency[left].add(right)
                adjacency[right].add(left)
                evidence.setdefault(tuple(sorted((left, right))), set()).add(building_id)

    records = []
    visited: set[str] = set()
    site_number = 0
    for start in sorted(adjacency):
        if start in visited:
            continue
        stack = [start]
        component: list[str] = []
        while stack:
            parcel_id = stack.pop()
            if parcel_id in visited:
                continue
            visited.add(parcel_id)
            component.append(parcel_id)
            stack.extend(adjacency[parcel_id] - visited)
        if len(component) < 2:
            continue
        site_number += 1
        linked_buildings = set()
        for pair, building_ids in evidence.items():
            if pair[0] in component and pair[1] in component:
                linked_buildings.update(building_ids)
        for parcel_id in component:
            records.append(
                {
                    "candidate_site_id": f"BLDG-{site_number:06d}",
                    parcel_id_col: parcel_id,
                    "parcel_count": len(component),
                    "building_count": len(linked_buildings),
                    "evidence_tier": "building_footprint_overlap",
                }
            )
    return pd.DataFrame.from_records(records)

