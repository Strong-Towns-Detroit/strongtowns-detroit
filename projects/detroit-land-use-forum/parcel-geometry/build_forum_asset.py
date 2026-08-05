#!/usr/bin/env python3
"""Build a self-contained forum exhibit about Detroit's inherited lot pattern."""

from __future__ import annotations

import base64
import html
import io
import shutil
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exhibit_brand import masthead_svg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = (
    ROOT / "projects/detroit-land-use-forum/spirit-plaza-accessibility"
    / "output/road_context.geojson"
)
OUT = HERE / "output"

NAVY = "#0c2340"
RED = "#c83a3a"
GOLD = "#ffb549"
CREAM = "#fffaf0"
MUTED = "#647184"


def classify(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = frame.copy()
    result["in_scope"] = result["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
    result["area_sqft"] = pd.to_numeric(
        result["total_square_footage"], errors="coerce"
    )
    result["width_ft"] = pd.to_numeric(result["frontage"], errors="coerce")
    result["evaluated"] = (
        result["in_scope"] & result["area_sqft"].gt(0) & result["width_ft"].gt(0)
    )
    result["below_area"] = result["evaluated"] & result["area_sqft"].lt(4950)
    result["below_width"] = result["evaluated"] & result["width_ft"].lt(49.5)
    result["below_standard"] = (
        result["evaluated"] & (result["below_area"] | result["below_width"])
    )
    return result


def map_png(frame: gpd.GeoDataFrame) -> str:
    out_scope = frame[frame["zoning_district"].notna() & ~frame["in_scope"]]
    unknown = frame[
        frame["zoning_district"].isna() | (frame["in_scope"] & ~frame["evaluated"])
    ]
    passes = frame[frame["evaluated"] & ~frame["below_standard"]]
    below = frame[frame["below_standard"]]

    fig, ax = plt.subplots(figsize=(10.8, 7.0), dpi=180)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    out_scope.plot(ax=ax, color="#e4dfd6", edgecolor="none")
    unknown.plot(ax=ax, color="#e4dfd6", edgecolor="none")
    passes.plot(ax=ax, color=NAVY, edgecolor="none")
    below.plot(ax=ax, color=RED, edgecolor="none")
    if ROADS.exists():
        roads = gpd.read_file(ROADS).to_crs(frame.crs)
        major = roads[roads["road_class"].isin(["major", "arterial"])]
        major.plot(ax=ax, color=NAVY, linewidth=0.22, alpha=0.36)
    ax.set_axis_off()
    ax.margins(0)
    fig.tight_layout(pad=0)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0, facecolor=CREAM)
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def build_svg(frame: gpd.GeoDataFrame) -> str:
    evaluated = frame[frame["evaluated"]]
    below = evaluated[evaluated["below_standard"]]
    n, b = len(evaluated), len(below)
    pct = b / n
    passes = n - b
    unknown = int(
        (frame["zoning_district"].isna() | (frame["in_scope"] & ~frame["evaluated"])).sum()
    )
    outside = int((frame["zoning_district"].notna() & ~frame["in_scope"]).sum())
    image = map_png(frame)
    both = (below["below_area"] & below["below_width"]).sum()
    area_only = (below["below_area"] & ~below["below_width"]).sum()
    width_only = (~below["below_area"] & below["below_width"]).sum()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Detroit's inherited lots and today's dimensional standard</title>
<desc id="desc">Parcel map of R1 through R6 lots classified yes when assessed area is below 4,950 square feet or recorded frontage is below 49.5 feet, no when both meet those cutoffs, and not enough data when a required value is missing or invalid.</desc>
<style>
.paper{{fill:{CREAM}}}.kicker,.metric-label,.note,.legend,.source{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:61px;font-weight:700}}.dek{{font-size:25px;fill:#48596d}}
.metric{{font-size:72px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:28px;font-weight:700}}.note{{font-size:18px;fill:#34475d}}.legend{{font-size:15px;fill:{NAVY}}}
.source{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="116">Detroit’s lots don’t fit Detroit’s rules</text>
<text class="dek" x="55" y="158">Recorded parcel dimensions compared with the minimums in R1–R6 districts</text>
<image href="data:image/png;base64,{image}" x="50" y="205" width="1015" height="680" preserveAspectRatio="xMidYMid meet"/>
<rect x="67" y="918" width="18" height="18" fill="{RED}"/><text class="legend" x="94" y="933">Blocked by recorded dimensions</text>
<rect x="385" y="918" width="18" height="18" fill="{NAVY}"/><text class="legend" x="412" y="933">Meets both minimums</text>
<rect x="625" y="918" width="18" height="18" fill="#e4dfd6"/><text class="legend" x="652" y="933">Not enough data / outside R1–R6</text>
<text class="metric" x="1120" y="274">{pct:.0%}</text>
<text class="metric-label" x="1123" y="305">BLOCKED BY RECORDED DIMENSIONS</text>
<text class="note" x="1123" y="338">{b:,} of {n:,} evaluated parcels</text>
<text class="note" x="1120" y="386">Unless a lot-of-record provision, combined</text>
<text class="note" x="1120" y="411">zoning lot, adjustment, variance, or other</text>
<text class="note" x="1120" y="436">exception applies, new development cannot</text>
<text class="note" x="1120" y="461">proceed on these dimensions.</text>
<text class="section-title" x="1120" y="520">Residential parcels by recorded dimensions</text>
<rect x="1120" y="552" width="18" height="18" fill="{RED}"/><text class="note" x="1150" y="568">Blocked <tspan font-weight="700">{b:,}</tspan></text>
<text class="source" x="1150" y="590">{both:,} below both · {width_only:,} frontage only · {area_only:,} area only</text>
<rect x="1120" y="625" width="18" height="18" fill="{NAVY}"/><text class="note" x="1150" y="641">Meets both minimums <tspan font-weight="700">{passes:,}</tspan></text>
<rect x="1120" y="681" width="18" height="18" fill="#e4dfd6"/><text class="note" x="1150" y="697">Not enough data / outside R1–R6 <tspan font-weight="700">{unknown + outside:,}</tspan></text>
<text class="section-title" x="1120" y="830">Legal dimensional minimums</text>
<text class="metric-label" x="1120" y="864">LEGAL MINIMUM</text>
<text class="note" x="1120" y="894">5,000 sq. ft. lot area · 50 ft. lot width</text>
<text class="source" x="1120" y="932">Screening calculation allows 1% measurement tolerance.</text>
<text class="source" x="55" y="1048">Classification: blocked when recorded area or frontage is more than 1% below the legal minimum; both values are required to classify “meets.”</text>
<text class="source" x="55" y="1072">Frontage is the best available proxy for ordinance lot width. Sources: City parcel data; Detroit Code §§50-13-1–7, 50-13-21, 50-13-222.</text>
</svg>"""


def run() -> None:
    columns = [
        "parcel_id", "zoning_district", "total_square_footage", "frontage", "is_improved",
        "geometry",
    ]
    frame = classify(gpd.read_file(DATA, columns=columns))
    svg = build_svg(frame)
    OUT.mkdir(parents=True, exist_ok=True)
    svg_path = OUT / "detroit-inherited-lot-pattern.svg"
    html_path = OUT / "detroit-inherited-lot-pattern.html"
    svg_path.write_text(svg)
    html_path.write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Detroit’s inherited lot pattern</title><style>"
        "html,body{margin:0;background:#fffaf0}main{width:min(100%,1600px);margin:auto}"
        "svg{display:block;width:100%;height:auto}@media print{@page{size:16in 11in;margin:0}}"
        "</style></head><body><main>" + svg + "</main></body></html>"
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [renderer, "--width", "3200", "--output",
             str(OUT / "detroit-inherited-lot-pattern.png"), str(svg_path)],
            check=True,
        )
    print(f"Evaluated {frame.evaluated.sum():,} parcels; "
          f"{frame.below_standard.sum():,} below threshold")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    run()
