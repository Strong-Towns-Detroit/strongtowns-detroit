#!/usr/bin/env python3
"""Render the Detroit BZA relief atlas as self-contained HTML, SVG, and PNG."""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import math
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from PIL import Image
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from exhibit_brand import masthead_svg
from exhibit_components import (
    forum_css,
    source_lines,
    title_block,
    write_svg_bundle,
)
from strongtowns_detroit.graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    MapMarkerStyle,
    SvgComponent,
    bza_hearing_marker_area,
    bza_hearing_marker_radius,
    build_map_graphic,
    write_graphic_bundle,
)
ROOT = HERE.parents[2]
DATA = ROOT / "pipelines/zoning/bza_dataset_gemini"
PARCELS = ROOT / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = (
    ROOT / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
OUT = HERE / "output"

NAVY = "#0c2340"
LIGHT_BLUE = "#a7c6ed"
ACCESSIBLE_BLUE = "#0072ce"
RED = "#c8102e"
GOLD = "#f2a900"
CREAM = "#fffaf0"
MUTED = "#7a7f87"
PURPLE = "#7b2cbf"
LAND = "#ebe5da"

TITLES = {
    "administrative_or_community_appeal": (
        "Appeals contest an administrative decision",
        "Sites where applicants or community appellants asked the board to review an earlier decision",
    ),
    "parking_supply": (
        "Parking rules send projects to the board",
        "Sites requesting relief from the required number of off-street parking spaces",
    ),
    "use_spacing_separation": (
        "Use-spacing rules shape where businesses can open",
        "Sites requesting relief from a required separation between regulated uses",
    ),
    "setbacks_yards": (
        "Setback rules collide with real sites",
        "Sites requesting relief from required front, side, or rear yards",
    ),
    "nonconforming_use_or_structure": (
        "Existing places do not always fit today’s code",
        "Sites seeking relief involving a nonconforming use, structure, or site condition",
    ),
    "lot_coverage": (
        "Lot-coverage limits constrain some projects",
        "Sites requesting permission to cover more of a lot than the code ordinarily allows",
    ),
    "lot_dimensions": (
        "Lot dimensions trigger project-by-project relief",
        "Sites requesting relief from minimum lot area, width, or related dimensional standards",
    ),
    "height": (
        "Height limits send projects to the board",
        "Sites requesting relief from a maximum or minimum building-height standard",
    ),
    "parking_layout": (
        "Parking design rules also require relief",
        "Sites requesting relief from parking-space dimensions, maneuvering, access, or layout rules",
    ),
}

OUTCOME_LABELS = [
    ("granted_reversed", "Request granted", ACCESSIBLE_BLUE),
    ("denied_upheld", "Request denied", RED),
    ("dismissed_withdrawn", "Dismissed or withdrawn", GOLD),
    ("procedural_unresolved", "Procedural or unresolved", MUTED),
    ("mixed_or_other_decided", "Mixed decision", PURPLE),
]

CATEGORY_LABELS = {
    "administrative_or_community_appeal": "Administrative/community appeal",
    "parking": "Parking",
    "parking_supply": "Parking supply",
    "use_spacing_separation": "Use spacing/separation",
    "setbacks_yards": "Setbacks/yards",
    "nonconforming_use_or_structure": "Nonconforming use/structure",
    "lot_coverage": "Lot coverage",
    "lot_dimensions": "Lot dimensions",
    "height": "Height",
    "parking_layout": "Parking layout",
    "screening_landscaping": "Screening/landscaping",
    "signs_billboards": "Signs/billboards",
    "floor_area_bulk": "Floor area/bulk",
    "multiple_buildings": "Multiple buildings",
    "open_recreation_space": "Open/recreation space",
    "fences_walls": "Fences/walls",
    "loading": "Loading",
    "density_units": "Density/unit count",
    "building_design_standards": "Building design standards",
    "hardship_relief": "Hardship",
}

CATEGORY_COLORS = [
    # High-contrast categorical palette for the dense BZA maps. The first
    # four retain the forum's navy/red/blue/orange anchors; subsequent colors
    # alternate hue and lightness instead of clustering in blue-grey.
    "#0c2340", "#c8102e", "#0072ce", "#e8871e",
    "#008c95", "#a23b72", "#4e7d35", "#6f4c9b",
    "#2aa7d6", "#b85c1e", "#e56b8a", "#8c7a16",
    "#7a4e2d", "#76a9dc", "#3d5a80", "#d6a21d",
    "#006d77", "#9b5de5", "#bc6c25", "#5f6f52",
]
CATEGORY_COLOR_MAP = dict(zip(CATEGORY_LABELS, CATEGORY_COLORS))

PRIMARY_DISPLAY_CATEGORY = {
    "parking": "parking",
    "parking_supply": "parking",
    "parking_layout": "parking",
}

SITE_RENDER_MODES = {"dots", "parcels", "both"}


def plot_case_sites(
    ax,
    dissolved: gpd.GeoDataFrame,
    color: str,
    site_render_mode: str,
) -> None:
    if site_render_mode not in SITE_RENDER_MODES:
        raise ValueError(
            f"Unknown site render mode {site_render_mode!r}; "
            f"choose from {sorted(SITE_RENDER_MODES)}"
        )
    if site_render_mode in {"parcels", "both"}:
        dissolved.plot(
            ax=ax, color=color, edgecolor=color, linewidth=1.15, alpha=0.98
        )
    if site_render_mode in {"dots", "both"}:
        dissolved.geometry.representative_point().plot(
            ax=ax,
            color=color,
            edgecolor=NAVY,
            markersize=27,
            linewidth=0.55,
            alpha=0.98,
        )


def load_inputs() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    gpd.GeoDataFrame,
    gpd.GeoDataFrame,
    gpd.GeoDataFrame,
]:
    summary = pd.read_csv(DATA / "atlas_category_summary.csv")
    applications = pd.read_csv(DATA / "atlas_applications.csv")
    sites = gpd.read_file(DATA / "atlas_category_sites.gpkg")
    parcels = gpd.read_file(PARCELS, columns=["geometry"])
    roads = gpd.read_file(ROADS).to_crs(parcels.crs)
    return summary, applications, sites.to_crs(parcels.crs), parcels, roads


def map_image(
    category_sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    site_render_mode: str = "dots",
) -> str:
    fig, ax = plt.subplots(figsize=(10.7, 7.15), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    gpd.GeoSeries([city_geometry], crs=category_sites.crs).plot(
        ax=ax, color=LAND, edgecolor="none"
    )
    major = roads[roads["road_class"].isin(["major", "arterial"])]
    major.plot(ax=ax, color=NAVY, linewidth=0.22, alpha=0.36)
    color_by_outcome = {
        key: color for key, _, color in OUTCOME_LABELS
    }
    # Plot neutral and non-final outcomes first so substantive decisions remain
    # legible where multiple case sites overlap.
    order = [
        "procedural_unresolved",
        "mixed_or_other_decided",
        "dismissed_withdrawn",
        "granted_reversed",
        "denied_upheld",
    ]
    for outcome in order:
        selected = category_sites[
            category_sites["final_outcome"].eq(outcome)
        ]
        if selected.empty:
            continue
        dissolved = selected.dissolve(by="case_history_id")
        color = color_by_outcome[outcome]
        plot_case_sites(ax, dissolved, color, site_render_mode)
    ax.set_axis_off()
    ax.margins(0.01)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(
        buffer, format="jpeg", bbox_inches="tight", pad_inches=0,
        facecolor=CREAM, pil_kwargs={"quality": 88, "optimize": True}
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def binary_map_image(
    sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    outcome_mode: bool = False,
    site_render_mode: str = "dots",
) -> str:
    fig, ax = plt.subplots(figsize=(10.7, 7.15), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    gpd.GeoSeries([city_geometry], crs=sites.crs).plot(
        ax=ax, color=LAND, edgecolor="none"
    )
    major = roads[roads["road_class"].isin(["major", "arterial"])]
    major.plot(ax=ax, color=NAVY, linewidth=0.22, alpha=0.36)
    if outcome_mode:
        order = [
            ("denied_upheld", RED),
            ("granted_reversed", ACCESSIBLE_BLUE),
        ]
    else:
        order = [(None, GOLD)]
    for outcome, color in order:
        selected = sites if outcome is None else sites[sites["final_outcome"].eq(outcome)]
        dissolved = selected.dissolve(by="case_history_id")
        plot_case_sites(ax, dissolved, color, site_render_mode)
    ax.set_axis_off()
    ax.margins(0.01)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(
        buffer, format="jpeg", bbox_inches="tight", pad_inches=0,
        facecolor=CREAM, pil_kwargs={"quality": 88, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def build_binary_svg(
    histories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    outcome_mode: bool,
    site_render_mode: str = "dots",
) -> str:
    histories = histories.drop_duplicates("case_history_id").copy()
    sites = sites.drop_duplicates(
        ["case_history_id", "site_id", "parcel_id"]
    ).copy()
    mapped_ids = set(sites["case_history_id"])
    if outcome_mode:
        substantive = histories[
            histories["final_outcome"].isin(["granted_reversed", "denied_upheld"])
        ].copy()
        display_sites = sites[sites["case_history_id"].isin(substantive["case_history_id"])]
        granted = int(substantive["final_outcome"].eq("granted_reversed").sum())
        denied = int(substantive["final_outcome"].eq("denied_upheld").sum())
        dismissed = int(
            histories["final_outcome"].eq("dismissed_withdrawn").sum()
        )
        unresolved = int(
            histories["final_outcome"].eq("procedural_unresolved").sum()
        )
        mixed = int(
            histories["final_outcome"].eq("mixed_or_other_decided").sum()
        )
        mapped = substantive["case_history_id"].isin(mapped_ids).sum()
        title = f"The Board granted {granted} requests and denied {denied}"
        dek = "327 cases with a clear grant or denial, 2019–2026"
        metric = f"{granted / (granted + denied):.0%}"
        metric_label = "OF CLEAR DECISIONS WERE GRANTS"
        metric_note = f"{granted} granted · {denied} denied"
        section = f"""
<text class="section-title" x="1120" y="515">How the board decided</text>
<circle cx="1131" cy="573" r="8" fill="{ACCESSIBLE_BLUE}" stroke="{NAVY}"/><text class="note" x="1152" y="579">Request granted</text><text class="count" x="1510" y="579" text-anchor="end">{granted}</text>
<circle cx="1131" cy="629" r="8" fill="{RED}" stroke="{NAVY}"/><text class="note" x="1152" y="635">Request denied</text><text class="count" x="1510" y="635" text-anchor="end">{denied}</text>"""
        legend = (
            f'<circle cx="70" cy="958" r="8" fill="{ACCESSIBLE_BLUE}" stroke="{NAVY}"/>'
            '<text class="legend" x="90" y="964">Request granted</text>'
            f'<circle cx="285" cy="958" r="8" fill="{RED}" stroke="{NAVY}"/>'
            '<text class="legend" x="305" y="964">Request denied</text>'
        )
        denominator_note = (
            "The percentage compares the 327 cases ending with a clear grant "
            "or denial."
        )
        mapped_line = ""
    else:
        display_sites = sites
        total = len(histories)
        mapped = histories["case_history_id"].isin(mapped_ids).sum()
        title = "BZA requests came from across Detroit"
        dek = "Located Board of Zoning Appeals cases recorded in meeting minutes, 2019–2026"
        metric = f"{total}"
        metric_label = "CASE HISTORIES, 2019–2026"
        metric_note = f"{mapped} mapped to assessor parcels ({mapped / total:.0%})"
        section = f"""
<text class="section-title" x="1120" y="515">Sites recorded in the minutes</text>
<circle cx="1131" cy="573" r="8" fill="{GOLD}" stroke="{NAVY}"/><text class="note" x="1152" y="579">Recorded BZA request</text>
<rect x="1123" y="615" width="16" height="16" fill="{LAND}" stroke="{NAVY}" stroke-width=".5"/><text class="note" x="1152" y="629">No request matched in this corpus</text>
<text class="note" x="1120" y="704">The map describes BZA activity, not the</text>
<text class="note" x="1120" y="729">number of parcels that may need relief.</text>"""
        legend = (
            f'<circle cx="70" cy="958" r="8" fill="{GOLD}" stroke="{NAVY}"/>'
            '<text class="legend" x="90" y="964">Recorded BZA request</text>'
        )
        denominator_note = (
            "Map unit: one case history; continued hearings and rehearings count once."
        )
        mapped_line = f"{mapped} of {total} case histories were located."
    image = binary_map_image(
        display_sites,
        city_geometry,
        roads,
        outcome_mode=outcome_mode,
        site_render_mode=site_render_mode,
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100" role="img">
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.count,.legend,.source{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}.title{{font-size:59px;font-weight:700}}
.dek{{font-size:24px;fill:#48596d}}.metric{{font-size:72px;font-weight:700}}
.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:28px;font-weight:700}}.note{{font-size:17px;fill:#34475d}}
.count{{font-size:18px;font-weight:700;fill:{NAVY}}}.legend{{font-size:15px;fill:{NAVY}}}.source{{font-size:13px;fill:{MUTED}}}
</style><rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="116">{html.escape(title)}</text>
<text class="dek" x="55" y="158">{html.escape(dek)}</text>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="720" preserveAspectRatio="xMidYMid meet"/>
{legend}
<text class="metric" x="1120" y="280">{metric}</text>
<text class="metric-label" x="1123" y="311">{metric_label}</text>
<text class="note" x="1123" y="349">{metric_note}</text>
{f'<text class="note" x="1123" y="385">{mapped_line}</text>' if mapped_line else ''}
{section}
<text class="source" x="55" y="1045">{html.escape(denominator_note)}</text>
<text class="source" x="55" y="1071">Source: Detroit BZA minutes, 2019–2026; locations matched to City of Detroit assessor parcels. Roads: OpenStreetMap.</text>
</svg>"""


def build_outcome_summary(histories: pd.DataFrame) -> str:
    histories = histories.drop_duplicates("case_history_id")
    counts = histories["final_outcome"].value_counts()
    outcomes = [
        ("Request granted", int(counts.get("granted_reversed", 0)),
         ACCESSIBLE_BLUE),
        ("Request denied", int(counts.get("denied_upheld", 0)), RED),
        ("Dismissed or withdrawn",
         int(counts.get("dismissed_withdrawn", 0)), GOLD),
        ("No final decision recorded",
         int(counts.get("procedural_unresolved", 0)), MUTED),
        ("Mixed or other decision",
         int(counts.get("mixed_or_other_decided", 0)), PURPLE),
    ]
    total = sum(count for _, count, _ in outcomes)
    maximum = max(count for _, count, _ in outcomes)
    rows = []
    for index, (label, count, color) in enumerate(outcomes):
        y = 305 + index * 125
        width = 850 * count / maximum
        share = count / total
        rows.append(
            f'<text class="bar-label" x="55" y="{y + 34}">'
            f'{html.escape(label)}</text>'
            f'<rect x="410" y="{y}" width="{width:.1f}" height="48" '
            f'rx="4" fill="{color}"/>'
            f'<text class="bar-count" x="{430 + width:.1f}" y="{y + 34}">'
            f'{count}</text>'
            f'<text class="bar-share" x="1450" y="{y + 34}" '
            f'text-anchor="end">{share:.0%}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">How 405 Detroit BZA cases ended</title>
<desc id="desc">Five horizontal bars show the final recorded disposition of Detroit Board of Zoning Appeals cases from 2019 through 2026.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.dek,.bar-label,.bar-count,.bar-share,.source,.metric-label{{font-family:Arial,Helvetica,sans-serif}}
.title,.metric{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:62px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:68px;font-weight:700}}.metric-label{{font-size:14px;font-weight:700;letter-spacing:1.3px;fill:{MUTED}}}
.bar-label{{font-size:22px;fill:{NAVY}}}.bar-count{{font-size:23px;font-weight:700;fill:{NAVY}}}
.bar-share{{font-size:19px;font-weight:700;fill:{MUTED}}}.source{{font-size:14px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
<text class="kicker" x="55" y="48">DETROIT LAND USE FORUM · BOARD OF ZONING APPEALS</text>
<text class="title" x="52" y="126">How 405 BZA cases ended</text>
<text class="dek" x="55" y="171">Final recorded disposition in meeting minutes, 2019–2026</text>
<text class="metric" x="1450" y="120" text-anchor="end">{total}</text>
<text class="metric-label" x="1450" y="150" text-anchor="end">UNIQUE CASES</text>
{''.join(rows)}
<text class="source" x="55" y="1018">Each case appears once, using its latest substantive decision or, when none was recorded, its latest procedural disposition.</text>
<text class="source" x="55" y="1050">“Request denied” includes cases in which the Board upheld an earlier agency decision against the person bringing the request.</text>
<text class="source" x="55" y="1080">Source: Detroit Board of Zoning Appeals meeting minutes, 2019–2026.</text>
</svg>"""


def write_named_asset(name: str, title: str, svg: str, output_dir: Path) -> None:
    write_svg_bundle(
        output_dir, name, title, svg,
        width=1600, height=1100, png_width=3200,
    )


def outcome_rows(applications: pd.DataFrame) -> str:
    counts = applications["final_outcome"].value_counts()
    rows = []
    for index, (key, label, color) in enumerate(OUTCOME_LABELS):
        y = 590 + index * 52
        count = int(counts.get(key, 0))
        rows.append(
            f'<circle cx="1131" cy="{y - 6}" r="7" fill="{color}" '
            f'stroke="{NAVY}" stroke-width=".5"/>'
            f'<text class="note" x="1152" y="{y}">{html.escape(label)}</text>'
            f'<text class="count" x="1510" y="{y}" text-anchor="end">{count}</text>'
        )
    return "".join(rows)


def donut_path(
    cx: float,
    cy: float,
    inner_radius: float,
    outer_radius: float,
    start_angle: float,
    end_angle: float,
) -> str:
    def point(radius: float, angle: float) -> tuple[float, float]:
        radians = math.radians(angle - 90)
        return (
            cx + radius * math.cos(radians),
            cy + radius * math.sin(radians),
        )

    outer_start = point(outer_radius, start_angle)
    outer_end = point(outer_radius, end_angle)
    inner_end = point(inner_radius, end_angle)
    inner_start = point(inner_radius, start_angle)
    large = 1 if end_angle - start_angle > 180 else 0
    return (
        f"M {outer_start[0]:.2f} {outer_start[1]:.2f} "
        f"A {outer_radius} {outer_radius} 0 {large} 1 "
        f"{outer_end[0]:.2f} {outer_end[1]:.2f} "
        f"L {inner_end[0]:.2f} {inner_end[1]:.2f} "
        f"A {inner_radius} {inner_radius} 0 {large} 0 "
        f"{inner_start[0]:.2f} {inner_start[1]:.2f} Z"
    )


def donut_segments(
    values: list[tuple[str, int, str]],
    cx: float,
    cy: float,
    inner_radius: float,
    outer_radius: float,
) -> str:
    total = sum(value for _, value, _ in values)
    angle = 0.0
    segments = []
    for key, value, color in values:
        sweep = 360 * value / total
        end = angle + sweep
        segments.append(
            f'<path d="{donut_path(cx, cy, inner_radius, outer_radius, angle, end)}" '
            f'fill="{color}" stroke="{CREAM}" stroke-width="3">'
            f"<title>{html.escape(key)}: {value}</title></path>"
        )
        angle = end
    return "".join(segments)


def concrete_assignments(applications: pd.DataFrame) -> pd.DataFrame:
    excluded = {
        "dimensional_relief_unspecified",
        "request_not_stated",
    }
    return applications[
        ~applications["category"].isin(excluded)
    ].drop_duplicates(["case_history_id", "category"])


def annular_marker(
    start_angle: float,
    end_angle: float,
    inner_radius: float = 0.56,
    outer_radius: float = 1.0,
) -> MplPath:
    sweep = max(end_angle - start_angle, 0.01)
    steps = max(5, int(math.ceil(sweep / 12)))
    angles = [
        math.radians(start_angle + sweep * index / steps)
        for index in range(steps + 1)
    ]
    outer = [
        (outer_radius * math.cos(angle), outer_radius * math.sin(angle))
        for angle in angles
    ]
    inner = [
        (inner_radius * math.cos(angle), inner_radius * math.sin(angle))
        for angle in reversed(angles)
    ]
    vertices = outer + inner + [outer[0]]
    codes = (
        [MplPath.MOVETO]
        + [MplPath.LINETO] * (len(vertices) - 2)
        + [MplPath.CLOSEPOLY]
    )
    return MplPath(vertices, codes)


def primary_relief_categories(
    applications: pd.DataFrame,
) -> dict[str, str | None]:
    """Choose the first concrete category recorded in relief_categories."""
    concrete = concrete_assignments(applications)
    available = (
        concrete.groupby("case_history_id")["category"]
        .apply(set)
        .to_dict()
    )
    result: dict[str, str | None] = {}
    for case_history_id, group in applications.groupby("case_history_id"):
        candidates = available.get(case_history_id, set())
        primary = None
        relief_categories = str(group.iloc[0].get("relief_categories", ""))
        for category in relief_categories.split("|"):
            if category in candidates:
                primary = category
                break
        if primary is None and candidates:
            primary = min(
                candidates,
                key=lambda category: list(CATEGORY_LABELS).index(category),
            )
        result[case_history_id] = PRIMARY_DISPLAY_CATEGORY.get(primary, primary)
    return result


def displace_overlapping_points(
    points: gpd.GeoSeries,
    minimum_separation: float = 520.0,
    symbol_radii: np.ndarray | None = None,
    padding: float = 0.0,
    overlap_fraction: float = 0.0,
    maximum_displacement: float = 1200.0,
    iterations: int = 180,
) -> tuple[np.ndarray, float]:
    """Separate symbols while permitting a configured amount of overlap."""
    if not 0 <= overlap_fraction < 1:
        raise ValueError("overlap_fraction must be from 0 up to 1")
    original = np.array([(point.x, point.y) for point in points], dtype=float)
    placed = original.copy()
    identifiers = [str(identifier) for identifier in points.index]
    if symbol_radii is not None:
        symbol_radii = np.asarray(symbol_radii, dtype=float)
        if symbol_radii.shape != (len(points),):
            raise ValueError("symbol_radii must contain one radius per point")
    for _ in range(iterations):
        moved = False
        for left in range(len(placed)):
            delta = placed[left + 1:] - placed[left]
            distances = np.linalg.norm(delta, axis=1)
            if symbol_radii is None:
                required = np.full(
                    len(delta), minimum_separation * (1 - overlap_fraction)
                )
            else:
                required = (
                    (symbol_radii[left] + symbol_radii[left + 1:])
                    * (1 - overlap_fraction)
                    + padding
                )
            for offset in np.flatnonzero(distances < required):
                right = left + 1 + int(offset)
                distance = distances[offset]
                if distance < 1e-9:
                    digest = hashlib.sha256(
                        f"{identifiers[left]}|{identifiers[right]}".encode()
                    ).digest()
                    angle = 2 * math.pi * int.from_bytes(
                        digest[:4], "big"
                    ) / (2**32)
                    direction = np.array([math.cos(angle), math.sin(angle)])
                else:
                    direction = delta[offset] / distance
                push = direction * (required[offset] - distance) * 0.52
                placed[left] -= push
                placed[right] += push
                moved = True
        displacement = placed - original
        lengths = np.linalg.norm(displacement, axis=1)
        beyond = lengths > maximum_displacement
        placed[beyond] = (
            original[beyond]
            + displacement[beyond]
            * (maximum_displacement / lengths[beyond])[:, None]
        )
        if not moved:
            break
    maximum_used = float(np.linalg.norm(placed - original, axis=1).max())
    return placed, maximum_used


def grouped_case_map_image(
    histories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    case_groups: dict[str, str],
    group_colors: dict[str, str],
    city_geometry,
    roads: gpd.GeoDataFrame,
    marker_style: MapMarkerStyle = MapMarkerStyle(),
) -> tuple[str, int, int, float, int, float]:
    fig, ax = plt.subplots(figsize=(10.7, 7.15), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    gpd.GeoSeries([city_geometry], crs=sites.crs).plot(
        ax=ax, color=LAND, edgecolor="none"
    )
    major = roads[roads["road_class"].isin(["major", "arterial"])]
    major.plot(ax=ax, color=NAVY, linewidth=0.22, alpha=0.36)

    histories = histories.drop_duplicates("case_history_id").copy()
    histories = histories[
        histories["case_history_id"].isin(case_groups)
    ].copy()
    sites = sites.drop_duplicates(
        ["case_history_id", "site_id", "parcel_id"]
    ).copy()
    sites = sites[sites["case_history_id"].isin(case_groups)].copy()
    case_values = histories.set_index("case_history_id")["appearance_count"]
    sites["map_group"] = sites["case_history_id"].map(case_groups)
    sites["appearance_count"] = (
        sites["case_history_id"].map(case_values).fillna(1).astype(int)
    )

    # Build connected project sites. First, every parcel/address belonging to
    # one case is one project. Then cases with the same map group are
    # joined only when they share a matched address or assessor parcel.
    case_keys = list(
        sites[["case_history_id", "map_group"]]
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
        identities = sites.dropna(subset=[identity_column])
        for (_, category), group in identities.groupby(
            [identity_column, "map_group"]
        ):
            keys = [
                (case_id, category)
                for case_id in group["case_history_id"].unique()
            ]
            for key in keys[1:]:
                union(keys[0], key)

    sites["project_group"] = [
        find((case_id, category))[0]
        for case_id, category in zip(
            sites["case_history_id"], sites["map_group"]
        )
    ]
    case_sites = sites.drop_duplicates(
        ["case_history_id", "project_group", "map_group"]
    )
    aggregate = (
        case_sites.groupby(["project_group", "map_group"])
        .agg(
            appearances=("appearance_count", "sum"),
            case_count=("case_history_id", "nunique"),
        )
    )
    dissolved = sites.dissolve(by=["project_group", "map_group"])
    dissolved = dissolved.join(aggregate)
    points = dissolved.geometry.representative_point()
    appearances = dissolved["appearances"].clip(lower=1, upper=10)
    marker_areas = appearances.map(bza_hearing_marker_area).to_numpy()

    # Convert marker radii from Matplotlib points into the map's projected
    # units. This makes collision spacing follow the final visible dot sizes.
    ax.set_axis_off()
    ax.margins(0.01)
    # Detroit's northern boundary rises at the northeast corner. Shift the
    # viewport slightly north so the city—and markers along that edge—render
    # lower in the frame without changing the map scale.
    y_min, y_max = ax.get_ylim()
    northward_view_shift = (y_max - y_min) * 0.02
    ax.set_ylim(
        y_min + northward_view_shift,
        y_max + northward_view_shift,
    )
    fig.tight_layout(pad=0)
    fig.canvas.draw()
    display_origin = ax.transData.transform((0.0, 0.0))
    display_kilometer = ax.transData.transform((1000.0, 0.0))
    pixels_per_map_unit = (
        np.linalg.norm(display_kilometer - display_origin) / 1000.0
    )
    radii_pixels = np.sqrt(marker_areas) * fig.dpi / 144.0
    radii_map_units = radii_pixels / pixels_per_map_unit
    placed, maximum_displacement = displace_overlapping_points(
        points,
        symbol_radii=radii_map_units,
        overlap_fraction=marker_style.overlap_fraction,
    )

    for index, ((_, category), _) in enumerate(points.items()):
        color = group_colors.get(category, MUTED)
        ax.scatter(
            [placed[index, 0]],
            [placed[index, 1]],
            # Matplotlib's `s` is marker area. Multiplying the base area by
            # appearances keeps visible area proportional to hearing count;
            # radius therefore grows with sqrt(appearances).
            s=marker_areas[index],
            marker="o",
            c=color,
            edgecolors=CREAM,
            linewidths=0.7,
            alpha=marker_style.opacity,
            zorder=5,
        )

    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="jpeg",
        bbox_inches="tight",
        pad_inches=0,
        facecolor=CREAM,
        pil_kwargs={"quality": 91, "optimize": True},
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
        histories["case_history_id"].nunique(),
        len(points),
        maximum_displacement,
        int(appearances.max()),
        radius_per_sqrt_unit,
    )


def render_map_visual(
    histories: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    applications: pd.DataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    *,
    marker_style: MapMarkerStyle = MapMarkerStyle(),
) -> tuple[SvgComponent, dict[str, object]]:
    primary_map = primary_relief_categories(applications)
    case_groups = {
        case_history_id: category or "unspecified"
        for case_history_id, category in primary_map.items()
    }
    (
        image,
        total,
        mapped,
        maximum_displacement,
        maximum_appearances,
        radius_per_sqrt_unit,
    ) = grouped_case_map_image(
        histories,
        sites,
        case_groups,
        {**CATEGORY_COLOR_MAP, "unspecified": MUTED},
        city_geometry,
        roads,
        marker_style=marker_style,
    )
    primary_map = primary_relief_categories(applications)
    mapped_ids = set(sites["case_history_id"])
    mapped_primary = {
        case_history_id: primary_map.get(case_history_id)
        for case_history_id in mapped_ids
    }
    primary_counts = pd.Series(
        [category for category in mapped_primary.values() if category]
    ).value_counts()
    category_counts = (
        primary_counts
        .sort_values(ascending=False)
    )
    unspecified = sum(
        category is None for category in mapped_primary.values()
    )
    decided = histories[
        histories["final_outcome"].isin(
            ["granted_reversed", "denied_upheld"]
        )
    ]
    denied = int(decided["final_outcome"].eq("denied_upheld").sum())
    dismissed_or_withdrawn = int(
        histories["final_outcome"].eq("dismissed_withdrawn").sum()
    )
    adverse_or_closed = denied + dismissed_or_withdrawn
    total_cases = len(histories)

    category_legend = []
    legend_items = [
        (
            CATEGORY_LABELS[category],
            int(count),
            CATEGORY_COLOR_MAP[category],
        )
        for category, count in category_counts.items()
    ]
    legend_items.append(("Request not specified", unspecified, MUTED))
    for index, (label, count, color) in enumerate(legend_items):
        column = index // 9
        row = index % 9
        x = 1120 + column * 225
        y = 565 + row * 48
        category_legend.append(
            f'<rect x="{x}" y="{y}" width="14" height="14" '
            f'fill="{color}"/>'
            f'<text class="small-legend" x="{x + 22}" y="{y + 12}">'
            f'{html.escape(label)}</text>'
            f'<text class="small-count" x="{x + 210}" y="{y + 12}" '
            f'text-anchor="end">{count}</text>'
        )

    visual = f"""
<style>{forum_css(metric_size=65, note_size=15,
extra_sans=(".count", ".small-legend", ".small-count"),
extra_rules=f".metric-label{{font-size:14px}}"
f".count{{font-size:16px;font-weight:700;fill:{NAVY}}}"
f".small-legend{{font-size:11px;fill:{NAVY}}}"
f".small-count{{font-size:11px;font-weight:700;fill:{NAVY}}}",
muted=MUTED)}</style>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="720" preserveAspectRatio="xMidYMid meet"/>

<text class="metric" x="1120" y="275">{adverse_or_closed}</text>
<text class="metric-label" x="1123" y="305">CASES DENIED, DISMISSED,</text>
<text class="metric-label" x="1123" y="328">OR WITHDRAWN</text>
<text class="note" x="1123" y="365">of {total_cases} total cases</text>

<text class="metric-label" x="1120" y="410">HEARINGS FOR THIS CASE</text>
<circle cx="1142" cy="442" r="18" fill="{NAVY}" fill-opacity=".14" stroke="{NAVY}" stroke-width=".7"/>
<circle cx="1142" cy="447.3" r="12.7" fill="{NAVY}" fill-opacity=".18" stroke="{NAVY}" stroke-width=".7"/>
<circle cx="1142" cy="453.6" r="6.4" fill="{NAVY}" fill-opacity=".24" stroke="{NAVY}" stroke-width=".7"/>
<text class="small-count" x="1173" y="430">{maximum_appearances}</text>
<text class="small-count" x="1173" y="447">4</text>
<text class="small-count" x="1173" y="462">1</text>

<text class="section-title" x="1120" y="520">Type of request</text>
{''.join(category_legend)}
"""
    return (
        SvgComponent(visual, 1600, 780, min_y=180),
        {
            "maximum_appearances": maximum_appearances,
            "effect_size_radius_per_sqrt_unit": radius_per_sqrt_unit,
        },
    )


def build_request_outcomes_by_type(
    histories: pd.DataFrame,
    applications: pd.DataFrame,
) -> str:
    histories = histories.drop_duplicates("case_history_id").copy()
    primary_map = primary_relief_categories(applications)
    histories["category"] = (
        histories["case_history_id"].map(primary_map).fillna("unspecified")
    )
    decided = histories[
        histories["final_outcome"].isin(
            ["granted_reversed", "denied_upheld"]
        )
    ].copy()
    summary = (
        decided.groupby(["category", "final_outcome"])
        .size()
        .unstack(fill_value=0)
    )
    for column in ["granted_reversed", "denied_upheld"]:
        if column not in summary:
            summary[column] = 0
    summary["total"] = (
        summary["granted_reversed"] + summary["denied_upheld"]
    )
    summary = summary.sort_values(
        ["total", "denied_upheld"], ascending=False
    )
    maximum = int(summary["total"].max())
    denied = int(summary["denied_upheld"].sum())

    rows = []
    for index, (category, values) in enumerate(summary.iterrows()):
        y = 282 + index * 43
        width = 700 * int(values["total"]) / maximum
        granted_width = (
            width * int(values["granted_reversed"]) / int(values["total"])
        )
        label = (
            "Request not specified"
            if category == "unspecified"
            else CATEGORY_LABELS[category]
        )
        rows.append(
            f'<text class="row-label" x="55" y="{y + 17}">'
            f'{html.escape(label)}</text>'
            f'<rect x="405" y="{y}" width="{width:.1f}" height="24" '
            f'rx="3" fill="{RED}"/>'
            f'<rect x="405" y="{y}" width="{granted_width:.1f}" '
            f'height="24" rx="3" fill="{ACCESSIBLE_BLUE}"/>'
            f'<text class="row-count" x="1140" y="{y + 17}">'
            f'{int(values["granted_reversed"])} granted · '
            f'{int(values["denied_upheld"])} denied</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">How Detroit's BZA decided each type of request</title>
<desc id="desc">Horizontal bars compare requests granted with requests denied for each primary request type recorded from 2019 through 2026.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.dek,.legend,.source,.row-label,.row-count{{font-family:Arial,Helvetica,sans-serif}}
.title,.metric{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:57px;font-weight:700}}.dek{{font-size:22px;fill:#48596d}}
.metric{{font-size:56px;font-weight:700}}.legend{{font-size:15px;fill:{NAVY}}}
.row-label{{font-size:14px;fill:{NAVY}}}.row-count{{font-size:13px;fill:#34475d}}
.source{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
<text class="kicker" x="55" y="45">DETROIT LAND USE FORUM · BOARD OF ZONING APPEALS</text>
<text class="title" x="52" y="116">How the BZA decided each type of request</text>
<text class="dek" x="55" y="158">327 cases ending with a clear grant or denial, 2019–2026</text>
<rect x="55" y="198" width="16" height="16" fill="{ACCESSIBLE_BLUE}"/>
<text class="legend" x="81" y="212">Request granted</text>
<rect x="260" y="198" width="16" height="16" fill="{RED}"/>
<text class="legend" x="286" y="212">Request denied</text>
<text class="metric" x="1320" y="214">{denied / len(decided):.0%}</text>
<text class="legend" x="1323" y="244">{denied} requests denied</text>
{''.join(rows)}
<text class="source" x="55" y="1038">Outside this comparison: 41 dismissed or withdrawn cases, 33 procedural or unresolved cases, and 4 mixed decisions.</text>
<text class="source" x="55" y="1064">Source: Detroit Board of Zoning Appeals meeting minutes, 2019–2026.</text>
</svg>"""


def build_type_outcome_donut(applications: pd.DataFrame) -> str:
    excluded = {
        "dimensional_relief_unspecified",
        "request_not_stated",
        "hardship_relief",
    }
    concrete = applications[
        ~applications["category"].isin(excluded)
    ].drop_duplicates(["case_history_id", "category"])
    category_counts = (
        concrete.groupby("category")["case_history_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    category_values = [
        (
            CATEGORY_LABELS[key],
            int(value),
            CATEGORY_COLORS[index],
        )
        for index, (key, value) in enumerate(category_counts.items())
    ]
    histories = concrete.drop_duplicates("case_history_id")
    raw_outcomes = histories["final_outcome"].value_counts()
    granted = int(raw_outcomes.get("granted_reversed", 0))
    denied = int(raw_outcomes.get("denied_upheld", 0))
    other = len(histories) - granted - denied
    outcome_values = [
        ("Request granted", granted, ACCESSIBLE_BLUE),
        ("Request denied", denied, RED),
        ("Another outcome", other, MUTED),
    ]
    approval_share = granted / (granted + denied)

    category_legend = []
    for index, (label, count, color) in enumerate(category_values):
        column = index // 8
        row = index % 8
        x = 875 + column * 355
        y = 415 + row * 55
        category_legend.append(
            f'<rect x="{x}" y="{y}" width="16" height="16" fill="{color}"/>'
            f'<text class="legend" x="{x + 27}" y="{y + 13}">'
            f"{html.escape(label)}</text>"
            f'<text class="legend-count" x="{x + 325}" y="{y + 13}" '
            f'text-anchor="end">{count}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">What Detroit brought to the Board of Zoning Appeals</title>
<desc id="desc">The outer ring shows 432 concrete relief assignments by type. The inner ring shows final outcomes for the 314 case histories represented.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.source,.legend,.legend-count{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title,.center-metric{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:57px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:65px;font-weight:700}}.metric-label{{font-size:14px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:27px;font-weight:700}}.center-metric{{font-size:55px;font-weight:700}}
.note{{font-size:17px;fill:#34475d}}.legend{{font-size:14px;fill:{NAVY}}}
.legend-count{{font-size:14px;font-weight:700;fill:{NAVY}}}.source{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
<text class="kicker" x="55" y="47">DETROIT LAND USE FORUM · BOARD OF ZONING APPEALS</text>
<text class="title" x="52" y="120">What Detroit brought to the board</text>
<text class="dek" x="55" y="164">Outer ring: relief type · inner ring: final recorded outcome</text>

{donut_segments(category_values, 425, 585, 265, 355)}
{donut_segments(outcome_values, 425, 585, 155, 255)}
<circle cx="425" cy="585" r="145" fill="{CREAM}"/>
<text class="center-metric" x="425" y="580" text-anchor="middle">{approval_share:.0%}</text>
<text class="metric-label" x="425" y="610" text-anchor="middle">GRANTED AMONG</text>
<text class="metric-label" x="425" y="632" text-anchor="middle">SUBSTANTIVE OUTCOMES</text>

<text class="section-title" x="875" y="285">Final outcome</text>
<circle cx="887" cy="327" r="8" fill="{ACCESSIBLE_BLUE}"/>
<text class="note" x="906" y="333">Request granted · {granted}</text>
<circle cx="1140" cy="327" r="8" fill="{RED}"/>
<text class="note" x="1159" y="333">Request denied · {denied}</text>
<circle cx="1363" cy="327" r="8" fill="{MUTED}"/>
<text class="note" x="1382" y="333">Other · {other}</text>

<text class="section-title" x="875" y="382">Relief assignments by type</text>
{''.join(category_legend)}

<text class="metric" x="875" y="930">{len(concrete)}</text>
<text class="metric-label" x="880" y="958">RELIEF ASSIGNMENTS</text>
<text class="metric" x="1120" y="930">{len(histories)}</text>
<text class="metric-label" x="1125" y="958">CASE HISTORIES</text>
<text class="metric" x="1375" y="930">{len(category_values)}</text>
<text class="metric-label" x="1380" y="958">CONCRETE RELIEF TYPES</text>

<text class="source" x="55" y="1038">A case may request more than one kind of relief, so the outer ring counts case-type assignments while the inner ring counts unique case histories.</text>
<text class="source" x="55" y="1064">Quality-assurance labels and the analytical hardship tag are excluded. Source: Detroit BZA minutes, 2019–2026.</text>
</svg>"""


def build_svg(
    category: str,
    applications: pd.DataFrame,
    category_sites: gpd.GeoDataFrame,
    city_geometry,
    roads: gpd.GeoDataFrame,
    site_render_mode: str = "dots",
) -> str:
    title, dek = TITLES[category]
    total = applications["case_history_id"].nunique()
    mapped = applications.loc[applications["mapped"], "case_history_id"].nunique()
    first_year = pd.to_datetime(applications["first_meeting_date"]).dt.year.min()
    last_year = pd.to_datetime(applications["last_meeting_date"]).dt.year.max()
    image = map_image(
        category_sites, city_geometry, roads, site_render_mode=site_render_mode
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">{html.escape(title)}</title>
<desc id="desc">{html.escape(dek)}. {mapped} of {total} case histories are mapped.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.count,.legend,.source{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:59px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:72px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:28px;font-weight:700}}.note{{font-size:17px;fill:#34475d}}
.count{{font-size:18px;font-weight:700;fill:{NAVY}}}.legend{{font-size:15px;fill:{NAVY}}}.source{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
<text class="kicker" x="55" y="45">DETROIT LAND USE FORUM · BOARD OF ZONING APPEALS</text>
<text class="title" x="52" y="116">{html.escape(title)}</text>
<text class="dek" x="55" y="158">{html.escape(dek)}</text>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="720" preserveAspectRatio="xMidYMid meet"/>
<text class="metric" x="1120" y="280">{total}</text>
<text class="metric-label" x="1123" y="311">CASE HISTORIES, {first_year}–{last_year}</text>
<text class="note" x="1123" y="349">{mapped} located on assessor parcels ({mapped / total:.0%})</text>
<text class="note" x="1123" y="385">Continued and reheard matters count once.</text>
<text class="section-title" x="1120" y="495">How the board decided</text>
<text class="source" x="1123" y="527">Final recorded outcome for each case</text>
{outcome_rows(applications)}
<text class="source" x="55" y="1045">Map unit: one distinct BZA case. A case appears in each category of relief it requested.</text>
<text class="source" x="55" y="1071">Source: Detroit BZA minutes, 2019–2026; locations matched to City of Detroit assessor parcels. Roads: OpenStreetMap.</text>
</svg>"""


def write_asset(category: str, svg: str, output_dir: Path) -> None:
    svg_path = output_dir / f"{category}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (output_dir / f"{category}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(TITLES[category][0])}</title>"
        "<style>html,body{margin:0;background:#fffaf0}"
        "main{width:min(100%,1600px);margin:auto}svg{display:block;width:100%;height:auto}"
        "@media print{@page{size:16in 11in;margin:0}}</style></head>"
        f"<body><main>{svg}</main></body></html>",
        encoding="utf-8",
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [
                renderer, "--width", "3200", "--output",
                str(output_dir / f"{category}.png"), str(svg_path),
            ],
            check=True,
        )


def build_index(categories: list[str], output_dir: Path) -> None:
    overview_cards = (
        '<a href="relief_type_map.html"><img src="relief_type_map.png" alt="">'
        "<span>Detroit Board of Zoning Appeals cases</span></a>"
        '<a href="request_outcomes_by_type.html"><img src="request_outcomes_by_type.png" alt="">'
        "<span>How the BZA decided each type of request</span></a>"
        '<a href="all_requests_binary.html"><img src="all_requests_binary.png" alt="">'
        "<span>Requests for relief reach across Detroit</span></a>"
        '<a href="granted_denied_binary.html"><img src="granted_denied_binary.png" alt="">'
        "<span>Most decided requests were granted</span></a>"
    )
    category_cards = "".join(
        f'<a href="{category}.html"><img src="{category}.png" alt="">'
        f"<span>{html.escape(TITLES[category][0])}</span></a>"
        for category in categories
    )
    cards = overview_cards + category_cards
    output_dir.joinpath("index.html").write_text(
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Detroit BZA relief atlas</title><style>
body{margin:0;padding:3rem;background:#fffaf0;color:#0c2340;font-family:Arial,sans-serif}
h1{font:700 3rem Georgia,serif}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:2rem}
a{color:inherit;text-decoration:none;font-weight:700}img{display:block;width:100%;margin-bottom:.7rem;border:1px solid #d8d0c3}
</style></head><body><h1>Detroit BZA relief atlas</h1><div class="grid">"""
        + cards + "</div></body></html>",
        encoding="utf-8",
    )


def run(
    output_dir: Path,
) -> None:
    _, all_applications, _, parcels, roads = load_inputs()
    city_geometry = unary_union(parcels.geometry)
    output_dir.mkdir(parents=True, exist_ok=True)
    histories = pd.read_csv(DATA / "case_histories.csv")
    all_sites = gpd.read_file(DATA / "map_sites.gpkg").to_crs(parcels.crs)
    visual, metadata = render_map_visual(
        histories,
        all_sites,
        all_applications,
        city_geometry,
        roads,
    )
    relief_type_graphic = build_map_graphic(
        visual=visual,
        metadata=metadata,
        title="Detroit Board of Zoning Appeals cases",
        subtitle="Cases by primary request recorded in meeting minutes, 2019–2026",
        sources=(
            "Color shows one request type per case; some cases involved "
            "additional requests.",
            "Source: Detroit BZA minutes, 2019–2026; locations linked to City "
            "assessor parcels. To aid legibility, locations may not represent "
            "precise addresses.",
        ),
        description=(
            "Map of Detroit Board of Zoning Appeals cases by the primary type "
            "of request recorded in meeting minutes from 2019 through 2026."
        ),
    )
    write_graphic_bundle(
        output_dir, "relief_type_map", relief_type_graphic,
        aspect_ratio=CONFERENCE_LANDSCAPE, png_width=3200,
    )
    print(f"Wrote {output_dir / 'relief_type_map.html'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
