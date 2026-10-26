"""Close-up maps for neighborhoods with at least 80% small parcels."""

from html import escape
from pathlib import Path
import re
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from basemap import load_detroit_basemap
from strongtowns_graphics import (
    ChoroplethBand, GraphicInput, MobileMapSegment, SvgComponent,
    WebMercatorBasemap, graphic_definition, map_on_mobile, parcel_choropleth_map,
)


def summarize(frame):
    area = pd.to_numeric(frame["total_square_footage"], errors="coerce")
    classified = frame.assign(
        small=(area > 0) & (area < 5000),
        very_small=(area > 0) & (area < 4000),
        unknown=~(area > 0),
    )
    summary = classified.groupby("neighborhood").agg(
        total=("small", "size"), under5000=("small", "sum"),
        under4000=("very_small", "sum"), unknown=("unknown", "sum"),
    )
    summary["share"] = summary.under5000 / summary.total
    # Compare exact counts; rounded percentages never determine eligibility.
    return summary[summary.under5000 * 5 >= summary.total * 4].sort_values(
        ["share", "total"], ascending=False,
    )


def output_name(neighborhood):
    return re.sub(r"[^a-z0-9]+", "-", neighborhood.lower()).strip("-")


def legend_segment():
    items = (
        ("Under 4,000 sqft", "#c83a3a"),
        ("4,000 to under 5,000 sqft", "#e7a544"),
        ("5,000 sqft or more", "#9fb4c9"),
        ("Unknown / zero area", "#e4dfd6"),
    )
    parts = []
    for index, (label, color) in enumerate(items):
        x, y = 20 + index % 2 * 540, 35 + index // 2 * 48
        parts.append(
            f'<rect x="{x}" y="{y-23}" width="24" height="24" fill="{color}"/>'
            f'<text x="{x+40}" y="{y}" style="font:28px Arial;fill:#0c2340">'
            f'{escape(label)}</text>'
        )
    return MobileMapSegment("lot-legend", SvgComponent("".join(parts), 1080, 105))


@graphic_definition(
    "neighborhood_lot_sizes",
    inputs=(
        GraphicInput("parcels", "detroit.parcels.raw", "raw.geojson"),
        GraphicInput("boundary", "detroit.osm.basemap.raw", "detroit_boundary.geojson"),
        GraphicInput("water", "detroit.osm.basemap.raw", "detroit_water.geojson"),
        GraphicInput("roads", "detroit.base-units.streets.raw", "raw.geojson"),
    ),
)
def build(context):
    frame = gpd.read_file(context.input("parcels"), columns=[
        "neighborhood", "total_square_footage", "geometry",
    ]).to_crs(3857)
    area = pd.to_numeric(frame.total_square_footage, errors="coerce")
    frame["lot_area"] = area.where(area > 0)
    summaries = summarize(frame)
    city = load_detroit_basemap(
        context.input("boundary"), context.input("roads"), context.input("water"),
    )
    graphics = {}
    for neighborhood, row in summaries.iterrows():
        parcels = frame[frame.neighborhood.eq(neighborhood)]
        extent = box(*parcels.total_bounds)
        # Use the city's parcel neighborhood assignments, not an inferred boundary.
        roads = gpd.clip(city.roads, extent)
        water = gpd.clip(city.water, extent)
        local = WebMercatorBasemap(extent, roads, water)
        graphic = parcel_choropleth_map(
            parcels, value_column="lot_area", basemap=local,
            bands=(
                ChoroplethBand("Under 4,000 sqft", 0, 4000, "#c83a3a"),
                ChoroplethBand("4,000 to under 5,000 sqft", 4000, 5000, "#e7a544"),
                ChoroplethBand("5,000 sqft or more", 5000, float("inf"), "#9fb4c9"),
            ),
            title=f"{neighborhood} has a high share of small parcels",
            subtitle="",
            legend_heading="RECORDED LOT AREA",
            missing_label="Unknown / zero area",
            sources=(
                "Source: City of Detroit parcel data, Oct. 26, 2026. City-assigned neighborhoods. "
                f"Shares use all {int(row.total):,} parcels; {int(row.unknown):,} have unknown/zero area.",
            ),
            description=(
                f"{neighborhood}: {int(row.under5000):,} of {int(row.total):,} parcels "
                f"({row.share:.1%}) have positive recorded areas under 5,000 sqft. "
                f"{int(row.under4000):,} are under 4,000 sqft. North is up; each map uses its own extent."
            ),
        )
        metrics = []
        for x, count, threshold in ((20, row.under5000, 5000), (560, row.under4000, 4000)):
            metrics.append(
                f'<text x="{x}" y="65" style="font:bold 64px Georgia;fill:#0c2340">'
                f'{count/row.total:.1%}</text>'
                f'<text x="{x}" y="105" style="font:bold 26px Arial;fill:#48596d">'
                f'OF PARCELS ARE UNDER {threshold:,} SQFT</text>'
                f'<text x="{x}" y="140" style="font:26px Arial;fill:#48596d">'
                f'{int(count):,} of {int(row.total):,} parcels</text>'
            )
        name = output_name(neighborhood)
        if name in graphics:
            raise ValueError(f"Duplicate neighborhood output name: {name}")
        graphics[name] = map_on_mobile(graphic, segments=(
            MobileMapSegment("neighborhood-statistics", SvgComponent("".join(metrics), 1080, 160)),
            legend_segment(),
        ))
    return graphics
