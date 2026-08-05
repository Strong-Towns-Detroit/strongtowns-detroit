#!/usr/bin/env python3
"""Map Detroit's total assessed property value per acre."""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FORUM = HERE.parent
ROOT = FORUM.parents[1]
sys.path.insert(0, str(FORUM))

from exhibit_brand import masthead_svg
from exhibit_components import (
    LegendItem,
    forum_css,
    map_frame,
    source_lines,
    swatch_legend,
    title_block,
    write_svg_bundle,
)

PARCELS = ROOT / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = FORUM / "spirit-plaza-accessibility/output/road_context.geojson"
OUT = HERE / "output"

NAVY = "#0c2340"
CREAM = "#fffaf0"
MUTED = "#647184"
NO_VALUE = "#e4dfd6"

BANDS = [
    ("$1–$25,000", 0, 25_000, "#a7c6ed"),
    ("$25,001–$100,000", 25_000, 100_000, "#5790db"),
    ("$100,001–$250,000", 100_000, 250_000, "#ffb549"),
    ("$250,001–$500,000", 250_000, 500_000, "#e8783d"),
    ("$500,001–$1 million", 500_000, 1_000_000, "#c83a3a"),
    ("More than $1 million", 1_000_000, np.inf, "#8f1d2d"),
]


def classify(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = frame.copy()
    result["assessed"] = pd.to_numeric(
        result["assessed_value"], errors="coerce"
    )
    result["parcel_sqft"] = pd.to_numeric(
        result["total_square_footage"], errors="coerce"
    )
    result["recorded"] = (
        result["assessed"].notna() & result["parcel_sqft"].gt(0)
    )
    result["assessed_value_per_acre"] = np.where(
        result["recorded"],
        result["assessed"] / result["parcel_sqft"] * 43_560,
        np.nan,
    )
    result["map_color"] = NO_VALUE
    for _, lower, upper, color in BANDS:
        selected = (
            result["assessed_value_per_acre"].gt(lower)
            & result["assessed_value_per_acre"].le(upper)
        )
        result.loc[selected, "map_color"] = color
    return result


def concentration(frame: gpd.GeoDataFrame, land_share: float = 0.10) -> float:
    """Share of assessed value on the highest-value-per-acre land share."""
    recorded = frame[frame["recorded"]].sort_values(
        "assessed_value_per_acre", ascending=False
    ).copy()
    recorded["cumulative_land"] = (
        recorded["parcel_sqft"].cumsum() / recorded["parcel_sqft"].sum()
    )
    recorded["cumulative_value"] = (
        recorded["assessed"].cumsum() / recorded["assessed"].sum()
    )
    return float(
        recorded.loc[
            recorded["cumulative_land"].ge(land_share),
            "cumulative_value",
        ].iloc[0]
    )


def map_image(frame: gpd.GeoDataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10.8, 7.0), dpi=435)
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    frame.plot(ax=ax, color=frame["map_color"], edgecolor="none")
    roads = gpd.read_file(ROADS).to_crs(frame.crs)
    roads[roads["road_class"].isin(["major", "arterial"])].plot(
        ax=ax, color=CREAM, linewidth=0.25, alpha=0.56
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
        pil_kwargs={"quality": 91, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def build_svg(frame: gpd.GeoDataFrame) -> str:
    recorded = frame[frame["recorded"]]
    zero = int(recorded["assessed"].eq(0).sum())
    unknown = int((~frame["recorded"]).sum())
    share = concentration(frame)
    image = map_image(frame)
    legend = [
        LegendItem("No recorded value / $0", NO_VALUE),
        *[LegendItem(label, color) for label, _, _, color in BANDS],
    ]
    first_legend_row = swatch_legend(
        legend[:4], positions=(67, 330, 585, 865),
        y=925, size=17, text_gap=8,
    )
    second_legend_row = swatch_legend(
        legend[4:], positions=(67, 350, 655),
        y=965, size=17, text_gap=8,
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Detroit's assessed property value per acre</title>
<desc id="desc">Parcel map comparing total assessed land and improvement value per acre. {share:.0%} of recorded assessed value is concentrated on 10 percent of recorded parcel acreage.</desc>
<style>{forum_css(title_size=61, metric_size=72, note_size=17,
extra_rules=".metric-label{font-size:14px}", muted=MUTED)}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{title_block("Detroit's assessed property value per acre",
"Total assessed land and improvement value divided by recorded parcel area")}
{map_frame(f"data:image/jpeg;base64,{image}")}
{first_legend_row}
{second_legend_row}
<text class="metric" x="1120" y="275">{share:.0%}</text>
<text class="metric-label" x="1123" y="305">OF ASSESSED VALUE IS CONCENTRATED</text>
<text class="metric-label" x="1123" y="328">ON 10% OF RECORDED PARCEL ACREAGE</text>
<text class="note" x="1123" y="380">Assessed value per acre makes parcels of</text>
<text class="note" x="1123" y="405">different sizes directly comparable.</text>
<text class="section-title" x="1120" y="485">What this measures</text>
<text class="note" x="1123" y="530">The assessment includes both land and</text>
<text class="note" x="1123" y="555">buildings. It is not a land-only value,</text>
<text class="note" x="1123" y="580">sale price, tax bill, or taxable value.</text>
{source_lines([
f"Coverage: {len(recorded):,} parcels with recorded area and assessment; {zero:,} have a recorded assessment of $0; {unknown:,} lack a usable area or assessment.",
"Source: City of Detroit parcel assessment data downloaded in 2026.",
"Values are nominal assessor records and have not been adjusted for exemptions or assessment-year differences.",
], first_y=1018, line_height=24)}
</svg>"""


def run() -> None:
    frame = classify(gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id", "assessed_value", "total_square_footage", "geometry",
        ],
    ))
    svg = build_svg(frame)
    OUT.mkdir(parents=True, exist_ok=True)
    write_svg_bundle(
        OUT,
        "detroit-assessed-value-per-acre",
        "Detroit assessed property value per acre",
        svg,
        width=1600,
        height=1100,
        png_width=3200,
    )
    summary = pd.DataFrame([{
        "parcels": len(frame),
        "recorded_parcels": int(frame["recorded"].sum()),
        "zero_assessment_parcels": int(
            (frame["recorded"] & frame["assessed"].eq(0)).sum()
        ),
        "top_ten_percent_land_assessed_value_share": concentration(frame),
    }])
    summary.to_csv(OUT / "assessed-value-per-acre-summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    run()
