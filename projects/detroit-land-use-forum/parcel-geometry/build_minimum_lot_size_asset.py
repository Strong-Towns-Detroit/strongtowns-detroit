#!/usr/bin/env python3
"""Build the minimum-lot-size exhibit linking parcel geometry to BZA relief."""

from __future__ import annotations

from strongtowns_detroit.bza import data_directory as bza_data_directory

import base64
import html
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg
from exhibit_components import (
    LegendItem,
    forum_css,
    map_frame,
    metric_block,
    source_lines,
    swatch_legend,
    title_block,
    write_svg_bundle,
)
from parcel_exhibit_components import bza_case_stat, is_detroit_parks_taxpayer
from strongtowns_graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    SvgComponent,
    render_graphic_svg,
    write_graphic_bundle,
)
from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA_REPOSITORY = data_repository()
PARCELS = DATA_REPOSITORY / "pipelines/parcel-data/parcels_with_compliance.gpkg"
BZA = bza_data_directory()
ROADS = (
    ROOT / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
OUT = HERE / "output"

NAVY = "#0c2340"
RED = "#c83a3a"
LIGHT_BLUE = "#a7c6ed"
CREAM = "#fffaf0"
MUTED = "#647184"
OUTSIDE = "#e4dfd6"

CATEGORY_ORDER = [
    "administrative_or_community_appeal",
    "parking_supply",
    "use_spacing_separation",
    "setbacks_yards",
    "nonconforming_use_or_structure",
    "lot_coverage",
    "lot_dimensions",
    "height",
    "parking_layout",
    "screening_landscaping",
    "signs_billboards",
    "floor_area_bulk",
    "multiple_buildings",
    "open_recreation_space",
    "fences_walls",
    "loading",
]
CATEGORY_LABELS = {
    "administrative_or_community_appeal": "Administrative/community appeal",
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
    "unspecified": "Request not specified",
}
CATEGORY_COLORS = {
    "administrative_or_community_appeal": "#0c2340",
    "parking_supply": "#c83a3a",
    "use_spacing_separation": "#0072ce",
    "setbacks_yards": "#e57f00",
    "nonconforming_use_or_structure": "#43617f",
    "lot_coverage": "#d85b68",
    "lot_dimensions": "#75a7db",
    "height": "#b96f00",
    "parking_layout": "#173e67",
    "screening_landscaping": "#a92f43",
    "signs_billboards": "#5f8fbe",
    "floor_area_bulk": "#d2a944",
    "multiple_buildings": "#647184",
    "open_recreation_space": "#8f5261",
    "fences_walls": "#90b8e8",
    "loading": "#927035",
    "unspecified": "#73777d",
}

AREA_MINIMUM = 5_000
TOLERANCE = 0.01
SCREENING_BOUNDARY = AREA_MINIMUM * (1 - TOLERANCE)

AREA_EVIDENCE = (
    r"(?:minimum lot area|deficient lot area|deficient lot square footage|"
    r"deficient lot size|minimum lot size|insufficient lot size|"
    r"lot size required|lot area required)"
)
EXCESS_EVIDENCE = r"(?:excessive lot size|maximum lot size)"


def classify_lot_area(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = frame.copy()
    result["parks_taxpayer"] = is_detroit_parks_taxpayer(result)
    result["in_scope"] = (
        result["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
        & ~result["parks_taxpayer"]
    )
    result["area_sqft"] = pd.to_numeric(
        result["total_square_footage"], errors="coerce"
    )
    result["evaluated"] = result["in_scope"] & result["area_sqft"].gt(0)
    result["below_minimum"] = (
        result["evaluated"] & result["area_sqft"].lt(SCREENING_BOUNDARY)
    )
    return result


def select_residential_area_cases(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    cases = categories[categories["category"].eq("lot_dimensions")].merge(
        histories, on="case_history_id", how="inner", validate="one_to_one"
    )
    evidence = (
        cases["evidence"].fillna("") + " " + cases["proposal"].fillna("")
    )
    is_area = evidence.str.contains(AREA_EVIDENCE, case=False, regex=True)
    is_excess = evidence.str.contains(
        EXCESS_EVIDENCE, case=False, regex=True
    )
    is_residential = cases["proposal"].fillna("").str.contains(
        r"\bR[1-6](?:\b|-)", case=False, regex=True
    )
    return cases[is_area & ~is_excess & is_residential].copy()


def relief_histogram(
    categories: pd.DataFrame,
    area_cases: pd.DataFrame,
) -> list[tuple[str, int, bool]]:
    counts = categories.groupby("category")["case_history_id"].nunique()
    rows = [
        ("Parking supply", int(counts.get("parking_supply", 0)), False),
        ("Use spacing", int(counts.get("use_spacing_separation", 0)), False),
        ("Setbacks / yards", int(counts.get("setbacks_yards", 0)), False),
        (
            "Nonconforming use / structure",
            int(counts.get("nonconforming_use_or_structure", 0)),
            False,
        ),
        ("Lot coverage", int(counts.get("lot_coverage", 0)), False),
        ("Height", int(counts.get("height", 0)), False),
        ("Minimum lot area · R1–R6", len(area_cases), True),
        ("Parking layout", int(counts.get("parking_layout", 0)), False),
    ]
    return sorted(rows, key=lambda row: (-row[1], not row[2]))


def primary_request_histogram(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
) -> list[tuple[str, int, str]]:
    """Assign every case to its first specific request listed in the minutes."""
    concrete = categories[
        categories["category"].isin(CATEGORY_ORDER)
    ].drop_duplicates(["case_history_id", "category"])
    available = (
        concrete.groupby("case_history_id")["category"].apply(set).to_dict()
    )
    counts = {category: 0 for category in CATEGORY_ORDER}
    counts["unspecified"] = 0
    for row in histories.itertuples():
        candidates = available.get(row.case_history_id, set())
        primary = None
        for category in str(row.relief_categories or "").split("|"):
            if category in candidates:
                primary = category
                break
        if primary is None and candidates:
            primary = min(
                candidates,
                key=lambda value: CATEGORY_ORDER.index(value),
            )
        counts[primary or "unspecified"] += 1
    rows = [
        (CATEGORY_LABELS[category], count, CATEGORY_COLORS[category])
        for category, count in counts.items()
        if count
    ]
    return sorted(rows, key=lambda row: -row[1])


def map_image(frame: gpd.GeoDataFrame) -> str:
    outside = frame[
        frame["zoning_district"].notna() & ~frame["in_scope"]
    ]
    unknown = frame[
        frame["zoning_district"].isna()
        | (frame["in_scope"] & ~frame["evaluated"])
    ]
    meets = frame[frame["evaluated"] & ~frame["below_minimum"]]
    below = frame[frame["below_minimum"]]
    fig, ax = plt.subplots(figsize=(10.8, 7.0), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    outside.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    unknown.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    meets.plot(ax=ax, color=NAVY, edgecolor="none")
    below.plot(ax=ax, color=RED, edgecolor="none")
    roads = gpd.read_file(ROADS).to_crs(frame.crs)
    roads[roads["road_class"].isin(["major", "arterial"])].plot(
        ax=ax, color=NAVY, linewidth=0.22, alpha=0.36
    )
    ax.set_axis_off()
    ax.margins(0)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(
        buffer, format="jpeg", bbox_inches="tight", pad_inches=0,
        facecolor=CREAM, pil_kwargs={"quality": 90, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def build_graphic(
    frame: gpd.GeoDataFrame,
    area_cases: pd.DataFrame,
    *,
    title: str = "Detroit's 5,000-square-foot minimum lot area",
    subtitle: str = (
        "Recorded R1–R6 parcel area compared with the 5,000-square-foot minimum"
    ),
    sources: tuple[str, ...] | None = None,
    description: str | None = None,
) -> Graphic:
    evaluated = frame[frame["evaluated"]]
    below = evaluated[evaluated["below_minimum"]]
    total, affected = len(evaluated), len(below)
    share = affected / total
    meets = total - affected
    unknown = int(
        (
            frame["zoning_district"].isna()
            | (frame["in_scope"] & ~frame["evaluated"])
        ).sum()
    )
    outside = int(
        (
            frame["zoning_district"].notna()
            & ~frame["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
        ).sum()
    )
    parks = int(
        (
            frame["parks_taxpayer"]
            & frame["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
        ).sum()
    )
    image = map_image(frame)
    visual = f"""
<style>{forum_css(extra_sans=(".bar-label", ".bar-value"),
extra_serif=(".bza-metric",),
extra_rules=f".bza-metric{{font-size:31px;font-weight:700}}"
f".bar-label,.bar-value{{font-size:13px;fill:{NAVY}}}",
muted=MUTED)}</style>
{map_frame(f"data:image/jpeg;base64,{image}")}
{swatch_legend([
LegendItem("Variance or exception required", RED),
LegendItem("Meets minimum area", NAVY),
LegendItem("Not evaluated / outside R1–R6", OUTSIDE),
], positions=(67, 345, 565))}
{metric_block(f"{share:.0%}", ["BELOW THE 5,000-SQ.-FT. MINIMUM"],
f"{affected:,} of {total:,} evaluated parcels")}
<text class="note" x="1120" y="379">Unless lot-of-record protection, a combined</text>
<text class="note" x="1120" y="404">zoning lot, adjustment, variance, or another</text>
<text class="note" x="1120" y="429">exception applies, new development cannot</text>
<text class="note" x="1120" y="454">proceed under this minimum.</text>
{bza_case_stat(len(area_cases), "lot-area", "residential minimum-lot-area")}
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, 1600, 780, min_y=180),
        sources=sources if sources is not None else (
            "Classification: below minimum when recorded lot area is under "
            "4,950 sq. ft.; the 1% tolerance avoids false precision around "
            "the legal 5,000-sq.-ft. boundary.",
            f"Parcel result: {affected:,} below · {meets:,} meet · {unknown:,} "
            f"not enough data · {parks:,} Parks & Recreation taxpayer · "
            f"{outside:,} outside R1–R6. Sources: City parcel data; Detroit "
            "BZA minutes; Detroit Code §§50-13-1–7, 50-13-21.",
        ),
        description=description if description is not None else (
            f"{affected:,} of {total:,} evaluated R1 through R6 parcels are "
            "more than one percent below 5,000 square feet. "
            f"{len(area_cases)} BZA case histories sought residential "
            "minimum-lot-area relief."
        ),
    )


def build_svg(frame: gpd.GeoDataFrame, area_cases: pd.DataFrame) -> str:
    return render_graphic_svg(build_graphic(frame, area_cases))


def build_histogram_svg(rows: list[tuple[str, int, str]]) -> str:
    maximum = max(count for _, count, _ in rows)
    bars = []
    for index, (label, count, color) in enumerate(rows):
        y = 250 + index * 48
        width = max(4, round(820 * count / maximum))
        bars.append(
            f'<text class="label" x="55" y="{y}">'
            f'{html.escape(label)}</text>'
            f'<rect x="520" y="{y - 20}" width="{width}" height="25" '
            f'fill="{color}"/>'
            f'<text class="value" x="{535 + width}" y="{y}">{count}</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">BZA cases by request type</title>
<desc id="desc">All 405 Detroit Board of Zoning Appeals case histories from 2019 through 2026, assigned to the first specific request listed in the minutes.</desc>
<style>{forum_css(title_size=62, source_size=14,
extra_sans=(".subtitle", ".label", ".value"),
extra_rules=f".subtitle{{font-size:20px;fill:#48596d}}"
f".label{{font-size:20px;fill:{NAVY}}}"
f".value{{font-size:19px;fill:{NAVY}}}",
muted=MUTED)}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{title_block("BZA cases by request type",
"405 case histories in the 2019–2026 minutes",
title_y=132, subtitle_y=177, subtitle_class="subtitle")}
{''.join(bars)}
{source_lines([
"Cases with multiple requests are assigned to the first specific request listed in the minutes."
], first_y=1060)}
</svg>"""


def write_svg_asset(stem: str, title: str, svg: str) -> None:
    write_svg_bundle(
        OUT, stem, title, svg, width=1600, height=1100, png_width=3200
    )


def run() -> None:
    frame = classify_lot_area(
        gpd.read_file(
            PARCELS,
            columns=[
                "parcel_id", "zoning_district",
                "total_square_footage", "taxpayer_1", "taxpayer_2",
                "geometry",
            ],
        )
    )
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")
    area_cases = select_residential_area_cases(histories, categories)
    histogram = primary_request_histogram(histories, categories)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "detroit-minimum-lot-size"
    write_graphic_bundle(
        OUT, stem, build_graphic(frame, area_cases),
        aspect_ratio=CONFERENCE_LANDSCAPE, png_width=3200,
    )
    write_svg_asset(
        "detroit-bza-request-types",
        "Detroit BZA cases by request type",
        build_histogram_svg(histogram),
    )
    area_cases.to_csv(OUT / "minimum-lot-area-bza-cases.csv", index=False)
    summary = {
        "legal_minimum_sqft": AREA_MINIMUM,
        "screening_boundary_sqft": SCREENING_BOUNDARY,
        "evaluated_parcels": int(frame["evaluated"].sum()),
        "below_minimum_parcels": int(frame["below_minimum"].sum()),
        "below_minimum_share": float(
            frame["below_minimum"].sum() / frame["evaluated"].sum()
        ),
        "residential_minimum_lot_area_bza_cases": int(len(area_cases)),
        "granted_or_reversed": int(
            area_cases["final_outcome"].eq("granted_reversed").sum()
        ),
    }
    (OUT / "minimum-lot-size-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUT / (stem + '.html')}")


if __name__ == "__main__":
    run()
