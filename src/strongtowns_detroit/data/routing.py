"""Deterministic routing-anchor, frontage, evidence, and review contracts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from uuid import UUID, uuid5
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import nearest_points


ANCHOR_NAMESPACE_V1 = UUID("b8d1454b-2476-5f8d-a845-d472815b7f51")
EVIDENCE_NAMESPACE_V1 = UUID("82f4de90-718b-5f49-866d-d05f1c485063")
PROJECTED_CRS = "EPSG:2898"


def canonical_identity(values: Iterable[object]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def parcel_key_v1(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    key = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return key or None


def stable_anchor_id(parcel_key: str, street_key: str, method: str) -> str:
    return str(uuid5(ANCHOR_NAMESPACE_V1, canonical_identity([parcel_key, street_key, method])))


def stable_evidence_id(anchor_id: str, address_id: str) -> str:
    return str(uuid5(EVIDENCE_NAMESPACE_V1, canonical_identity([anchor_id, address_id])))


def _segments(geometry) -> list[LineString]:
    polygon = max(geometry.geoms, key=lambda part: part.area) if geometry.geom_type == "MultiPolygon" else geometry
    if polygon.geom_type != "Polygon":
        return []
    coordinates = list(polygon.exterior.coords)
    return [
        LineString((start, end))
        for start, end in zip(coordinates, coordinates[1:])
        if start != end
    ]


def _angle(line: LineString) -> float:
    start, end = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180


def _local_segment(street, point) -> LineString:
    components = street.geoms if street.geom_type == "MultiLineString" else [street]
    candidates = []
    for component in components:
        coordinates = list(component.coords)
        candidates.extend(
            LineString((start, end))
            for start, end in zip(coordinates, coordinates[1:])
            if start != end
        )
    return min(candidates, key=lambda item: item.distance(point))


def frontage_for(parcel, street) -> dict[str, object]:
    rows = []
    for edge in _segments(parcel):
        midpoint = edge.interpolate(0.5, normalized=True)
        local = _local_segment(street, midpoint)
        difference = abs(_angle(edge) - _angle(local))
        difference = min(difference, 180 - difference)
        rows.append((edge, edge.distance(street), difference))
    if not rows:
        raise ValueError("parcel has no evaluable exterior segment")
    parallel = [row for row in rows if row[2] <= 35]
    edge, distance, difference = min(
        parallel or rows, key=lambda row: (row[1], -row[0].length)
    )
    confidence = (
        "low" if not parallel
        else "high" if distance <= 80 and difference <= 15
        else "medium"
    )
    return {
        "geometry": edge,
        "frontage_length_ft": edge.length,
        "street_distance_ft": distance,
        "angle_difference": difference,
        "confidence": confidence,
    }


def _nearest_street_index(streets: gpd.GeoDataFrame, geometry) -> int:
    result = streets.sindex.nearest(geometry, return_all=False)
    if len(result) < 2 or not len(result[1]):
        raise ValueError("no nearest street")
    return int(result[1][0])


def build_routing_anchor_tables(
    parcels: gpd.GeoDataFrame,
    addresses: gpd.GeoDataFrame,
    streets: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame | None = None,
) -> dict[str, pd.DataFrame | gpd.GeoDataFrame]:
    parcels = parcels.to_crs(PROJECTED_CRS).copy()
    addresses = addresses.to_crs(PROJECTED_CRS).copy()
    streets = streets.to_crs(PROJECTED_CRS).copy()
    buildings = buildings.to_crs(PROJECTED_CRS).copy() if buildings is not None else None
    parcels["parcel_key"] = parcels["parcel_id"].map(parcel_key_v1)
    addresses["parcel_key"] = addresses["parcel_id"].map(parcel_key_v1)
    streets["street_key"] = streets["street_id"].astype("string")

    street_lookup = {
        str(row.street_id): (index, row.geometry)
        for index, row in streets.iterrows()
    }
    address_groups = {
        key: group for key, group in addresses.dropna(subset=["parcel_key"]).groupby("parcel_key", sort=True)
    }
    building_counts: dict[str, int] | None = None
    if buildings is not None:
        buildings["parcel_key"] = buildings["parcel_id"].map(parcel_key_v1)
        if "status" in buildings:
            buildings = buildings[
                buildings["status"].astype("string").fillna("").str.lower().isin({"active", "current"})
            ]
        building_counts = buildings.dropna(subset=["parcel_key"]).groupby("parcel_key").size().to_dict()

    anchors, anchor_geometry = [], []
    frontages, frontage_geometry = [], []
    evidence = []
    dispositions = []
    blocked = []
    for _, parcel in parcels.sort_values("parcel_key", kind="stable").iterrows():
        parcel_key = parcel.parcel_key
        if not parcel_key or parcel.geometry is None or parcel.geometry.is_empty:
            blocked.append({"parcel_id": str(parcel.parcel_id), "reason": "invalid_parcel"})
            continue
        group = address_groups.get(parcel_key)
        linked: dict[str, list[pd.Series]] = {}
        if group is not None and "street_id" in group:
            for _, address in group.sort_values("address_id", kind="stable").iterrows():
                if pd.isna(address.street_id):
                    continue
                street_key = str(int(address.street_id)) if isinstance(address.street_id, float) and address.street_id.is_integer() else str(address.street_id)
                if street_key in street_lookup:
                    linked.setdefault(street_key, []).append(address)
        candidates = [(key, rows, "linked_address") for key, rows in sorted(linked.items())]
        if not candidates:
            try:
                street_index = _nearest_street_index(streets, parcel.geometry)
                street_key = str(streets.iloc[street_index].street_key)
                candidates = [(street_key, [], "nearest_street_fallback")]
            except ValueError:
                blocked.append({"parcel_id": str(parcel.parcel_id), "reason": "no_usable_street"})
                continue
        for street_key, address_rows, method in candidates:
            street = street_lookup[street_key][1]
            result = frontage_for(parcel.geometry, street)
            anchor_point = nearest_points(parcel.geometry.boundary, street)[0]
            anchor_id = stable_anchor_id(parcel_key, street_key, method)
            boundary_distance = anchor_point.distance(parcel.geometry.boundary)
            review_status = (
                "required"
                if method == "nearest_street_fallback"
                or result["confidence"] in {"low", "not_evaluated"}
                or result["street_distance_ft"] > 80
                else "not_required"
            )
            anchors.append({
                "anchor_id": anchor_id,
                "parcel_id": str(parcel.parcel_id),
                "parcel_key": parcel_key,
                "street_key": street_key,
                "method": method,
                "confidence": result["confidence"],
                "review_status": review_status,
                "street_distance_ft": float(result["street_distance_ft"]),
                "parcel_boundary_distance_ft": float(boundary_distance),
            })
            anchor_geometry.append(anchor_point)
            frontages.append({
                "anchor_id": anchor_id,
                "frontage_length_ft": float(result["frontage_length_ft"]),
                "street_distance_ft": float(result["street_distance_ft"]),
                "angle_difference": float(result["angle_difference"]),
            })
            frontage_geometry.append(result["geometry"])
            dispositions.append({
                "anchor_id": anchor_id,
                "review_status": review_status,
                "reviewer": None,
                "review_time": None,
                "evidence_uri": None,
                "notes": None,
                "parent_disposition_snapshot": None,
            })
            for address in address_rows:
                address_id = str(address.address_id)
                evidence.append({
                    "evidence_id": stable_evidence_id(anchor_id, address_id),
                    "anchor_id": anchor_id,
                    "address_id": address_id,
                    "address_objectid": int(address.objectid) if "objectid" in address and pd.notna(address.objectid) else None,
                    "linked_current_building_count": (
                        building_counts.get(parcel_key, 0) if building_counts is not None else None
                    ),
                })

    anchors_frame = gpd.GeoDataFrame(anchors, geometry=anchor_geometry, crs=PROJECTED_CRS).to_crs("EPSG:4326")
    frontages_frame = gpd.GeoDataFrame(frontages, geometry=frontage_geometry, crs=PROJECTED_CRS).to_crs("EPSG:4326")
    evidence_frame = pd.DataFrame(evidence)
    dispositions_frame = pd.DataFrame(dispositions)
    blocked_frame = pd.DataFrame(blocked, columns=["parcel_id", "reason"])

    if len(anchors_frame) and anchors_frame.anchor_id.duplicated().any():
        raise ValueError("duplicate anchor UUID")
    if len(frontages_frame) != len(anchors_frame) or set(frontages_frame.anchor_id) != set(anchors_frame.anchor_id):
        raise ValueError("every anchor must have exactly one frontage")
    if len(anchors_frame) and (anchors_frame.parcel_boundary_distance_ft > 0.01).any():
        raise ValueError("anchor exceeds parcel-boundary tolerance")
    if len(frontages_frame) and not frontages_frame.angle_difference.between(0, 90).all():
        raise ValueError("frontage angle outside [0, 90]")
    linked_ids = set(anchors_frame.loc[anchors_frame.method == "linked_address", "anchor_id"])
    fallback_ids = set(anchors_frame.loc[anchors_frame.method == "nearest_street_fallback", "anchor_id"])
    evidence_anchor_ids = set(evidence_frame.anchor_id) if len(evidence_frame) else set()
    if not linked_ids <= evidence_anchor_ids or fallback_ids & evidence_anchor_ids:
        raise ValueError("anchor evidence does not match anchor method")
    return {
        "anchors": anchors_frame,
        "frontages": frontages_frame,
        "evidence": evidence_frame,
        "dispositions": dispositions_frame,
        "blocked": blocked_frame,
    }


def export_review_packet(
    anchors: gpd.GeoDataFrame,
    dispositions: pd.DataFrame,
    *,
    parent_manifest_sha256: str,
    directory: Path,
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    review = anchors.merge(dispositions, on=["anchor_id", "review_status"], how="left")
    review["decision"] = ""
    review["reviewer"] = review.get("reviewer", "")
    review["review_time"] = review.get("review_time", "")
    review["evidence_uri"] = review.get("evidence_uri", "")
    review["notes"] = review.get("notes", "")
    review["parent_disposition_snapshot"] = parent_manifest_sha256
    csv_path = directory / "routing-anchor-review.csv"
    gpkg_path = directory / "routing-anchor-review.gpkg"
    review.drop(columns="geometry").to_csv(csv_path, index=False)
    review.to_file(gpkg_path, driver="GPKG")
    return csv_path, gpkg_path


def import_review_decisions(
    decisions: pd.DataFrame,
    current: pd.DataFrame,
    *,
    expected_parent_manifest_sha256: str,
) -> pd.DataFrame:
    required = {
        "anchor_id", "decision", "reviewer", "review_time", "evidence_uri",
        "notes", "parent_disposition_snapshot",
    }
    missing = required - set(decisions.columns)
    if missing:
        raise ValueError(f"missing review columns: {sorted(missing)}")
    decisions = decisions[decisions.decision.astype("string").str.len().fillna(0) > 0].copy()
    if decisions.anchor_id.duplicated().any():
        raise ValueError("duplicate anchor decision")
    if not decisions.parent_disposition_snapshot.eq(expected_parent_manifest_sha256).all():
        raise ValueError("stale parent disposition snapshot")
    if not decisions.decision.isin({"approved", "rejected"}).all():
        raise ValueError("review decision must be approved or rejected")
    if decisions.reviewer.astype("string").str.strip().eq("").any():
        raise ValueError("reviewer is required")
    times = pd.to_datetime(decisions.review_time, errors="raise", utc=True)
    if not set(decisions.anchor_id) <= set(current.anchor_id):
        raise ValueError("review contains unknown anchor ID")
    updated = current.copy().set_index("anchor_id")
    for row, review_time in zip(decisions.itertuples(index=False), times):
        updated.loc[row.anchor_id, "review_status"] = row.decision
        updated.loc[row.anchor_id, "reviewer"] = row.reviewer
        updated.loc[row.anchor_id, "review_time"] = review_time.isoformat()
        updated.loc[row.anchor_id, "evidence_uri"] = row.evidence_uri
        updated.loc[row.anchor_id, "notes"] = row.notes
        updated.loc[row.anchor_id, "parent_disposition_snapshot"] = expected_parent_manifest_sha256
    return updated.reset_index()
