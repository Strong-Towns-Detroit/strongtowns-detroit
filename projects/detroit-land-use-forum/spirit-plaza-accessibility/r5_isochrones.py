#!/usr/bin/env python3
"""Generate reproducible Campus Martius isochrones with R5, OSM, and GTFS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box
from shapely.ops import unary_union

from traveltime_isochrones import departures

HERE = Path(__file__).resolve().parent


def destination_grid(boundary, cell_m):
    boundary = boundary.to_crs(boundary.estimate_utm_crs())
    region = unary_union(boundary.geometry)
    minx, miny, maxx, maxy = region.bounds
    rows = []
    index = 0
    y = miny
    while y < maxy:
        x = minx
        while x < maxx:
            cell = box(x, y, x + cell_m, y + cell_m)
            if region.intersects(cell):
                rows.append({"id": str(index), "geometry": cell.centroid})
                index += 1
            x += cell_m
        y += cell_m
    return gpd.GeoDataFrame(rows, crs=boundary.crs).to_crs("EPSG:4326")


def _numeric_minutes(values):
    if np.issubdtype(values.dtype, np.timedelta64):
        return values.dt.total_seconds() / 60
    return pd.to_numeric(values, errors="coerce")


def _mode_times(r5py, network, origin, grid, mode, times):
    samples = []
    transport_modes = {
        "walking": [r5py.TransportMode.WALK],
        "public_transport": [
            r5py.TransportMode.TRANSIT,
            r5py.TransportMode.WALK,
        ],
        "driving": [r5py.TransportMode.CAR],
    }[mode]
    for when in times:
        matrix = r5py.TravelTimeMatrix(
            network,
            origins=origin,
            destinations=grid[["id", "geometry"]],
            departure=when.replace(tzinfo=None),
            transport_modes=transport_modes,
            snap_to_network=True,
        )
        values = matrix.set_index("to_id")["travel_time"]
        values.index = values.index.astype(str)
        samples.append(_numeric_minutes(values).rename(when.isoformat()))
    return pd.concat(samples, axis=1).median(axis=1, skipna=True)


def _bands(grid, times, thresholds, mode, cell_m):
    projected = grid.to_crs(grid.estimate_utm_crs())
    projected["travel_time"] = projected["id"].map(times)
    projected["cell"] = projected.geometry.map(
        lambda point: box(
            point.x - cell_m / 2,
            point.y - cell_m / 2,
            point.x + cell_m / 2,
            point.y + cell_m / 2,
        )
    )
    rows = []
    for threshold in thresholds:
        cells = projected.loc[
            projected["travel_time"] <= threshold, "cell"
        ]
        if cells.empty:
            continue
        geometry = unary_union(list(cells)).buffer(cell_m * 0.55).buffer(-cell_m * 0.55)
        geometry = gpd.GeoSeries([geometry], crs=projected.crs).to_crs("EPSG:4326").iloc[0]
        rows.append(
            {
                "mode": mode,
                "minutes": threshold,
                "provider": "R5 / OpenStreetMap / archived GTFS",
                "departure_summary": "median of 13 departures",
                "geometry": geometry,
            }
        )
    return rows


def run(spec_path, pbf, gtfs, boundary_path, output_path, cell_m=250):
    try:
        import r5py
    except ImportError as exc:
        raise SystemExit(
            "r5py is required for the primary model. Install the optional routing "
            "environment described in README.md."
        ) from exc

    spec = json.loads(spec_path.read_text())
    boundary = gpd.read_file(boundary_path).to_crs("EPSG:4326")
    grid = destination_grid(boundary, cell_m)
    origin = gpd.GeoDataFrame(
        {"id": ["spirit-plaza"]},
        geometry=[Point(spec["origin"]["longitude"], spec["origin"]["latitude"])],
        crs="EPSG:4326",
    )
    network = r5py.TransportNetwork(pbf, list(gtfs))
    sample_times = departures(spec)
    rows = []
    for mode in spec["modes"]:
        mode_times = _mode_times(r5py, network, origin, grid, mode, sample_times)
        rows.extend(
            _bands(grid, mode_times, spec["threshold_minutes"], mode, cell_m)
        )
    output = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_file(output_path, driver="GeoJSON")
    print(f"Wrote {output_path} ({len(output)} polygons; {len(grid)} grid cells)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=HERE / "spec.json")
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--gtfs", type=Path, nargs="+", required=True)
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "output" / "r5_isochrones.geojson")
    parser.add_argument("--cell-m", type=float, default=250)
    args = parser.parse_args()
    run(args.spec, args.pbf, args.gtfs, args.boundary, args.output, args.cell_m)


if __name__ == "__main__":
    main()
