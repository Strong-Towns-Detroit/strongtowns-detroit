#!/usr/bin/env python3
"""Render the running comparison of candidate Detroit basemap layers."""

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARCELS = ROOT / "pipelines/parcel-data/parcels_with_compliance.gpkg"
CONTEXT = ROOT / "sites/land-forum/public/data/detroit-context.geojson"
ROADS = (
    ROOT
    / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
WATER = (
    ROOT
    / "pipelines/housingDataAnalysis/street_simplification/output"
    / "detroit_water.gpkg"
)
OUTPUT = HERE / "output/basemap-options.png"

CREAM = "#fffaf0"
LAND = "#ebe5da"
NAVY = "#0c2340"


def _setup_axis(axis, title: str, bounds: tuple[float, float, float, float]) -> None:
    axis.set_title(title, fontsize=15)
    axis.set_aspect("equal")
    axis.axis("off")
    axis.set_facecolor(CREAM)
    axis.set_xlim(bounds[0], bounds[2])
    axis.set_ylim(bounds[1], bounds[3])


def _plot_osm_roads(axis, roads: gpd.GeoDataFrame) -> None:
    styles = {
        "local": {"linewidth": 0.18, "alpha": 0.18},
        "arterial": {"linewidth": 0.34, "alpha": 0.32},
        "major": {"linewidth": 0.58, "alpha": 0.44},
    }
    for road_class in ("local", "arterial", "major"):
        selected = roads[roads["road_class"].eq(road_class)]
        if not selected.empty:
            selected.plot(ax=axis, color=NAVY, zorder=3, **styles[road_class])


def main() -> None:
    parcels = gpd.read_file(PARCELS, columns=["geometry"])
    parcel_mask = parcels.geometry.union_all()
    context = gpd.read_file(CONTEXT)
    city = (
        context[context["kind"].eq("city")]
        .to_crs(parcels.crs)
        .geometry.union_all()
    )
    roads = gpd.read_file(ROADS).to_crs(parcels.crs)
    water = gpd.read_file(WATER).to_crs(parcels.crs)
    water = water[water.geom_type.isin(["Polygon", "MultiPolygon"])]
    bounds = city.bounds

    figure, axes = plt.subplots(1, 5, figsize=(30, 6), dpi=160)
    figure.patch.set_facecolor(CREAM)
    titles = (
        "Current parcel-derived mask",
        "Existing city silhouette",
        "Difference overlay",
        "City silhouette + full OSM roads",
        "OSM roads + negative water mask",
    )
    for axis, title in zip(axes, titles):
        _setup_axis(axis, title, bounds)

    gpd.GeoSeries([parcel_mask], crs=parcels.crs).plot(
        ax=axes[0], color=LAND, edgecolor="none"
    )
    gpd.GeoSeries([city], crs=parcels.crs).plot(
        ax=axes[1], color=LAND, edgecolor="none"
    )
    gpd.GeoSeries([city], crs=parcels.crs).plot(
        ax=axes[2], color="#d9e7f5", edgecolor="none"
    )
    gpd.GeoSeries([parcel_mask], crs=parcels.crs).plot(
        ax=axes[2], color="#e98b67", edgecolor="none"
    )
    gpd.GeoSeries([city], crs=parcels.crs).plot(
        ax=axes[3], color=LAND, edgecolor="none"
    )
    _plot_osm_roads(axes[3], roads)
    gpd.GeoSeries([city], crs=parcels.crs).plot(
        ax=axes[4], color=LAND, edgecolor="none"
    )
    water.plot(ax=axes[4], color=CREAM, edgecolor="none", zorder=2)
    _plot_osm_roads(axes[4], roads)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout(pad=1.5)
    figure.savefig(OUTPUT, bbox_inches="tight", facecolor=CREAM)
    plt.close(figure)
    print(OUTPUT)


if __name__ == "__main__":
    main()
