#!/usr/bin/env python3
"""Estimate Detroit's assessed land value from vacant-parcel land rates."""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from strongtowns_detroit.repositories import data_repository

HERE = Path(__file__).resolve().parent
FORUM = HERE.parent
ROOT = FORUM.parents[1]
sys.path.insert(0, str(FORUM))

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

PARCELS = data_repository() / "pipelines/parcel-data/parcels_with_compliance.gpkg"
ROADS = FORUM / "spirit-plaza-accessibility/output/road_context.geojson"
OUT = HERE / "output"

NAVY = "#0c2340"
CREAM = "#fffaf0"
MUTED = "#647184"
NO_DATA = "#e4dfd6"
MIN_LANDMAP_COMPS = 5
MIN_NEIGHBORHOOD_COMPS = 10

BANDS = [
    ("Up to $7,500", 0, 7_500, "#a7c6ed"),
    ("$7,501–$15,000", 7_500, 15_000, "#5790db"),
    ("$15,001–$25,000", 15_000, 25_000, "#ffb549"),
    ("$25,001–$100,000", 25_000, 100_000, "#e8783d"),
    ("$100,001–$1 million", 100_000, 1_000_000, "#c83a3a"),
    ("More than $1 million", 1_000_000, np.inf, "#8f1d2d"),
]


def comparison_medians(
    training: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, float]:
    landmap = training.groupby("landmap")["observed_rate"].agg(
        ["median", "size"]
    )
    landmap = landmap.loc[
        landmap["size"].ge(MIN_LANDMAP_COMPS), "median"
    ]
    neighborhood = training.groupby("neighborhood")["observed_rate"].agg(
        ["median", "size"]
    )
    neighborhood = neighborhood.loc[
        neighborhood["size"].ge(MIN_NEIGHBORHOOD_COMPS), "median"
    ]
    return landmap, neighborhood, float(training["observed_rate"].median())


def model(frame: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, dict]:
    result = frame.copy()
    result["assessed"] = pd.to_numeric(
        result["assessed_value"], errors="coerce"
    )
    result["parcel_sqft"] = pd.to_numeric(
        result["total_square_footage"], errors="coerce"
    )
    vacant = (
        result["property_class_description"].fillna("").str.endswith("-VACANT")
        & result["assessed"].gt(0)
        & result["parcel_sqft"].gt(0)
    )
    training = result.loc[
        vacant, ["parcel_id", "landmap", "neighborhood", "assessed",
                 "parcel_sqft"]
    ].copy()
    training["observed_rate"] = (
        training["assessed"] / training["parcel_sqft"]
    )
    lower, upper = training["observed_rate"].quantile([0.01, 0.99])
    training = training[
        training["observed_rate"].between(lower, upper)
    ].copy()
    landmap, neighborhood, citywide = comparison_medians(training)
    result["estimated_land_rate_sqft"] = result["landmap"].map(landmap)
    result["estimate_method"] = np.where(
        result["estimated_land_rate_sqft"].notna(), "landmap median", ""
    )
    neighborhood_rate = result["neighborhood"].map(neighborhood)
    use_neighborhood = (
        result["estimated_land_rate_sqft"].isna()
        & neighborhood_rate.notna()
    )
    result.loc[
        use_neighborhood, "estimated_land_rate_sqft"
    ] = neighborhood_rate[use_neighborhood]
    result.loc[use_neighborhood, "estimate_method"] = "neighborhood median"
    use_city = (
        result["estimated_land_rate_sqft"].isna()
        & result["parcel_sqft"].gt(0)
    )
    result.loc[use_city, "estimated_land_rate_sqft"] = citywide
    result.loc[use_city, "estimate_method"] = "citywide median"
    result["estimated_assessed_land_value"] = (
        result["estimated_land_rate_sqft"] * result["parcel_sqft"]
    )
    result.loc[
        ~result["parcel_sqft"].gt(0),
        ["estimated_land_rate_sqft", "estimated_assessed_land_value"],
    ] = np.nan
    result["estimated_land_value_per_acre"] = (
        result["estimated_land_rate_sqft"] * 43_560
    )
    result["map_color"] = NO_DATA
    for _, lower_band, upper_band, color in BANDS:
        selected = (
            result["estimated_land_value_per_acre"].gt(lower_band)
            & result["estimated_land_value_per_acre"].le(upper_band)
        )
        result.loc[selected, "map_color"] = color

    # Fixed reproducible holdout validation.
    random = np.random.default_rng(42)
    train_mask = random.random(len(training)) < 0.80
    fit, holdout = training[train_mask], training[~train_mask].copy()
    fit_landmap, fit_neighborhood, fit_city = comparison_medians(fit)
    predicted = holdout["landmap"].map(fit_landmap)
    predicted = predicted.fillna(
        holdout["neighborhood"].map(fit_neighborhood)
    ).fillna(fit_city)
    ratio = np.maximum(
        holdout["observed_rate"] / predicted,
        predicted / holdout["observed_rate"],
    )
    absolute_percentage_error = (
        (holdout["observed_rate"] - predicted).abs()
        / holdout["observed_rate"]
    )
    total_estimated_land = float(
        result["estimated_assessed_land_value"].sum()
    )
    total_assessment = float(result["assessed"].fillna(0).sum())
    audit = {
        "model": (
            "median assessed value per square foot of vacant parcels by "
            "assessor landmap; neighborhood and citywide fallbacks"
        ),
        "raw_vacant_comparables": int(vacant.sum()),
        "training_comparables_after_1pct_tail_trim": int(len(training)),
        "landmap_groups": int(len(landmap)),
        "landmap_parcel_coverage": float(
            result["landmap"].map(landmap).notna().mean()
        ),
        "holdout_records": int(len(holdout)),
        "holdout_median_absolute_percentage_error": float(
            absolute_percentage_error.median()
        ),
        "holdout_within_factor_2": float((ratio <= 2).mean()),
        "estimated_assessed_land_value": total_estimated_land,
        "recorded_total_assessed_value": total_assessment,
        "estimated_land_share_of_total_assessment": (
            total_estimated_land / total_assessment
        ),
    }
    return result, audit


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
        buffer, format="jpeg", bbox_inches="tight", pad_inches=0,
        facecolor=CREAM, pil_kwargs={"quality": 91, "optimize": True},
    )
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def build_svg(frame: gpd.GeoDataFrame, audit: dict) -> str:
    image = map_image(frame)
    share = audit["estimated_land_share_of_total_assessment"]
    estimated_billions = audit["estimated_assessed_land_value"] / 1e9
    total_billions = audit["recorded_total_assessed_value"] / 1e9
    legend = [
        LegendItem("No estimate", NO_DATA),
        *[LegendItem(label, color) for label, _, _, color in BANDS],
    ]
    first_row = swatch_legend(
        legend[:4], positions=(67, 280, 530, 800),
        y=925, size=17, text_gap=8,
    )
    second_row = swatch_legend(
        legend[4:], positions=(67, 360, 700),
        y=965, size=17, text_gap=8,
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1100"
role="img" aria-labelledby="title desc">
<title id="title">An estimate of Detroit's assessed land value</title>
<desc id="desc">Estimated assessed land value per acre based on local vacant-parcel assessment rates. The estimated land component is {share:.0%} of total recorded assessed property value.</desc>
<style>{forum_css(title_size=60, metric_size=72, note_size=17,
extra_rules=".metric-label{font-size:14px}", muted=MUTED)}</style>
<rect class="paper" width="1600" height="1100"/>
{masthead_svg()}
{title_block("An estimate of Detroit's assessed land value",
"Vacant-parcel assessment rates applied within assessor land-map areas")}
{map_frame(f"data:image/jpeg;base64,{image}")}
{first_row}{second_row}
{metric_block(f"{share:.0%}", [
"ESTIMATED LAND SHARE OF DETROIT'S",
"TOTAL RECORDED ASSESSED VALUE",
], f"${estimated_billions:.1f}B estimated land value",
value_y=275, label_y=305, label_line_height=23, detail_gap=47)}
<text class="note" x="1123" y="402">${total_billions:.1f}B total assessed property value</text>
<text class="section-title" x="1120" y="485">How the estimate works</text>
<text class="note" x="1123" y="530">Vacant parcels reveal assessed land rates.</text>
<text class="note" x="1123" y="555">The median local rate is applied to each</text>
<text class="note" x="1123" y="580">parcel's recorded area.</text>
<text class="note" x="1123" y="635">This is a modeled assessed value—not an</text>
<text class="note" x="1123" y="660">official appraisal or market-price estimate.</text>
{source_lines([
f"Model: {audit['training_comparables_after_1pct_tail_trim']:,} vacant-parcel comparisons; assessor land-map median with neighborhood and citywide fallbacks.",
f"Validation: {audit['holdout_records']:,}-parcel holdout; median absolute percentage error {audit['holdout_median_absolute_percentage_error']:.1%}; {audit['holdout_within_factor_2']:.0%} within a factor of two.",
"Source: City of Detroit parcel assessment data downloaded in 2026. Dollar bands show estimated assessed land value per acre.",
], first_y=1018, line_height=24)}
</svg>"""


def run() -> None:
    frame, audit = model(gpd.read_file(
        PARCELS,
        columns=[
            "parcel_id", "property_class_description", "assessed_value",
            "total_square_footage", "landmap", "neighborhood", "geometry",
        ],
    ))
    OUT.mkdir(parents=True, exist_ok=True)
    write_svg_bundle(
        OUT, "detroit-estimated-assessed-land-value",
        "Estimated assessed land value in Detroit",
        build_svg(frame, audit),
        width=1600, height=1100, png_width=3200,
    )
    frame[[
        "parcel_id", "estimated_land_rate_sqft",
        "estimated_assessed_land_value", "estimated_land_value_per_acre",
        "estimate_method",
    ]].to_csv(OUT / "parcel-land-value-estimates.csv", index=False)
    (OUT / "land-value-model-audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    run()
