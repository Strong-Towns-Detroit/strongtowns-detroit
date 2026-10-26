"""Detroit parcel sizes and R1 zoning from the pinned city parcel source."""

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
    MobileMapSegment, SvgComponent,
    graphic_definition, map_on_mobile, parcel_choropleth_map,
)


def with_insets(graphic, insets, legend):
    """Compose a two-column editorial legend with the standard mobile map."""
    markup = []
    for index, (label, color) in enumerate(legend):
        x, y = 20 + (index % 2) * 540, 35 + (index // 2) * 48
        markup.append(
            f'<rect x="{x}" y="{y - 23}" width="24" height="24" fill="{color}"/>'
            f'<text x="{x + 40}" y="{y}" style="font:28px Arial;fill:#0c2340">'
            f'{escape(label)}</text>'
        )
    return map_on_mobile(graphic, insets=insets, segments=(
        MobileMapSegment(name="lot-legend", content=SvgComponent(
            "".join(markup), 1080, 110,
        )),
    ))


@graphic_definition(
    "detroit_lot_sizes",
    inputs=(
        GraphicInput("parcels", "detroit.parcels.raw", "raw.geojson"),
        GraphicInput("boundary", "detroit.osm.basemap.raw", "detroit_boundary.geojson"),
        GraphicInput("water", "detroit.osm.basemap.raw", "detroit_water.geojson"),
        GraphicInput("roads", "detroit.base-units.streets.raw", "raw.geojson"),
    ),
)
def build(context):
    frame = gpd.read_file(context.input("parcels"), columns=[
        "total_square_footage", "zoning_district", "geometry",
    ]).to_crs(3857)
    area = pd.to_numeric(frame.total_square_footage, errors="coerce")
    frame["area"] = area.where(area > 0)
    zoning = frame.zoning_district.astype("string").str.strip()
    frame["r1"] = np.where(zoning.eq("R1").fillna(False), 1.0, 0.0)
    frame.loc[zoning.isna() | zoning.eq(""), "r1"] = np.nan
    total = len(frame)
    under4000 = int(frame["area"].lt(4000).sum())
    under5000 = int(frame["area"].lt(5000).sum())
    r1_count = int(frame.r1.eq(1).sum())
    unknown_area = int(frame["area"].isna().sum())
    basemap = load_detroit_basemap(
        context.input("boundary"), context.input("roads"), context.input("water"),
    )
    sources = (
        "Source: City of Detroit parcel data, downloaded Oct. 26, 2026. "
        f"Shares use all {total:,} parcel records; {unknown_area:,} have unknown/zero area.",
    )
    sizes = parcel_choropleth_map(
        frame, value_column="area", basemap=basemap,
        bands=(
            ChoroplethBand("Under 4,000 sq ft", 0, 4000, "#c83a3a"),
            ChoroplethBand("4,000–4,999 sq ft", 4000, 5000, "#e7a544"),
            ChoroplethBand("5,000+ sq ft", 5000, float("inf"), "#9fb4c9"),
        ),
        title="Detroit is a city of small lots",
        subtitle=f"{under5000:,} of {total:,} parcels are smaller than 5,000 sq ft",
        legend_heading="RECORDED LOT AREA",
        missing_label="Unknown / zero area", sources=sources,
        description=(f"{under5000:,} of {total:,} parcels ({under5000/total:.0%}) "
                     f"under 5,000 square feet; {under4000:,} ({under4000/total:.0%}) "
                     "under 4,000. The smaller group is included in the larger. "
                     "Only positive recorded areas are classified as small lots."),
    )
    sizes = with_insets(sizes, (
        MobileMapInset.hero_statistic(
            pocket=MobileMapPocket.LOWER_LEFT, value=f"{under5000/total:.0%}",
            label=("OF PARCELS ARE", "UNDER 5,000 SQFT", f"{under5000:,} PARCELS"),
        ),
        MobileMapInset.hero_statistic(
            pocket=MobileMapPocket.LOWER_RIGHT, value=f"{under4000/total:.0%}",
            label=("OF PARCELS ARE", "UNDER 4,000 SQFT", f"{under4000:,} PARCELS"),
        ),
    ), (
        ("Under 4,000 sq ft", "#c83a3a"),
        ("4,000 to under 5,000 sq ft", "#e7a544"),
        ("5,000 sq ft or more", "#9fb4c9"),
        ("Unknown / zero area", "#e4dfd6"),
    ))
    r1 = parcel_choropleth_map(
        frame, value_column="r1", basemap=basemap,
        bands=(
            ChoroplethBand("Other zoning", 0, 0.5, "#ddd5c7"),
            ChoroplethBand("R1 zoning", 0.5, 1, "#0c2340"),
        ),
        title="Half of Detroit's parcels are zoned R1",
        subtitle=f"{r1_count:,} of {total:,} parcels citywide",
        legend_heading="PARCEL ZONING", sources=sources,
        missing_label="Unknown zoning",
        description=f"{r1_count:,} of {total:,} parcels ({r1_count/total:.0%}) are zoned R1.",
    )
    r1 = with_insets(r1, (
        MobileMapInset.hero_statistic(
            pocket=MobileMapPocket.LOWER_RIGHT, value=f"{r1_count/total:.0%}",
            label=("OF ALL PARCELS ZONED R1", f"{r1_count:,} PARCELS"),
        ),
    ), (("R1 zoning", "#0c2340"), ("Other zoning", "#ddd5c7"),
        ("Unknown zoning", "#e4dfd6")))
    return {"detroit-lot-sizes": sizes, "detroit-r1-zoning": r1}
