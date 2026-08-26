"""Consistent, fingerprinted ArcGIS FeatureServer acquisition."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .manifest import canonical_json


def _request_json(session, url: str, *, params=None, data=None, timeout=120) -> dict[str, Any]:
    response = session.request(
        "POST" if data is not None else "GET", url,
        params=params, data=data, timeout=timeout,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        raise ValueError(f"ArcGIS returned non-JSON content type: {content_type}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("ArcGIS response is not a JSON object")
    if "error" in payload:
        raise ValueError(f"ArcGIS error: {payload['error']}")
    return payload


def layer_fingerprint(session, layer_url: str) -> dict[str, Any]:
    metadata = _request_json(session, layer_url, params={"f": "json"})
    ids_payload = _request_json(
        session, f"{layer_url}/query",
        data={"where": "1=1", "returnIdsOnly": "true", "f": "json"},
    )
    ids = sorted(ids_payload.get("objectIds") or [])
    fields = [
        {key: field.get(key) for key in ("name", "type", "length", "nullable")}
        for field in metadata.get("fields", [])
    ]
    schema_hash = hashlib.sha256(canonical_json(fields)).hexdigest()
    ids_hash = hashlib.sha256(canonical_json(ids)).hexdigest()
    return {
        "layer_url": layer_url,
        "object_id_field": metadata.get("objectIdField"),
        "geometry_type": metadata.get("geometryType"),
        "spatial_reference": metadata.get("extent", {}).get("spatialReference"),
        "last_edit_date": metadata.get("editingInfo", {}).get("lastEditDate"),
        "schema_hash": schema_hash,
        "object_id_count": len(ids),
        "object_ids_sha256": ids_hash,
        "object_ids": ids,
    }


def fingerprint_id(fingerprint: dict[str, Any]) -> str:
    stable = {key: value for key, value in fingerprint.items() if key != "object_ids"}
    return hashlib.sha256(canonical_json(stable)).hexdigest()


@dataclass(frozen=True)
class ArcGISCollection:
    output: Path
    before: dict[str, Any]
    after: dict[str, Any]
    feature_count: int
    cache_fingerprint: str
    started_at: str
    completed_at: str


def collect_layer(
    layer_url: str,
    output: Path,
    *,
    session=None,
    cache_root: Path | None = None,
    page_size: int = 1000,
    out_fields: str = "*",
    out_sr: int = 4326,
) -> ArcGISCollection:
    """Collect a layer only if its complete source fingerprint stays stable."""
    if out_sr != 4326:
        raise ValueError("contract-v1 ArcGIS snapshots require out_sr=4326")
    started_at = datetime.now(timezone.utc).isoformat()
    session = session or requests.Session()
    before = layer_fingerprint(session, layer_url)
    identity = hashlib.sha256(canonical_json({
        "source_fingerprint": fingerprint_id(before),
        "page_size": page_size,
        "out_fields": out_fields,
        "out_sr": out_sr,
    })).hexdigest()
    cache = (cache_root or output.parent / ".pages") / identity
    cache.mkdir(parents=True, exist_ok=True)
    object_id_field = before["object_id_field"]
    if not object_id_field:
        raise ValueError("ArcGIS layer does not declare an object-ID field")
    ids = before.pop("object_ids")
    collected: dict[Any, dict[str, Any]] = {}

    for page_number, start in enumerate(range(0, len(ids), page_size)):
        requested = ids[start : start + page_size]
        page_path = cache / f"{page_number:09d}.json"
        if page_path.is_file():
            payload = json.loads(page_path.read_text())
        else:
            payload = _request_json(
                session, f"{layer_url}/query",
                data={
                    "objectIds": ",".join(map(str, requested)),
                    "outFields": out_fields,
                    "returnGeometry": "true",
                    "outSR": str(out_sr),
                    "f": "geojson",
                },
            )
            temporary = page_path.with_suffix(".tmp")
            temporary.write_bytes(canonical_json(payload))
            temporary.replace(page_path)
        features = payload.get("features")
        if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise ValueError("ArcGIS page is not a GeoJSON feature collection")
        returned = []
        for feature in features:
            if feature.get("type") != "Feature" or not isinstance(feature.get("properties"), dict):
                raise ValueError("ArcGIS page contains a malformed GeoJSON feature")
            geometry = feature.get("geometry")
            if geometry is not None and (
                not isinstance(geometry, dict)
                or not isinstance(geometry.get("type"), str)
                or "coordinates" not in geometry
            ):
                raise ValueError("ArcGIS page contains malformed GeoJSON geometry")
            properties = feature.get("properties") or {}
            matches = [
                value for key, value in properties.items()
                if key.lower() == object_id_field.lower()
            ]
            if len(matches) != 1:
                raise ValueError(f"missing object ID {object_id_field} in ArcGIS feature")
            object_id = matches[0]
            if object_id in collected:
                raise ValueError(f"duplicate ArcGIS object ID: {object_id}")
            collected[object_id] = feature
            returned.append(object_id)
        if set(returned) != set(requested):
            raise ValueError(
                f"ArcGIS returned IDs different from requested page {page_number}"
            )
        time.sleep(0.01)

    after = layer_fingerprint(session, layer_url)
    after_ids = after.pop("object_ids")
    if before != after or ids != after_ids:
        raise ValueError("ArcGIS source changed during collection")
    if len(collected) != before["object_id_count"]:
        raise ValueError("ArcGIS server and collected feature counts differ")
    geojson = {
        "type": "FeatureCollection",
        "features": [collected[object_id] for object_id in ids],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(canonical_json(geojson))
    temporary.replace(output)
    return ArcGISCollection(
        output, before, after, len(collected), identity, started_at,
        datetime.now(timezone.utc).isoformat(),
    )
