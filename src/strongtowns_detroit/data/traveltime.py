"""Manifest-bound TravelTime request and result ledgers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

from .manifest import canonical_json


REQUEST_NAMESPACE_V1 = UUID("a8c25fae-dc41-5b85-9600-754ecb20f90c")
API_URL = "https://api.traveltimeapp.com/v4/time-map"
ALLOWED_DIRECTIONS = {"arrival", "departure"}
ALLOWED_MODES = {"walking", "cycling", "driving", "public_transport"}


def request_id(
    anchor_id: str,
    direction: str,
    mode: str,
    horizon_seconds: int,
    reference_time: datetime,
    provider: str = "traveltime",
    contract_version: str = "1.0.0",
) -> str:
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("reference time must be timezone-aware")
    identity = [
        anchor_id, direction, mode, horizon_seconds,
        reference_time.astimezone(timezone.utc).isoformat(), provider, contract_version,
    ]
    return str(uuid5(REQUEST_NAMESPACE_V1, json.dumps(identity, separators=(",", ":"))))


def build_request_ledger(
    anchors: gpd.GeoDataFrame,
    *,
    directions: tuple[str, ...],
    mode: str,
    horizon_seconds: int,
    reference_time: datetime,
    include_required: bool = False,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    if not directions or set(directions) - ALLOWED_DIRECTIONS:
        raise ValueError("invalid or empty directions")
    if mode not in ALLOWED_MODES:
        raise ValueError(f"invalid mode: {mode}")
    if horizon_seconds <= 0:
        raise ValueError("horizon must be positive")
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("reference time must be timezone-aware")
    permitted = {"not_required", "approved"}
    if include_required:
        permitted.add("required")
    selected = anchors[anchors.review_status.isin(permitted)].copy()
    blocked = anchors[~anchors.review_status.isin(permitted)][
        ["parcel_id", "anchor_id", "review_status"]
    ].copy()
    rows, geometries = [], []
    for _, anchor in selected.sort_values("anchor_id", kind="stable").iterrows():
        for direction in sorted(directions):
            identifier = request_id(
                anchor.anchor_id, direction, mode, horizon_seconds, reference_time
            )
            rows.append({
                "request_id": identifier,
                "provider_search_id": f"s{len(rows):08d}",
                "anchor_id": anchor.anchor_id,
                "parcel_id": anchor.parcel_id,
                "direction": direction,
                "mode": mode,
                "horizon_seconds": horizon_seconds,
                "reference_time_utc": reference_time.astimezone(timezone.utc),
                "required_override": bool(
                    include_required and anchor.review_status == "required"
                ),
            })
            geometries.append(anchor.geometry)
    ledger = gpd.GeoDataFrame(rows, geometry=geometries, crs=anchors.crs)
    if ledger.request_id.duplicated().any() or ledger.provider_search_id.duplicated().any():
        raise ValueError("duplicate TravelTime request identity")
    return ledger, blocked.reset_index(drop=True)


def _search(row) -> tuple[str, dict]:
    point = row.geometry
    key = "departure_time" if row.direction == "departure" else "arrival_time"
    search = {
        "id": row.provider_search_id,
        "coords": {"lat": point.y, "lng": point.x},
        key: row.reference_time_utc.isoformat(),
        "travel_time": int(row.horizon_seconds),
        "transportation": {"type": row.mode},
        "no_holes": False,
        "remove_water_bodies": True,
    }
    return f"{row.direction}_searches", search


@dataclass(frozen=True)
class ProviderRun:
    results: gpd.GeoDataFrame
    errors: pd.DataFrame
    retries: int


class TravelTimeBatchError(ValueError):
    pass


def execute_request_ledger(
    ledger: gpd.GeoDataFrame,
    raw_directory: Path,
    *,
    app_id: str,
    api_key: str,
    session=None,
    max_attempts: int = 5,
) -> ProviderRun:
    """Execute and exactly reconcile every request, retaining raw evidence."""
    session = session or requests.Session()
    raw_directory.mkdir(parents=True, exist_ok=True)
    successes, geometries, errors = [], [], []
    retries = 0
    expected = set(ledger.request_id)
    seen: set[str] = set()
    for row in ledger.itertuples(index=False):
        payload_key, search = _search(row)
        response = None
        terminal_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = session.post(
                    API_URL,
                    headers={
                        "X-Application-Id": app_id,
                        "X-Api-Key": api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/geo+json",
                    },
                    json={payload_key: [search]},
                    timeout=120,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < max_attempts:
                        retries += 1
                        wait = min(float(response.headers.get("Retry-After", 0) or 0), 30)
                        time.sleep(wait or min(2 ** (attempt - 1), 8))
                        continue
                response.raise_for_status()
                break
            except requests.RequestException as error:
                terminal_error = error
                if attempt < max_attempts:
                    retries += 1
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                response = None
        raw_path = raw_directory / f"{row.request_id}.json"
        if response is None:
            error_record = {
                "request_id": row.request_id,
                "provider_search_id": row.provider_search_id,
                "error_type": "transport",
                "message": str(terminal_error),
            }
            raw_path.write_bytes(canonical_json({"error": error_record}))
            errors.append(error_record)
            seen.add(row.request_id)
            continue
        try:
            payload = response.json()
        except ValueError as error:
            payload = {"malformed_response": response.text}
            raw_path.write_bytes(canonical_json(payload))
            raise TravelTimeBatchError(
                f"malformed provider response for {row.request_id}"
            ) from error
        raw_path.write_bytes(canonical_json(payload))
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise TravelTimeBatchError(
                f"expected one feature for {row.request_id}, received "
                f"{len(features) if isinstance(features, list) else 'malformed'}"
            )
        feature = features[0]
        returned_id = (feature.get("properties") or {}).get("search_id")
        if returned_id != row.provider_search_id:
            raise TravelTimeBatchError(
                f"unexpected provider search ID for {row.request_id}: {returned_id}"
            )
        geometry = shape(feature.get("geometry"))
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise TravelTimeBatchError(f"invalid result geometry for {row.request_id}")
        if row.request_id in seen:
            raise TravelTimeBatchError(f"duplicate result for {row.request_id}")
        seen.add(row.request_id)
        successes.append({
            "request_id": row.request_id,
            "provider_search_id": row.provider_search_id,
            "anchor_id": row.anchor_id,
        })
        geometries.append(geometry)

    successful_ids = {row["request_id"] for row in successes}
    error_ids = {row["request_id"] for row in errors}
    if successful_ids & error_ids or expected != successful_ids | error_ids:
        raise TravelTimeBatchError("TravelTime request/result reconciliation failed")
    result_frame = gpd.GeoDataFrame(successes, geometry=geometries, crs="EPSG:4326")
    error_frame = pd.DataFrame(
        errors,
        columns=["request_id", "provider_search_id", "error_type", "message"],
    )
    if len(error_frame):
        raise TravelTimeBatchError(
            f"{len(error_frame)} terminal provider errors; result dataset cannot promote"
        )
    return ProviderRun(result_frame, error_frame, retries)
