#!/usr/bin/env python3
"""Fetch and aggregate TravelTime isochrones for the Campus Martius study.

Credentials are read only from TRAVELTIME_APP_ID and TRAVELTIME_API_KEY.
Raw responses are cached so a render never silently changes underneath a poster.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import geopandas as gpd
import requests
from dotenv import load_dotenv
from shapely.geometry import box, shape
from shapely.ops import unary_union

API_URL = "https://api.traveltimeapp.com/v4/time-map"
HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[3]


def departures(spec):
    day = spec["service_date"]
    zone = ZoneInfo(spec["timezone"])
    start = datetime.fromisoformat(f"{day}T{spec['departure_window']['start']}").replace(
        tzinfo=zone
    )
    end = datetime.fromisoformat(f"{day}T{spec['departure_window']['end']}").replace(
        tzinfo=zone
    )
    step = timedelta(minutes=spec["departure_window"]["interval_minutes"])
    values = []
    while start <= end:
        values.append(start)
        start += step
    return values


def _request(app_id, api_key, search):
    try:
        response = requests.post(
            API_URL,
            headers={
                "X-Application-Id": app_id,
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/geo+json",
            },
            json={"departure_searches": [search]},
            timeout=120,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not reach TravelTime at {API_URL}. Check network/DNS access and retry; "
            "completed responses remain cached."
        ) from exc
    response.raise_for_status()
    return response.json()


def _search(spec, mode, threshold, when, search_id):
    origin = spec["origin"]
    return {
        "id": search_id,
        "coords": {"lat": origin["latitude"], "lng": origin["longitude"]},
        "departure_time": when.isoformat(),
        "travel_time": threshold * 60,
        "transportation": {"type": mode},
        "no_holes": False,
        "remove_water_bodies": True,
    }


def _geometry(payload):
    features = payload.get("features", [])
    if not features:
        raise ValueError("TravelTime returned no GeoJSON features")
    return unary_union([shape(feature["geometry"]) for feature in features])


def median_coverage(polygons, cell_m=250):
    """Return cells reached by at least half of exact-time polygons.

    TravelTime's ``range`` result is a union (best departure). A regular metric grid
    makes the published median semantics explicit and deterministic.
    """
    if not polygons:
        raise ValueError("at least one polygon is required")
    series = gpd.GeoSeries(polygons, crs="EPSG:4326")
    crs = series.estimate_utm_crs()
    projected = list(series.to_crs(crs))
    minx, miny, maxx, maxy = unary_union(projected).bounds
    required = len(projected) // 2 + 1
    cells = []
    y = miny
    while y < maxy:
        x = minx
        while x < maxx:
            cell = box(x, y, x + cell_m, y + cell_m)
            center = cell.centroid
            if sum(poly.covers(center) for poly in projected) >= required:
                cells.append(cell)
            x += cell_m
        y += cell_m
    if not cells:
        return None
    result = unary_union(cells).buffer(cell_m * 0.55).buffer(-cell_m * 0.55)
    return gpd.GeoSeries([result], crs=crs).to_crs("EPSG:4326").iloc[0]


def run(spec_path, output_dir, cell_m=250):
    # Explicit environment variables retain precedence over values in the local file.
    load_dotenv(REPO_ROOT / ".env", override=False)
    app_id = os.environ.get("TRAVELTIME_APP_ID")
    api_key = os.environ.get("TRAVELTIME_API_KEY")
    if not app_id or not api_key:
        raise SystemExit(
            "Set TRAVELTIME_APP_ID and TRAVELTIME_API_KEY. "
            "No credentials are written to disk."
        )
    spec = json.loads(Path(spec_path).read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    rows = []
    times = departures(spec)

    for mode in spec["modes"]:
        sample_times = times if mode == "public_transport" else [times[0]]
        for threshold in spec["threshold_minutes"]:
            polygons = []
            for when in sample_times:
                search_id = f"{mode}-{threshold}-{when:%H%M}"
                search = _search(spec, mode, threshold, when, search_id)
                digest = hashlib.sha256(
                    json.dumps(search, sort_keys=True).encode()
                ).hexdigest()[:16]
                raw_path = raw_dir / f"{digest}.geojson"
                if raw_path.exists():
                    payload = json.loads(raw_path.read_text())
                else:
                    payload = _request(app_id, api_key, search)
                    raw_path.write_text(json.dumps(payload))
                polygons.append(_geometry(payload))
            geometry = (
                median_coverage(polygons, cell_m)
                if mode == "public_transport"
                else polygons[0]
            )
            if geometry is not None:
                rows.append(
                    {
                        "mode": mode,
                        "minutes": threshold,
                        "provider": "TravelTime",
                        "departure_summary": (
                            "median of 13 departures"
                            if mode == "public_transport"
                            else f"departure at {sample_times[0]:%H:%M}"
                        ),
                        "geometry": geometry,
                    }
                )

    output = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    path = output_dir / "traveltime_isochrones.geojson"
    output.to_file(path, driver="GeoJSON")
    print(f"Wrote {path} ({len(output)} polygons)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=HERE / "spec.json")
    parser.add_argument("--output-dir", type=Path, default=HERE / "output")
    parser.add_argument("--cell-m", type=float, default=250)
    args = parser.parse_args()
    run(args.spec, args.output_dir, args.cell_m)


if __name__ == "__main__":
    main()
