#!/usr/bin/env python3
"""Translate the BZA parking-space gap into surface-parking land area."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
from exhibit_brand import masthead_svg
PARKING_SUMMARY = PROJECT / "parking-requirements/output/summary.json"
TYPE_SUMMARY = (
    PROJECT
    / "parking-by-project-type/output/parking-project-type-summary.csv"
)
OUT = HERE / "output"

SQFT_PER_ACRE = 43_560
LOW_SQFT_PER_SPACE = 300
MID_SQFT_PER_SPACE = 325
HIGH_SQFT_PER_SPACE = 350

CREAM = "#fffaf0"
NAVY = "#082647"
RED = "#c8102e"
GOLD = "#ffb547"
BLUE = "#4e92ce"
MUTED = "#526477"
PALE = "#e4dccf"

TYPE_COLORS = {
    "Community & institutional": RED,
    "Food, drink & gathering": "#df5366",
    "Housing & mixed-use": NAVY,
    "Vehicle, production & industrial": BLUE,
    "Retail, office & personal services": "#79add7",
    "Cannabis facilities": GOLD,
}


def acres(spaces: float, sqft_per_space: float) -> float:
    return spaces * sqft_per_space / SQFT_PER_ACRE


def calculations() -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    parking = json.loads(PARKING_SUMMARY.read_text(encoding="utf-8"))
    types = pd.read_csv(TYPE_SUMMARY)
    gap = int(parking["requested_shortfall_spaces"])
    sensitivity = pd.DataFrame(
        [
            {
                "square_feet_per_space": value,
                "total_square_feet": gap * value,
                "acres": acres(gap, value),
                "equivalent_square_side_ft": (gap * value) ** 0.5,
            }
            for value in [250, 300, 325, 350, 400]
        ]
    )
    types["midpoint_acres"] = types["gap"].map(
        lambda value: acres(value, MID_SQFT_PER_SPACE)
    )
    return parking, types, sensitivity


def build_svg(
    parking: dict, types: pd.DataFrame, sensitivity: pd.DataFrame
) -> str:
    gap = int(parking["requested_shortfall_spaces"])
    low = acres(gap, LOW_SQFT_PER_SPACE)
    midpoint = acres(gap, MID_SQFT_PER_SPACE)
    high = acres(gap, HIGH_SQFT_PER_SPACE)
    side_low = (gap * LOW_SQFT_PER_SPACE) ** 0.5
    side_high = (gap * HIGH_SQFT_PER_SPACE) ** 0.5

    block_x, block_y, block_width, block_height = 56, 545, 940, 332
    cursor = block_x
    segments = []
    labels = []
    ordered = types.sort_values("gap", ascending=False)
    for _, row in ordered.iterrows():
        width = block_width * row.gap / gap
        color = TYPE_COLORS[row.project_type]
        segments.append(
            f'<rect x="{cursor:.1f}" y="{block_y}" width="{width:.1f}" '
            f'height="{block_height}" fill="{color}"/>'
        )
        if width >= 70:
            labels.append(
                f'<text class="block-value" x="{cursor + width / 2:.1f}" '
                f'y="{block_y + block_height / 2 - 4}" text-anchor="middle">'
                f'{row.midpoint_acres:.1f}</text>'
                f'<text class="block-unit" x="{cursor + width / 2:.1f}" '
                f'y="{block_y + block_height / 2 + 22}" text-anchor="middle">'
                f'acres</text>'
            )
        cursor += width

    legend = []
    for index, (_, row) in enumerate(ordered.iterrows()):
        column = index // 3
        item = index % 3
        x = 1050 + column * 270
        y = 590 + item * 82
        label = html.escape(row.project_type)
        legend.append(
            f'<rect x="{x}" y="{y}" width="18" height="18" '
            f'fill="{TYPE_COLORS[row.project_type]}"/>'
            f'<text class="legend-label" x="{x + 29}" y="{y + 15}">'
            f'{label}</text>'
            f'<text class="legend-value" x="{x + 29}" y="{y + 39}">'
            f'{int(row.gap):,} spaces · {row.midpoint_acres:.1f} acres</text>'
        )

    sensitivity_rows = []
    for index, row in sensitivity.iterrows():
        x = 1070 + index * 105
        sensitivity_rows.append(
            f'<text class="sensitivity-value" x="{x}" y="921" '
            f'text-anchor="middle">{int(row.square_feet_per_space)}</text>'
            f'<text class="sensitivity-acre" x="{x}" y="946" '
            f'text-anchor="middle">{row.acres:.1f} ac</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">Filling the recorded parking gap with surface lots would consume about eight acres</title>
<desc id="desc">If the 1,075-space gap in 35 BZA cases were supplied as conventional surface parking, it would occupy approximately 7.4 to 8.6 acres at 300 to 350 square feet per space.</desc>
<style>
.paper{{fill:{CREAM}}}
.kicker,.metric-label,.note,.source,.legend-label,.legend-value,.sensitivity-value,.sensitivity-acre,.block-unit{{font-family:Arial,Helvetica,sans-serif}}
.title,.dek,.metric,.section-title,.block-value{{font-family:Georgia,'Times New Roman',serif;fill:{NAVY}}}
.kicker{{font-size:16px;font-weight:700;letter-spacing:3px;fill:{RED}}}
.title{{font-size:58px;font-weight:700}}.dek{{font-size:24px;fill:#48596d}}
.metric{{font-size:75px;font-weight:700}}.metric-label{{font-size:15px;font-weight:700;letter-spacing:1.2px;fill:{MUTED}}}
.section-title{{font-size:27px;font-weight:700}}.note{{font-size:18px;fill:#34475d}}
.source{{font-size:13px;fill:{MUTED}}}.legend-label{{font-size:15px;font-weight:700;fill:{NAVY}}}
.legend-value{{font-size:14px;fill:{MUTED}}}.block-value{{font-size:31px;font-weight:700;fill:{CREAM}}}
.block-unit{{font-size:13px;font-weight:700;letter-spacing:1px;fill:{CREAM}}}
.sensitivity-value{{font-size:15px;font-weight:700;fill:{NAVY}}}
.sensitivity-acre{{font-size:13px;fill:{MUTED}}}
</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
<text class="title" x="52" y="120">Filling the recorded parking gap with surface lots</text>
<text class="title" x="52" y="184">would consume about eight acres</text>
<text class="dek" x="55" y="231">Land equivalent of 1,075 spaces across 35 BZA cases with explicit counts</text>

<text class="metric" x="60" y="365">{gap:,}</text>
<text class="metric-label" x="65" y="397">SPACES IN THE REQUESTED GAP</text>
<text class="metric" x="465" y="365">{low:.1f}–{high:.1f}</text>
<text class="metric-label" x="470" y="397">ACRES AT 300–350 SQ. FT. PER SPACE</text>
<text class="metric" x="1035" y="365">{side_low:.0f}–{side_high:.0f}</text>
<text class="metric-label" x="1040" y="397">FEET PER SIDE IF ARRANGED AS A SQUARE</text>

<text class="section-title" x="55" y="478">The eight-acre midpoint by project type</text>
<text class="note" x="55" y="510">Each block’s width represents its share of the 1,075-space gap</text>
{''.join(segments)}
{''.join(labels)}
<text class="source" x="56" y="903">Midpoint conversion: 325 sq. ft. per space · {midpoint:.1f} acres total</text>

<text class="section-title" x="1045" y="535">Project types</text>
{''.join(legend)}
<text class="section-title" x="1045" y="874">Sensitivity</text>
<text class="source" x="1047" y="896">Square feet per surface space → resulting acres</text>
{''.join(sensitivity_rows)}

<line x1="55" y1="1000" x2="1545" y2="1000" stroke="{PALE}" stroke-width="2"/>
<text class="note" x="55" y="1033">This is a land-equivalent estimate, not observed construction. Most applicants received relief from at least part of the recorded gap.</text>
<text class="source" x="55" y="1061">EPA reports 250–400 sq. ft. per residential surface space, averaging about 350; APA uses 300 sq. ft. including aisles and landscaping. Analysis range: 300–350.</text>
</svg>"""


def write_assets(
    parking: dict, types: pd.DataFrame, sensitivity: pd.DataFrame
) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    svg = build_svg(parking, types, sensitivity)
    stem = "detroit-parking-land-consumption"
    svg_path = OUT / f"{stem}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    (OUT / f"{stem}.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Detroit parking land consumption</title>"
        "<style>html,body{margin:0;background:#fffaf0}"
        "main{width:min(100%,1600px);margin:auto}"
        "svg{display:block;width:100%;height:auto}"
        "@media print{@page{size:16in 11in;margin:0}}</style></head>"
        f"<body><main>{svg}</main></body></html>",
        encoding="utf-8",
    )
    renderer = shutil.which("rsvg-convert")
    if renderer:
        subprocess.run(
            [
                renderer, "--width", "3200",
                "--output", str(OUT / f"{stem}.png"), str(svg_path),
            ],
            check=True,
        )
    sensitivity.to_csv(OUT / "parking-land-sensitivity.csv", index=False)
    types.to_csv(OUT / "parking-land-by-project-type.csv", index=False)
    summary = {
        "space_gap": int(parking["requested_shortfall_spaces"]),
        "presentation_range_sqft_per_space": [
            LOW_SQFT_PER_SPACE, HIGH_SQFT_PER_SPACE
        ],
        "presentation_range_acres": [
            acres(
                parking["requested_shortfall_spaces"],
                LOW_SQFT_PER_SPACE,
            ),
            acres(
                parking["requested_shortfall_spaces"],
                HIGH_SQFT_PER_SPACE,
            ),
        ],
        "midpoint_sqft_per_space": MID_SQFT_PER_SPACE,
        "midpoint_acres": acres(
            parking["requested_shortfall_spaces"], MID_SQFT_PER_SPACE
        ),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


def main() -> None:
    parking, types, sensitivity = calculations()
    if int(types["gap"].sum()) != int(
        parking["requested_shortfall_spaces"]
    ):
        raise ValueError("Project-type gaps do not reconcile to parking total")
    if not (
        LOW_SQFT_PER_SPACE
        < MID_SQFT_PER_SPACE
        < HIGH_SQFT_PER_SPACE
    ):
        raise ValueError("Presentation assumptions are not ordered")
    write_assets(parking, types, sensitivity)


if __name__ == "__main__":
    main()
