#!/usr/bin/env python3
"""Build separate single- and two-family existing lot-coverage exhibits."""

from __future__ import annotations

import base64
import html
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg
from parcel_exhibit_components import bza_case_stat

from build_minimum_lot_size_asset import (
    BZA,
    CREAM,
    LIGHT_BLUE,
    MUTED,
    NAVY,
    OUT,
    OUTSIDE,
    PARCELS,
    RED,
    relief_histogram,
)
from lot_coverage_model import (
    coverage_building_type,
    maximum_coverage_percent,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OVERLAPS = (
    ROOT
    / "projects/detroit-land-use-forum/base-units-geometry"
    / "output/building_parcel_overlaps.csv"
)
CANDIDATE_SITES = (
    ROOT
    / "projects/detroit-land-use-forum/base-units-geometry"
    / "output/building_linked_candidate_sites.csv"
)
ROADS = (
    ROOT
    / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
TOLERANCE = 0.01

CONFIG = {
    "single_family": {
        "stem": "detroit-single-family-lot-coverage",
        "kicker": "SINGLE-FAMILY LOT COVERAGE",
        "title": "Detroit’s single-family lot-coverage limits",
        "dek": "Single-family building footprints compared with the applicable 35–45% maximum",
        "metric_label": "ABOVE THE APPLICABLE COVERAGE LIMIT",
        "bza_label": "clearly identified single-family lot-coverage",
        "small_lot_boundary": "4,000",
        "case_include": (
            r"single[- ]family dwelling|single[- ]family residential located|"
            r"existing single family zoning lot|single family dwelling currently exists|"
            r"rebuild accessory structure \(boathouse/garage\)"
        ),
        "case_exclude": r"restaurant|stacked two-family|rear setback area",
    },
    "two_family": {
        "stem": "detroit-two-family-lot-coverage",
        "kicker": "TWO-FAMILY LOT COVERAGE",
        "title": "Detroit’s two-family lot-coverage limits",
        "dek": "Two-family and duplex footprints compared with the applicable 35–45% maximum",
        "metric_label": "ABOVE THE APPLICABLE COVERAGE LIMIT",
        "bza_label": "clearly identified two-family lot-coverage",
        "small_lot_boundary": "4,300",
        "case_include": (
            r"(?:attached|stacked|separate)[^.;]{0,100}(?:two|2)[- ]family dwellings|"
            r"(?:two|2)[- ]family (?:dwellings|buildings)"
        ),
        "case_exclude": r"$^",
    },
}


def normalize_parcel_id(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()
    return cleaned or None


def load_coverage_frame() -> gpd.GeoDataFrame:
    frame = gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id",
            "zoning_district",
            "use_code_description",
            "total_square_footage",
            "geometry",
        ],
    )
    frame["parcel_key"] = frame["parcel_id"].map(normalize_parcel_id)
    frame["building_type"] = [
        coverage_building_type(district, use)
        for district, use in zip(
            frame["zoning_district"], frame["use_code_description"]
        )
    ]
    frame["lot_area_sqft"] = pd.to_numeric(
        frame["total_square_footage"], errors="coerce"
    )
    overlaps = pd.read_csv(OVERLAPS, dtype={"parcel_id": "string"})
    overlaps["parcel_key"] = overlaps["parcel_id"].map(normalize_parcel_id)
    footprint = overlaps.groupby("parcel_key")["overlap_area"].sum()
    frame["footprint_sqft"] = frame["parcel_key"].map(footprint)
    candidates = pd.read_csv(
        CANDIDATE_SITES, dtype={"parcel_id": "string"}
    )
    candidate_keys = set(
        candidates["parcel_id"].map(normalize_parcel_id).dropna()
    )
    frame["candidate_multi_parcel_site"] = frame["parcel_key"].isin(
        candidate_keys
    )
    return frame


def classify_coverage(
    frame: gpd.GeoDataFrame,
    building_type: str,
) -> gpd.GeoDataFrame:
    result = frame.copy()
    result["in_scope"] = result["building_type"].eq(building_type)
    result["allowed_coverage_pct"] = [
        maximum_coverage_percent(kind, area)
        if kind == building_type and pd.notna(area)
        else None
        for kind, area in zip(
            result["building_type"], result["lot_area_sqft"]
        )
    ]
    result["evaluated"] = (
        result["in_scope"]
        & result["lot_area_sqft"].gt(0)
        & result["footprint_sqft"].gt(0)
        & ~result["candidate_multi_parcel_site"]
        & result["allowed_coverage_pct"].notna()
    )
    result["observed_coverage_pct"] = (
        result["footprint_sqft"] / result["lot_area_sqft"] * 100
    )
    result["above_maximum"] = (
        result["evaluated"]
        & (
            result["observed_coverage_pct"]
            > result["allowed_coverage_pct"] * (1 + TOLERANCE)
        )
    )
    return result


def select_cases(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
    building_type: str,
) -> pd.DataFrame:
    config = CONFIG[building_type]
    cases = categories[categories["category"].eq("lot_coverage")].merge(
        histories, on="case_history_id", how="inner", validate="one_to_one"
    )
    proposal = cases["proposal"].fillna("")
    include = proposal.str.contains(
        config["case_include"], case=False, regex=True
    )
    exclude = proposal.str.contains(
        config["case_exclude"], case=False, regex=True
    )
    return cases[include & ~exclude].copy()


def map_image(frame: gpd.GeoDataFrame) -> str:
    other = frame[~frame["in_scope"]]
    unknown = frame[frame["in_scope"] & ~frame["evaluated"]]
    meets = frame[frame["evaluated"] & ~frame["above_maximum"]]
    above = frame[frame["above_maximum"]]
    fig, ax = plt.subplots(figsize=(10.8, 7.0), dpi=155)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    other.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    unknown.plot(ax=ax, color=OUTSIDE, edgecolor="none")
    meets.plot(ax=ax, color=NAVY, edgecolor="none")
    above.plot(ax=ax, color=RED, edgecolor="none")
    roads = gpd.read_file(ROADS).to_crs(frame.crs)
    roads[roads["road_class"].isin(["major", "arterial"])].plot(
        ax=ax, color=NAVY, linewidth=0.22, alpha=0.36
    )
    ax.set_axis_off()
    ax.margins(0)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(
        buffer,
        format="jpeg",
        bbox_inches="tight",
        pad_inches=0,
        facecolor=CREAM,
        pil_kwargs={"quality": 90, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def histogram_svg(
    rows: list[tuple[str, int, bool]],
    selected_label: str,
) -> str:
    maximum = max(count for _, count, _ in rows)
    result = []
    for index, (label, count, selected) in enumerate(rows):
        if selected:
            label = selected_label
        y = 605 + index * 45
        width = max(3, round(245 * count / maximum))
        color = RED if selected else LIGHT_BLUE
        weight = 700 if selected else 400
        result.append(
            f'<text class="bar-label" x="1120" y="{y}" '
            f'font-weight="{weight}">{html.escape(label)}</text>'
            f'<rect x="1120" y="{y + 9}" width="{width}" height="11" '
            f'fill="{color}"/>'
            f'<text class="bar-value" x="{1128 + width}" y="{y + 20}" '
            f'font-weight="{weight}">{count}</text>'
        )
    return "".join(result)


def build_svg(
    frame: gpd.GeoDataFrame,
    cases: pd.DataFrame,
    building_type: str,
    categories: pd.DataFrame,
) -> str:
    config = CONFIG[building_type]
    evaluated = frame[frame["evaluated"]]
    above = evaluated[evaluated["above_maximum"]]
    total, affected = len(evaluated), len(above)
    share = affected / total
    meets = total - affected
    unknown = int((frame["in_scope"] & ~frame["evaluated"]).sum())
    other = int((~frame["in_scope"]).sum())
    candidate = int(
        (frame["in_scope"] & frame["candidate_multi_parcel_site"]).sum()
    )
    image = map_image(frame)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">{html.escape(config["title"])}</title>
<desc id="desc">{affected:,} of {total:,} evaluated properties have recorded building coverage more than one percent above the applicable legal maximum.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.legend,.source,.bar-label,.bar-value{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title,.bza-metric{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:57px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:72px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:27px;font-weight:700}}.bza-metric{{font-size:31px;font-weight:700}}
.note{{font-size:17px;fill:#34475d}}.legend{{font-size:15px;fill:{NAVY}}}
.source{{font-size:13px;fill:{MUTED}}}.bar-label{{font-size:13px;fill:{NAVY}}}.bar-value{{font-size:13px;fill:{NAVY}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="116">{html.escape(config["title"])}</text>
<text class="dek" x="55" y="158">{html.escape(config["dek"])}</text>
<image href="data:image/jpeg;base64,{image}" x="48" y="205" width="1015" height="680" preserveAspectRatio="xMidYMid meet"/>
<rect x="67" y="918" width="18" height="18" fill="{RED}"/><text class="legend" x="94" y="933">Above applicable maximum</text>
<rect x="315" y="918" width="18" height="18" fill="{NAVY}"/><text class="legend" x="342" y="933">At or below maximum</text>
<rect x="545" y="918" width="18" height="18" fill="{OUTSIDE}"/><text class="legend" x="572" y="933">Not enough data / other parcel type</text>
<text class="metric" x="1120" y="270">{share:.0%}</text>
<text class="metric-label" x="1123" y="301">{config["metric_label"]}</text>
<text class="note" x="1123" y="334">{affected:,} of {total:,} evaluated properties</text>
<text class="note" x="1120" y="379">The ordinary maximum is 35%. On lots under</text>
<text class="note" x="1120" y="404">{config["small_lot_boundary"]} sq. ft., it rises by one point per 100</text>
<text class="note" x="1120" y="429">sq. ft. of reduced lot area, up to 45%.</text>
<text class="note" x="1120" y="454">The limit depends on lot size and building type.</text>
{bza_case_stat(len(cases), "lot-coverage", config["bza_label"])}
<text class="source" x="55" y="1038">Unit: assessor parcel. {candidate:,} possible multi-parcel building sites are not evaluated. Building type uses assessor records; footprints use City Base Units.</text>
<text class="source" x="55" y="1064">Classification allows 1% above the legal maximum for measurement tolerance. Result: {affected:,} above · {meets:,} at/below · {unknown:,} not evaluated · {other:,} other type.</text>
</svg>"""


def write_asset(
    frame: gpd.GeoDataFrame,
    cases: pd.DataFrame,
    categories: pd.DataFrame,
    building_type: str,
) -> None:
    config = CONFIG[building_type]
    svg = build_svg(frame, cases, building_type, categories)
    stem = config["stem"]
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(config["title"])}</title>'
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
                renderer,
                "--width",
                "3200",
                "--output",
                str(OUT / f"{stem}.png"),
                str(svg_path),
            ],
            check=True,
        )
    cases.to_csv(OUT / f"{stem}-bza-cases.csv", index=False)
    evaluated = frame[frame["evaluated"]]
    summary = {
        "building_type": building_type,
        "evaluated_properties": int(len(evaluated)),
        "above_maximum_properties": int(evaluated["above_maximum"].sum()),
        "above_maximum_share": float(evaluated["above_maximum"].mean()),
        "possible_multi_parcel_sites_excluded": int(
            (
                frame["in_scope"]
                & frame["candidate_multi_parcel_site"]
            ).sum()
        ),
        "bza_case_histories": int(len(cases)),
        "granted_or_reversed": int(
            cases["final_outcome"].eq("granted_reversed").sum()
        ),
        "denied_or_upheld": int(
            cases["final_outcome"].eq("denied_upheld").sum()
        ),
    }
    (OUT / f"{stem}-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = load_coverage_frame()
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")
    requested = sys.argv[1:]
    # The two-family model remains available explicitly, but the forum asset
    # set no longer publishes a standalone two-family coverage map.
    building_types = requested or ["single_family"]
    unknown = set(building_types) - set(CONFIG)
    if unknown:
        raise SystemExit(f"Unknown building type(s): {', '.join(sorted(unknown))}")
    for building_type in building_types:
        frame = classify_coverage(base, building_type)
        cases = select_cases(histories, categories, building_type)
        write_asset(frame, cases, categories, building_type)


if __name__ == "__main__":
    run()
