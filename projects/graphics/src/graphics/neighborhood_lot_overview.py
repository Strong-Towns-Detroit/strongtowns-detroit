"""Citywide small-lot neighborhood selection and neighborhood choropleth."""

from html import escape
from pathlib import Path
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from basemap import load_detroit_basemap
from strongtowns_graphics import (
    ChoroplethBand, GraphicInput, MobileMapInset, MobileMapPocket,
    MobileMapSegment, SvgComponent, WebMercatorBasemap,
    graphic_definition, map_on_mobile, parcel_choropleth_map,
)


def finish(graphic, items, count):
    parts = []
    for i, (label, color) in enumerate(items):
        x, y = 20 + i % 2 * 540, 35 + i // 2 * 48
        parts.append(
            f'<rect x="{x}" y="{y-23}" width="24" height="24" fill="{color}"/>'
            f'<text x="{x+40}" y="{y}" style="font:28px Arial;fill:#0c2340">'
            f'{escape(label)}</text>'
        )
    return map_on_mobile(graphic, insets=(
        MobileMapInset.hero_statistic(
            pocket=MobileMapPocket.LOWER_RIGHT, value=str(count),
            label=("NEIGHBORHOODS WITH", "80%+ OF PARCELS", "UNDER 5,000 SQFT"),
        ),
    ), segments=(MobileMapSegment(
        "neighborhood-legend", SvgComponent("".join(parts), 1080, 158),
    ),))


@graphic_definition(
    "neighborhood_lot_overview",
    inputs=(
        GraphicInput("parcels", "detroit.parcels.raw", "raw.geojson"),
        GraphicInput("neighborhoods", "detroit.neighborhoods.raw", "raw.geojson"),
        GraphicInput("boundary", "detroit.osm.basemap.raw", "detroit_boundary.geojson"),
        GraphicInput("water", "detroit.osm.basemap.raw", "detroit_water.geojson"),
        GraphicInput("roads", "detroit.base-units.streets.raw", "raw.geojson"),
    ),
)
def build(context):
    parcels = gpd.read_file(context.input("parcels"), columns=[
        "neighborhood", "total_square_footage", "geometry",
    ]).to_crs(3857)
    area = pd.to_numeric(parcels.total_square_footage, errors="coerce")
    parcels["small"] = (area > 0) & (area < 5000)
    summary = parcels.groupby("neighborhood").agg(total=("small", "size"), small=("small", "sum"))
    summary["share"] = summary.small / summary.total
    qualifying = summary.index[summary.small * 5 >= summary.total * 4]
    neighborhoods = gpd.read_file(context.input("neighborhoods")).to_crs(3857)
    if neighborhoods.nhood_name.duplicated().any():
        raise ValueError("Duplicate city neighborhood boundary names")
    if set(summary.index) != set(neighborhoods.nhood_name):
        raise ValueError("Parcel neighborhood names and boundary names do not match")
    neighborhoods = neighborhoods.merge(summary, left_on="nhood_name", right_index=True, validate="one_to_one")
    city = load_detroit_basemap(context.input("boundary"), context.input("roads"), context.input("water"))
    # Draw the official polygon edges through the renderer's context-line layer.
    # No street network is drawn here, keeping the neighborhood borders legible.
    outlines = gpd.GeoDataFrame(
        {"road_class": ["major"] * len(neighborhoods)},
        geometry=neighborhoods.geometry.boundary, crs=3857,
    )
    basemap = WebMercatorBasemap(city.land_geometry, outlines, city.water)
    backdrop = neighborhoods[["geometry"]].assign(value=-1.0)
    selected = parcels[parcels.neighborhood.isin(qualifying)][["geometry"]].copy()
    selected_area = area.loc[selected.index]
    selected["value"] = np.select(
        [selected_area.gt(0) & selected_area.lt(4000),
         selected_area.ge(4000) & selected_area.lt(5000), selected_area.ge(5000)],
        [1.0, 2.0, 3.0], default=np.nan,
    )
    highlighted = gpd.GeoDataFrame(pd.concat([backdrop, selected], ignore_index=True), crs=3857)
    sources = (
        "Sources: City of Detroit parcels (Oct. 26, 2026) and neighborhood boundaries. "
        "Shares count all parcels by city-assigned neighborhood; zero/missing areas are not small lots.",
    )
    selection = parcel_choropleth_map(
        highlighted, value_column="value", basemap=basemap,
        bands=(
            ChoroplethBand("Other neighborhoods", -1, 0, "#e9e4da"),
            ChoroplethBand("Under 4,000 sqft", 0, 1.5, "#c83a3a"),
            ChoroplethBand("4,000 to under 5,000 sqft", 1.5, 2.5, "#e7a544"),
            ChoroplethBand("5,000 sqft or more", 2.5, 3.5, "#9fb4c9"),
        ),
        title="Where small lots are the norm",
        subtitle=f"{len(qualifying)} neighborhoods where 80%+ of parcels are under 5,000 sqft",
        legend_heading="LOT AREA IN HIGHLIGHTED NEIGHBORHOODS",
        sources=sources, missing_label="Unknown / zero area",
        description="All city neighborhood boundaries, with individual parcel sizes shown only in neighborhoods where at least 80% of parcels are under 5,000 sqft. Other neighborhoods are faded.",
    )
    selection = finish(selection, (
        ("Under 4,000 sqft", "#c83a3a"),
        ("4,000 to under 5,000 sqft", "#e7a544"),
        ("5,000 sqft or more", "#9fb4c9"),
        ("Other neighborhoods", "#e9e4da"),
        ("Unknown / zero area", "#e4dfd6"),
    ), len(qualifying))
    bands = (
        ChoroplethBand("Under 50%", 0, .5, "#e9e4da"),
        ChoroplethBand("50% to under 65%", .5, .65, "#a7c6df"),
        ChoroplethBand("65% to under 80%", .65, .8, "#537da1"),
        ChoroplethBand("80% to under 90%", .8, .9, "#e7a544"),
        ChoroplethBand("90% or more", .9, 1, "#c83a3a"),
    )
    choropleth = parcel_choropleth_map(
        neighborhoods, value_column="share", bands=bands, basemap=basemap,
        title="Small lots across Detroit",
        subtitle="Share of each neighborhood's parcels under 5,000 sqft",
        legend_heading="SHARE OF PARCELS UNDER 5,000 SQFT", sources=sources,
        missing_label="No parcel data",
        description="Neighborhood choropleth showing the share of all parcels with positive recorded area under 5,000 sqft. Orange and red neighborhoods meet the 80% threshold.",
    )
    choropleth = finish(choropleth, tuple((b.label, b.color) for b in bands), len(qualifying))
    return {"small-lot-neighborhoods-highlighted": selection,
            "small-lot-neighborhoods-choropleth": choropleth}
