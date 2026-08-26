#!/usr/bin/env python3
"""Build the minimum-lot-width exhibit linking parcel frontage to BZA relief."""

from __future__ import annotations

import html
import json
import shutil
import subprocess

import geopandas as gpd
import pandas as pd

from build_minimum_lot_size_asset import (
    BZA,
    CREAM,
    HERE,
    LIGHT_BLUE,
    MUTED,
    NAVY,
    OUT,
    OUTSIDE,
    PARCELS,
    RED,
)
from build_minimum_lot_size_asset import ROADS
from exhibit_components import (
    LegendItem,
    forum_css,
    map_frame,
    metric_block,
    swatch_legend,
)
from strongtowns_detroit.graphics import (
    CONFERENCE_LANDSCAPE,
    Graphic,
    SvgComponent,
    render_graphic_svg,
    write_graphic_bundle,
)
from parcel_exhibit_components import bza_case_stat, is_detroit_parks_taxpayer
import base64
import io
import matplotlib.pyplot as plt

WIDTH_MINIMUM = 50
TOLERANCE = 0.01
SCREENING_BOUNDARY = WIDTH_MINIMUM * (1 - TOLERANCE)

WIDTH_EVIDENCE = (
    r"(?:minimum lot width|deficient lot width|insufficient lot width|"
    r"lot width required)"
)
EXCESS_EVIDENCE = (
    r"(?:excessive lot width|maximum lot width|maximum lot size and width)"
)


def classify_lot_width(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    result = frame.copy()
    result["parks_taxpayer"] = is_detroit_parks_taxpayer(result)
    result["in_scope"] = (
        result["zoning_district"].isin([f"R{i}" for i in range(1, 7)])
        & ~result["parks_taxpayer"]
    )
    result["width_ft"] = pd.to_numeric(result["frontage"], errors="coerce")
    result["evaluated"] = result["in_scope"] & result["width_ft"].gt(0)
    result["below_minimum"] = (
        result["evaluated"] & result["width_ft"].lt(SCREENING_BOUNDARY)
    )
    return result


def select_residential_width_cases(
    histories: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    cases = categories[categories["category"].eq("lot_dimensions")].merge(
        histories, on="case_history_id", how="inner", validate="one_to_one"
    )
    evidence = (
        cases["evidence"].fillna("") + " " + cases["proposal"].fillna("")
    )
    is_width = evidence.str.contains(
        WIDTH_EVIDENCE, case=False, regex=True
    )
    is_excess = evidence.str.contains(
        EXCESS_EVIDENCE, case=False, regex=True
    )
    is_residential = cases["proposal"].fillna("").str.contains(
        r"\bR[1-6](?:\b|-)", case=False, regex=True
    )
    return cases[is_width & ~is_excess & is_residential].copy()


def map_image(frame: gpd.GeoDataFrame) -> str:
    outside = frame[frame["zoning_district"].notna() & ~frame["in_scope"]]
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
    width_cases: pd.DataFrame,
    *,
    title: str = "Detroit's 50-foot minimum residential lot width",
    subtitle: str = (
        "Recorded R1–R6 frontage compared with the 50-foot minimum lot width"
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
LegendItem("Meets minimum width", NAVY),
LegendItem("Not evaluated / outside R1–R6", OUTSIDE),
], positions=(67, 345, 565))}
{metric_block(f"{share:.0%}", ["BELOW THE 50-FT. MINIMUM"],
f"{affected:,} of {total:,} evaluated parcels")}
<text class="note" x="1120" y="379">Unless lot-of-record protection, a combined</text>
<text class="note" x="1120" y="404">zoning lot, adjustment, variance, or another</text>
<text class="note" x="1120" y="429">exception applies, new development cannot</text>
<text class="note" x="1120" y="454">proceed under this minimum.</text>
{bza_case_stat(len(width_cases), "lot-width", "residential minimum-lot-width")}
"""
    return Graphic(
        title=title,
        subtitle=subtitle,
        visual=SvgComponent(visual, 1600, 780, min_y=180),
        sources=sources if sources is not None else (
            "Classification: below minimum when recorded frontage is under "
            "49.5 ft.; the 1% tolerance avoids false precision around the "
            "legal 50-ft. boundary.",
            "Frontage is a validated proxy, not a universal legal lot-width "
            f"measurement. Parcel result: {affected:,} below · {meets:,} meet · "
            f"{unknown:,} not enough data · {parks:,} Parks & Recreation "
            f"taxpayer · {outside:,} outside R1–R6.",
        ),
        description=description if description is not None else (
            f"{affected:,} of {total:,} evaluated R1 through R6 parcels have "
            "recorded frontage more than one percent below 50 feet. "
            f"{len(width_cases)} BZA case histories requested residential "
            "minimum-lot-width relief."
        ),
    )


def build_svg(frame: gpd.GeoDataFrame, width_cases: pd.DataFrame) -> str:
    return render_graphic_svg(build_graphic(frame, width_cases))


def run() -> None:
    frame = classify_lot_width(
        gpd.read_file(
            PARCELS,
            columns=[
                "parcel_id", "zoning_district", "frontage",
                "taxpayer_1", "taxpayer_2", "geometry",
            ],
        )
    )
    histories = pd.read_csv(BZA / "case_histories.csv")
    categories = pd.read_csv(BZA / "case_categories.csv")
    width_cases = select_residential_width_cases(histories, categories)
    OUT.mkdir(parents=True, exist_ok=True)
    stem = "detroit-minimum-lot-width"
    write_graphic_bundle(
        OUT, stem, build_graphic(frame, width_cases),
        aspect_ratio=CONFERENCE_LANDSCAPE, png_width=3200,
    )
    width_cases.to_csv(
        OUT / "minimum-lot-width-bza-cases.csv", index=False
    )
    summary = {
        "legal_minimum_ft": WIDTH_MINIMUM,
        "screening_boundary_ft": SCREENING_BOUNDARY,
        "evaluated_parcels": int(frame["evaluated"].sum()),
        "below_minimum_parcels": int(frame["below_minimum"].sum()),
        "below_minimum_share": float(
            frame["below_minimum"].sum() / frame["evaluated"].sum()
        ),
        "residential_minimum_lot_width_bza_cases": int(len(width_cases)),
        "granted_or_reversed": int(
            width_cases["final_outcome"].eq("granted_reversed").sum()
        ),
    }
    (OUT / "minimum-lot-width-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUT / (stem + '.html')}")


if __name__ == "__main__":
    run()
