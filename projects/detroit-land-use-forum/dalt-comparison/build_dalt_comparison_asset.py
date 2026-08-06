#!/usr/bin/env python3
"""Build an original explanatory chart of depreciation-assisted LVT."""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORUM = HERE.parent
sys.path.insert(0, str(FORUM))

from exhibit_brand import masthead_svg
from exhibit_components import (
    forum_css,
    metric_block,
    source_lines,
    title_block,
    write_svg_bundle,
)

OUT = HERE / "output"
NAVY = "#0c2340"
RED = "#c83a3a"
BLUE = "#5790db"
GRAY = "#7d8288"
CREAM = "#fffaf0"
GREEN = "#3f7d68"

LAND_VALUE = 100_000
BUILDING_VALUE = 200_000
TAX_RATE = 0.02
BUILDING_LIFE = 20
ABATEMENT_YEARS = 10
DISCOUNT_RATE = 0.05
# A transparent, reproducible approximation of the article's illustrative
# front-loaded depreciation curve. It leaves about 8% of initial improvement
# value at year 10 and reaches zero at year 20.
DEPRECIATION_POWER = 3.6


def series() -> list[dict[str, float]]:
    rows = []
    for year in range(BUILDING_LIFE + 1):
        remaining = max(0.0, 1 - year / BUILDING_LIFE)
        building = BUILDING_VALUE * remaining**DEPRECIATION_POWER
        conventional = TAX_RATE * (LAND_VALUE + building)
        dalt = TAX_RATE * (
            LAND_VALUE + (building if year >= ABATEMENT_YEARS else 0)
        )
        lvt = TAX_RATE * LAND_VALUE
        rows.append(
            {
                "year": year,
                "building": building,
                "conventional": conventional,
                "dalt": dalt,
                "lvt": lvt,
            }
        )
    return rows


def path_for(
    rows: list[dict[str, float]],
    key: str,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    ymax: float,
) -> str:
    points = []
    for row in rows:
        x = x0 + width * row["year"] / BUILDING_LIFE
        y = y0 + height * (1 - row[key] / ymax)
        points.append(f"{x:.1f},{y:.1f}")
    return "M" + " L".join(points)


def pv_reduction(rows: list[dict[str, float]]) -> float:
    conventional_building = 0.0
    dalt_building = 0.0
    for row in rows:
        discount = (1 + DISCOUNT_RATE) ** row["year"]
        building_tax = TAX_RATE * row["building"]
        conventional_building += building_tax / discount
        if row["year"] >= ABATEMENT_YEARS:
            dalt_building += building_tax / discount
    return 1 - dalt_building / conventional_building


def build_svg() -> str:
    rows = series()
    reduction = pv_reduction(rows)
    x0, y0, width, height = 120, 280, 960, 500
    ymax = 6_200
    chart_bottom = y0 + height

    grid = []
    for value in (0, 2_000, 4_000, 6_000):
        y = y0 + height * (1 - value / ymax)
        grid.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + width}" '
            f'y2="{y:.1f}" class="grid"/>'
            f'<text x="{x0 - 18}" y="{y + 5:.1f}" class="axis" '
            f'text-anchor="end">${value // 1000}k</text>'
        )
    for year in (0, 5, 10, 15, 20):
        x = x0 + width * year / BUILDING_LIFE
        grid.append(
            f'<line x1="{x:.1f}" y1="{chart_bottom}" x2="{x:.1f}" '
            f'y2="{chart_bottom + 7}" class="axis-line"/>'
            f'<text x="{x:.1f}" y="{chart_bottom + 34}" class="axis" '
            f'text-anchor="middle">{year}</text>'
        )

    abatement_x = x0 + width * ABATEMENT_YEARS / BUILDING_LIFE
    lines = [
        ("conventional", RED, "", 5),
        ("dalt", GREEN, "", 5),
        ("lvt", GRAY, 'stroke-dasharray="10 9"', 4),
    ]
    paths = "".join(
        f'<path d="{path_for(rows, key, x0=x0, y0=y0, width=width, height=height, ymax=ymax)}" '
        f'fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linejoin="round" {dash}/>'
        for key, color, dash, stroke in lines
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">A ten-year building exemption approaches a land value tax</title>
<desc id="desc">Illustrative annual tax under conventional property tax, a ten-year building-value exemption, and a pure land value tax.</desc>
<style>{forum_css(title_size=45, metric_size=72, note_size=17,
extra_rules=f"""
.grid{{stroke:#ded8ce;stroke-width:1}}
.axis-line{{stroke:{NAVY};stroke-width:1.5}}
.axis,.chart-label{{font-family:Arial,Helvetica,sans-serif;fill:#526276;font-size:15px}}
.legend-text{{font-family:Arial,Helvetica,sans-serif;fill:{NAVY};font-size:16px}}
.callout{{font-family:Arial,Helvetica,sans-serif;fill:{NAVY};font-size:17px;font-weight:700}}
""")}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{title_block("A ten-year building exemption approaches a land value tax",
"Illustrative annual tax on $100,000 of land and a $200,000 building")}
<text class="chart-label" x="{x0}" y="{y0 - 28}">ANNUAL TAX AT THE SAME 2% RATE</text>
{''.join(grid)}
<line x1="{x0}" y1="{chart_bottom}" x2="{x0 + width}" y2="{chart_bottom}" class="axis-line"/>
<line x1="{abatement_x}" y1="{y0}" x2="{abatement_x}" y2="{chart_bottom}" stroke="{NAVY}" stroke-width="1.5" stroke-dasharray="3 6" opacity=".55"/>
<text class="callout" x="{abatement_x + 12}" y="{y0 + 28}">Building exemption ends</text>
{paths}
<text class="axis" x="{x0 + width / 2}" y="{chart_bottom + 50}" text-anchor="middle">YEAR OF BUILDING LIFE</text>
<line x1="122" y1="875" x2="167" y2="875" stroke="{RED}" stroke-width="5"/>
<text class="legend-text" x="180" y="881">Conventional property tax</text>
<line x1="405" y1="875" x2="450" y2="875" stroke="{GREEN}" stroke-width="5"/>
<text class="legend-text" x="463" y="881">DALT: building exempt for 10 years</text>
<line x1="785" y1="875" x2="830" y2="875" stroke="{GRAY}" stroke-width="4" stroke-dasharray="10 9"/>
<text class="legend-text" x="843" y="881">Pure land value tax</text>
{metric_block(f"{reduction:.0%}", [
"LESS PRESENT VALUE OF",
"BUILDING TAX UNDER DALT",
], x=1160, value_y=325, label_y=357, label_line_height=22)}
<text class="section-title" x="1160" y="475">What changes</text>
<text class="note" x="1163" y="520">New improvements are untaxed during</text>
<text class="note" x="1163" y="546">their first ten years. Land remains taxed.</text>
<text class="note" x="1163" y="600">When buildings depreciate rapidly, the</text>
<text class="note" x="1163" y="626">remaining tax resembles a land value tax.</text>
<text class="section-title" x="1160" y="710">What this is not</text>
<text class="note" x="1163" y="755">This is an illustrative mechanism—not a</text>
<text class="note" x="1163" y="781">Detroit revenue estimate or legal analysis.</text>
{source_lines([
"Illustration adapted from Lars Doucet, “DALT: Depreciation-Assisted Land Value Tax,” Progress and Poverty, July 29, 2026.",
f"Assumptions: 2% tax rate; 20-year building life; front-loaded depreciation; {ABATEMENT_YEARS}-year improvement exemption; {DISCOUNT_RATE:.0%} discount rate.",
"All three lines use the same tax rate for comparison. A revenue-neutral policy would require a different rate.",
], first_y=1018, line_height=24)}
</svg>"""


def run() -> None:
    write_svg_bundle(
        OUT,
        "dalt-property-tax-comparison",
        "A ten-year building exemption approaches a land value tax",
        build_svg(),
        width=1600,
        height=1100,
        png_width=3200,
    )
    print(f"Wrote DALT chart to {OUT}")


if __name__ == "__main__":
    run()
