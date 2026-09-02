#!/usr/bin/env python3
"""Build deduplicated BZA proposed-use map and bar-chart exhibits."""

from __future__ import annotations

import base64
import html
import io
import math
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parent
FORUM = HERE.parent
ROOT = FORUM.parents[1]
sys.path.insert(0, str(FORUM))
sys.path.insert(0, str(FORUM / "bza-relief-atlas"))

from exhibit_brand import masthead_svg
from exhibit_components import (
    forum_css,
    source_lines,
    title_block,
    write_svg_bundle,
)
from build_atlas import displace_overlapping_points
from strongtowns_graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    MapMarkerStyle,
    SvgComponent,
    bza_hearing_marker_area,
    bza_hearing_marker_radius,
    render_graphic_svg,
    write_graphic_bundle,
)
from strongtowns_detroit.repositories import data_repository

DATA_REPOSITORY = data_repository()
DATA = DATA_REPOSITORY / "pipelines/zoning/bza_dataset_gemini"
CLASSIFICATIONS = (
    DATA / "project_type_enrichment/case_histories_with_project_types.csv"
)
SITES = DATA / "map_sites.gpkg"
PARCELS = DATA_REPOSITORY / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = (
    FORUM / "spirit-plaza-accessibility/output/road_context.geojson"
)
OUT = HERE / "output"

NAVY = "#0c2340"
RED = "#c83a3a"
CREAM = "#fffaf0"
MUTED = "#7a7f87"
LAND = "#ebe5da"

FAMILY_ORDER = [
    "housing",
    "cannabis_or_controlled_use",
    "vehicle_oriented",
    "mixed_use",
    "retail_or_personal_service",
    "food_or_beverage",
    "institutional_or_civic",
    "parking_only",
    "industrial_or_logistics",
    "signage",
    "office_or_medical",
    "recreation_or_open_space",
    "other",
    "religious",
]
FAMILY_LABELS = {
    "housing": "Residential projects",
    "cannabis_or_controlled_use": "Cannabis or controlled use",
    "vehicle_oriented": "Vehicle sales and services",
    "mixed_use": "Mixed-use",
    "retail_or_personal_service": "Retail or personal service",
    "food_or_beverage": "Food or beverage",
    "institutional_or_civic": "Institutional or civic",
    "parking_only": "Parking",
    "industrial_or_logistics": "Industrial or logistics",
    "signage": "Signage",
    "office_or_medical": "Office or medical",
    "recreation_or_open_space": "Recreation or open space",
    "other": "Other / insufficient detail",
    "religious": "Religious",
}
FAMILY_COLORS = {
    "housing": "#0c2340",
    "cannabis_or_controlled_use": "#c8102e",
    "vehicle_oriented": "#0072ce",
    "mixed_use": "#e8871e",
    "retail_or_personal_service": "#008c95",
    "food_or_beverage": "#a23b72",
    "institutional_or_civic": "#4e7d35",
    "parking_only": "#6f4c9b",
    "industrial_or_logistics": "#2aa7d6",
    "signage": "#b85c1e",
    "office_or_medical": "#e56b8a",
    "recreation_or_open_space": "#8c7a16",
    "other": "#73777d",
    "religious": "#76a9dc",
}


def selected_cases(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one display classification per canonical case history."""
    selected = frame.drop_duplicates("case_history_id").copy()
    selected["display_family"] = selected["project_type_family"]
    insufficient_detail = (
        selected["confidence"].eq("low")
        | selected["project_type_family"].eq("unclear")
    )
    selected.loc[insufficient_detail, "display_family"] = "other"
    return selected.copy()


def load_inputs():
    cases = selected_cases(pd.read_csv(CLASSIFICATIONS))
    sites = gpd.read_file(SITES)
    parcels = gpd.read_file(PARCELS, columns=["geometry"])
    roads = gpd.read_file(ROADS).to_crs(parcels.crs)
    sites = sites.to_crs(parcels.crs)
    city = parcels.geometry.union_all()
    return cases, sites, city, roads


def map_image(
    cases: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    marker_style: MapMarkerStyle = MapMarkerStyle(),
) -> tuple[str, int, int]:
    case_family = cases.set_index("case_history_id")["display_family"]
    case_appearances = cases.set_index("case_history_id")["appearance_count"]
    located = sites[
        sites["case_history_id"].isin(cases["case_history_id"])
    ].drop_duplicates(["case_history_id", "site_id", "parcel_id"]).copy()
    located["family"] = located["case_history_id"].map(case_family)
    located["appearance_count"] = (
        located["case_history_id"].map(case_appearances).fillna(1).astype(int)
    )

    # Match the request-type map: combine cases only when both the mapped site
    # and the analytic category match, then sum their hearing appearances.
    case_keys = list(
        located[["case_history_id", "family"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    parent = {key: key for key in case_keys}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        keep, merge = sorted([left_root, right_root], key=str)
        parent[merge] = keep

    for identity_column in ["site_id", "parcel_id"]:
        identities = located.dropna(subset=[identity_column])
        for (_, family), group in identities.groupby(
            [identity_column, "family"]
        ):
            keys = [
                (case_id, family)
                for case_id in group["case_history_id"].unique()
            ]
            for key in keys[1:]:
                union(keys[0], key)

    located["project_group"] = [
        find((case_id, family))[0]
        for case_id, family in zip(
            located["case_history_id"], located["family"]
        )
    ]
    case_sites = located.drop_duplicates(
        ["case_history_id", "project_group", "family"]
    )
    aggregate = (
        case_sites.groupby(["project_group", "family"])
        .agg(appearances=("appearance_count", "sum"))
    )
    dissolved = located.dissolve(by=["project_group", "family"])
    dissolved = dissolved.join(aggregate)
    points = dissolved.geometry.representative_point()
    appearances = dissolved["appearances"].clip(lower=1, upper=10)
    marker_areas = appearances.map(bza_hearing_marker_area).to_numpy()

    fig, ax = plt.subplots(figsize=(10.7, 7.15), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    gpd.GeoSeries([city_geometry], crs=sites.crs).plot(
        ax=ax, color=LAND, edgecolor="none"
    )
    roads[roads["road_class"].isin(["major", "arterial"])].plot(
        ax=ax, color=NAVY, linewidth=0.22, alpha=0.36
    )
    ax.set_axis_off()
    ax.margins(0.01)
    y_min, y_max = ax.get_ylim()
    shift = (y_max - y_min) * 0.02
    ax.set_ylim(y_min + shift, y_max + shift)
    fig.tight_layout(pad=0)
    fig.canvas.draw()
    origin = ax.transData.transform((0.0, 0.0))
    kilometer = ax.transData.transform((1000.0, 0.0))
    pixels_per_unit = np.linalg.norm(kilometer - origin) / 1000.0
    radii_pixels = np.sqrt(marker_areas) * fig.dpi / 144.0
    radii = radii_pixels / pixels_per_unit
    placed, _ = displace_overlapping_points(
        points,
        symbol_radii=radii,
        overlap_fraction=marker_style.overlap_fraction,
    )
    for index, ((_, family), _) in enumerate(points.items()):
        ax.scatter(
            [placed[index, 0]], [placed[index, 1]],
            s=marker_areas[index],
            c=FAMILY_COLORS[family],
            edgecolors=CREAM,
            linewidths=0.75,
            alpha=marker_style.opacity,
            zorder=5,
        )
    buffer = io.BytesIO()
    fig.savefig(
        buffer, format="jpeg", bbox_inches="tight", pad_inches=0,
        facecolor=CREAM, pil_kwargs={"quality": 91, "optimize": True},
    )
    image_width = Image.open(io.BytesIO(buffer.getvalue())).width
    radius_per_sqrt_unit = bza_hearing_marker_radius(
        1,
        raster_dpi=fig.dpi,
        raster_width=image_width,
        embedded_width=1015,
    )
    plt.close(fig)
    return (
        base64.b64encode(buffer.getvalue()).decode(),
        len(dissolved),
        int(appearances.max()),
        radius_per_sqrt_unit,
    )


def map_graphic(
    cases: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    *,
    title: str = "Proposed uses in Detroit BZA cases",
    subtitle: str = (
        "Cases grouped by the project described in meeting minutes, 2019–2026"
    ),
    sources: tuple[str, ...] = (
        "Repeat hearings are consolidated into one case.",
        "Proposed-use labels are analytic groupings derived from the "
        "minutes, independent of Detroit’s zoning-use categories.",
        "Source: Detroit BZA minutes, 2019–2026; locations linked to City "
        "assessor parcels. To aid legibility, locations may not represent "
        "precise addresses.",
    ),
    description: str | None = None,
    marker_style: MapMarkerStyle = MapMarkerStyle(),
) -> Graphic:
    image, located, maximum_appearances, radius_per_sqrt_unit = map_image(
        cases, sites, city_geometry, roads, marker_style=marker_style
    )
    counts = cases["display_family"].value_counts()
    legend = []
    items = [
        (FAMILY_LABELS[key], int(counts.get(key, 0)), FAMILY_COLORS[key])
        for key in FAMILY_ORDER if counts.get(key, 0)
    ]
    for index, (label, count, color) in enumerate(items):
        column, row = index // 8, index % 8
        x, y = 1120 + column * 225, 565 + row * 48
        legend.append(
            f'<rect x="{x}" y="{y}" width="14" height="14" fill="{color}"/>'
            f'<text class="small-legend" x="{x + 22}" y="{y + 12}">'
            f'{html.escape(label)}</text>'
            f'<text class="small-count" x="{x + 210}" y="{y + 12}" '
            f'text-anchor="end">{count}</text>'
        )
    housing = int(counts.get("housing", 0))
    mixed_use = int(counts.get("mixed_use", 0))
    residential_or_mixed = housing + mixed_use
    residential_or_mixed_share = residential_or_mixed / len(cases)
    visual = f"""
<style>{forum_css(metric_size=65, note_size=15,
extra_sans=(".small-legend", ".small-count"),
extra_rules=f".small-legend{{font-size:11px;fill:{NAVY}}}"
f".small-count{{font-size:11px;font-weight:700;fill:{NAVY}}}",
muted=MUTED)}</style>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="720" preserveAspectRatio="xMidYMid meet"/>
<text class="metric" x="1120" y="275">{residential_or_mixed_share:.0%}</text>
<text class="metric-label" x="1123" y="305">OF CASES WERE FOR RESIDENTIAL</text>
<text class="metric-label" x="1123" y="328">OR MIXED-USE PROJECTS</text>
<text class="note" x="1123" y="370">{residential_or_mixed} of {len(cases)} cases</text>
<text class="metric-label" x="1120" y="410">HEARINGS FOR THIS CASE</text>
<circle cx="1142" cy="442" r="18" fill="{NAVY}" fill-opacity=".14" stroke="{NAVY}" stroke-width=".7"/>
<circle cx="1142" cy="447.3" r="12.7" fill="{NAVY}" fill-opacity=".18" stroke="{NAVY}" stroke-width=".7"/>
<circle cx="1142" cy="453.6" r="6.4" fill="{NAVY}" fill-opacity=".24" stroke="{NAVY}" stroke-width=".7"/>
<text class="small-count" x="1173" y="430">{maximum_appearances}</text>
<text class="small-count" x="1173" y="447">4</text>
<text class="small-count" x="1173" y="462">1</text>
<text class="section-title" x="1120" y="520">Proposed use</text>
{''.join(legend)}
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, 1600, 780, min_y=180),
        sources=sources,
        description=description if description is not None else (
            f"A deduplicated map of all {len(cases)} Detroit BZA case histories "
            "grouped by the proposed use described in meeting minutes."
        ),
        metadata={
            "maximum_appearances": maximum_appearances,
            "effect_size_radius_per_sqrt_unit": radius_per_sqrt_unit,
        },
    )


def map_svg(
    cases: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
) -> str:
    return render_graphic_svg(map_graphic(cases, sites, city_geometry, roads))


def bar_svg(cases: pd.DataFrame) -> str:
    counts = cases["display_family"].value_counts()
    rows = [
        (FAMILY_LABELS[key], int(counts[key]), FAMILY_COLORS[key])
        for key in FAMILY_ORDER if counts.get(key, 0)
    ]
    rows.sort(key=lambda row: -row[1])
    maximum = max(count for _, count, _ in rows)
    bars = []
    for index, (label, count, color) in enumerate(rows):
        y = 250 + index * 48
        width = max(4, round(820 * count / maximum))
        bars.append(
            f'<text class="label" x="55" y="{y}">{html.escape(label)}</text>'
            f'<rect x="520" y="{y - 20}" width="{width}" height="25" '
            f'fill="{color}"/>'
            f'<text class="value" x="{535 + width}" y="{y}">{count}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">BZA cases by proposed use</title>
<desc id="desc">Horizontal bars count all {len(cases)} deduplicated BZA case histories by the proposed use described in meeting minutes.</desc>
<style>{forum_css(title_size=62, source_size=14,
extra_sans=(".subtitle", ".label", ".value"),
extra_rules=f".subtitle{{font-size:20px;fill:#48596d}}"
f".label{{font-size:20px;fill:{NAVY}}}"
f".value{{font-size:19px;fill:{NAVY}}}",
muted=MUTED)}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{title_block("BZA cases by proposed use",
f"{len(cases)} cases recorded in the 2019–2026 minutes",
title_y=132, subtitle_y=177, subtitle_class="subtitle")}
{''.join(bars)}
{source_lines([
"Repeat hearings are consolidated into one case.",
"Proposed-use labels are analytic groupings derived from the minutes, independent of Detroit’s zoning-use categories.",
], first_y=1035, line_height=25)}
</svg>"""


def run() -> None:
    cases, sites, city, roads = load_inputs()
    if len(cases) != cases["case_history_id"].nunique():
        raise ValueError("Use-type cases are not deduplicated")
    OUT.mkdir(parents=True, exist_ok=True)
    write_graphic_bundle(
        OUT, "detroit-bza-proposed-use-map",
        map_graphic(cases, sites, city, roads),
        aspect_ratio=CONFERENCE_LANDSCAPE, png_width=3200,
    )
    write_svg_bundle(
        OUT, "detroit-bza-proposed-use-types",
        "BZA cases by proposed use",
        bar_svg(cases),
        width=1600, height=1100, png_width=3200,
    )
    cases.to_csv(OUT / "deduplicated-use-type-cases.csv", index=False)
    print(f"Wrote {len(cases)} deduplicated cases to {OUT}")


if __name__ == "__main__":
    run()
