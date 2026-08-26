"""Fingerprintable OSM acquisition and source-faithful POI normalization."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .manifest import canonical_json


DEFAULT_POI_TAGS = {
    "amenity": True,
    "shop": True,
    "office": True,
    "tourism": True,
    "leisure": True,
}


def source_identity(index) -> tuple[str, str]:
    if isinstance(index, tuple) and len(index) >= 2:
        return str(index[0]), str(index[1])
    return "unknown", str(index)


def normalize_osm_features(
    frame: gpd.GeoDataFrame, *, return_rejected: bool = False
) -> gpd.GeoDataFrame | tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Preserve source tags and derive routing interpretations explicitly."""
    tag_columns = [column for column in DEFAULT_POI_TAGS if column in frame]
    rows, geometries, rejected = [], [], []
    for source_row, (index, row) in enumerate(frame.sort_index().iterrows()):
        if {"source_id", "osm_type", "osm_id", "tag_keys", "tag_values"} <= set(frame.columns):
            osm_type, osm_id = str(row.osm_type), str(row.osm_id)
            tags = list(zip(row.tag_keys, row.tag_values))
            source_id = str(row.source_id)
        else:
            osm_type, osm_id = source_identity(index)
            tags = [
                (column, str(row[column]))
                for column in tag_columns
                if pd.notna(row[column]) and str(row[column]).strip()
            ]
            source_id = f"osm:{osm_type}:{osm_id}"
        if not tags or row.geometry is None or row.geometry.is_empty:
            rejected.append({
                "source_row": source_row,
                "source_id": source_id,
                "reason": "missing_tags" if not tags else "missing_geometry",
            })
            continue
        if row.geometry.geom_type == "Point":
            routing_geometry = row.geometry
            method = "source_point"
        else:
            routing_geometry = row.geometry.representative_point()
            method = "representative_point"
        rows.append({
            "source_id": source_id,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "tag_keys": [key for key, _ in tags],
            "tag_values": [value for _, value in tags],
            "primary_category": tags[0][0],
            "routing_point_method": method,
            "source_geometry_type": row.geometry.geom_type,
        })
        geometries.append(routing_geometry)
    result = gpd.GeoDataFrame(rows, geometry=geometries, crs=frame.crs)
    if result.source_id.duplicated().any():
        raise ValueError("duplicate OSM source identity")
    result = result.to_crs("EPSG:4326")
    rejected_frame = pd.DataFrame(
        rejected, columns=["source_row", "source_id", "reason"]
    )
    return (result, rejected_frame) if return_rejected else result


def prepare_osm_source(
    frame: gpd.GeoDataFrame, *, return_rejected: bool = False
) -> gpd.GeoDataFrame | tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Retain immutable OSM identity, all selected tags, and original geometry."""
    tag_columns = [column for column in DEFAULT_POI_TAGS if column in frame]
    rows, geometries, rejected = [], [], []
    for source_row, (index, row) in enumerate(frame.sort_index().iterrows()):
        osm_type, osm_id = source_identity(index)
        tags = [
            (column, str(row[column]))
            for column in tag_columns
            if pd.notna(row[column]) and str(row[column]).strip()
        ]
        source_id = f"osm:{osm_type}:{osm_id}"
        if not tags or row.geometry is None or row.geometry.is_empty:
            rejected.append({
                "source_row": source_row,
                "source_id": source_id,
                "reason": "missing_tags" if not tags else "missing_geometry",
            })
            continue
        rows.append({
            "source_id": source_id,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "tag_keys": [key for key, _ in tags],
            "tag_values": [value for _, value in tags],
        })
        geometries.append(row.geometry)
    result = gpd.GeoDataFrame(rows, geometry=geometries, crs=frame.crs)
    if result.source_id.duplicated().any():
        raise ValueError("duplicate OSM source identity")
    result = result.to_crs("EPSG:4326")
    rejected_frame = pd.DataFrame(
        rejected, columns=["source_row", "source_id", "reason"]
    )
    return (result, rejected_frame) if return_rejected else result


def collect_osm_pois(
    output: Path,
    *,
    place: str = "Detroit, Michigan, USA",
    tags: dict | None = None,
    cache_root: Path,
) -> dict:
    import osmnx as ox

    started_at = datetime.now(timezone.utc).isoformat()
    tags = tags or DEFAULT_POI_TAGS
    query = {"place": place, "tags": tags}
    fingerprint = hashlib.sha256(canonical_json(query)).hexdigest()
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(cache_root / fingerprint)
    boundary = ox.geocode_to_gdf(place).to_crs("EPSG:4326")
    boundary_hash = hashlib.sha256(boundary.geometry.iloc[0].wkb).hexdigest()
    features = ox.features_from_polygon(boundary.geometry.iloc[0], tags)
    source, rejected = prepare_osm_source(features, return_rejected=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    source.to_parquet(output, index=False)
    rejected.to_parquet(output.parent / "rejects.parquet", index=False)
    return {
        "provider": "OpenStreetMap",
        "query": query,
        "endpoint": ox.settings.overpass_url,
        "osmnx_version": ox.__version__,
        "boundary_sha256": boundary_hash,
        "cache_fingerprint": fingerprint,
        "input": len(features),
        "accepted": len(source),
        "rejected": len(rejected),
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "transaction_quality": "best_effort",
    }
